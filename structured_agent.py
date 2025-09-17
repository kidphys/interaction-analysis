from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field
from typing import Union, List, Dict, Any, Literal, Annotated
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from redshift_api import execute_with_columns
import traceback
from dotenv import load_dotenv
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich import print as rprint

# Load environment variables
load_dotenv('.env.local')

# Pydantic models for structured responses
class MessageItem(BaseModel):
    type: Literal["message"]
    content: str = Field(description="Agent comment or analysis message")

class TableItem(BaseModel):
    type: Literal["table"]
    data: Dict[str, List[Any]] = Field(description="Table data in 'series' orient: {column_name: [values]}")
    title: str = Field(description="Title for the table")

class ChartItem(BaseModel):
    type: Literal["chart"]
    data: Dict[str, List[Any]] = Field(description="Chart data in 'series' orient: {column_name: [values]}")
    chart_type: str = Field(description="Type of chart (bar, line, pie, etc.)")
    title: str = Field(description="Title for the chart")

class InsightResponse(BaseModel):
    items: List[Annotated[Union[MessageItem, TableItem, ChartItem], Field(discriminator='type')]] = Field(
        description="List of response items containing messages, tables, or charts"
    )

# Define the tool for the dashboard context
@tool
def run_query_tool(sql: str, config: RunnableConfig):
    """
    Run a query on the Redshift data warehouse given the following table:
    `answers`
        user_id (varchar)
        slide_id (varchar)
        question_id (varchar)
        participant_id (varchar)
        presentation_id (varchar)
        presentation_title (varchar)
        slide_type (varchar): can be 'Pick Answer', 'Poll', 'Open Ended'
        slide_title (varchar): the title of the question asked in the slide
        submitted_answer_text (varchar): the answer that this participant submitted
        correct (boolean)
        createdat (timestamp)
    """
    # Get user_id from session state
    user_id = config['metadata']['user_id']
    # user_id = 1472007 # duke's id

    final_sql = f"""
   WITH answers AS (
    SELECT
        fa.user_id,
        fa.slide_id,
        fa.question_id,
        fa.participant_id,
        fa.master_presentation_id as presentation_id,
        fa.slide_type,
        dq.slide_title,
        dp.title as presentation_title,
        fa.submitted_answer_text,
        fa.correct,
        fa.createdat
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_questions dq
        ON fa.question_id = dq.id
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    WHERE fa.user_id = '{user_id}' -- Replace with actual user ID or bind parameter
)
    {sql}
    """

    try:
        rows, cols = execute_with_columns(final_sql)
        # rows = "[('Who is this lady or gentleman?', 801, 327), ('Remember the wishes for Santa?', 54, 48), ('Who is this handsome redhead?', 43, 37), ('Who is this lady or gentleman? (on the left)', 84, 34), ('Steps to process requests', 45, 33), ('Match principle with their meaning', 34, 28), ('AhaSlides loves this place so much, we went there for company trip TWICE', 30, 28), ('Choose the correct answer?', 27, 26), ('Who is this lady or gentleman? (on the left)\\n', 39, 26), ('Which positions will have candidates joining AhaSlides next month?', 28, 26)]"
        # cols =  "RMKeyView(['slide_title', 'total_answers', 'correct_answers'])"
        return {
            'rows': str(rows),
            'cols': str(cols),
            'message': 'test'
        }
    except Exception as e:
        import traceback
        print(f'Exception type: {type(e)}')
        print(f'Args: {e.args}')
        print('Full traceback:')
        traceback.print_exc()
        return f"Error executing query: {str(e)}"

# System prompt
system_prompt = """
You are a helpful assistant that can give insights about the data.

It's critical that your final response should use the structured format with an 'items' list that can contain:
1. message items: for analysis, comments, and recommendations
2. table items: for displaying data tables with column names and values (always provide a descriptive title)
3. chart items: for displaying charts with data and chart type (bar, line, area, pie, etc.) (always provide a descriptive title)

You can mix and match these items to provide comprehensive responses with both analysis and visual data.
For tables and charts, always provide meaningful titles that describe what the data represents.
Data should be in 'series' orient format: {column_name: [list_of_values]}
"""

class StructuredAgent:
    """
    A structured response agent that can query data warehouse and return structured responses
    with messages, tables, and charts.
    """

    def __init__(self, user_id="1472007", model_name="anthropic:claude-sonnet-4-20250514"):
        self.user_id = user_id
        self.model_name = model_name
        self.agent_executor = None
        self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name)
        tools = [run_query_tool]
        sys_message = SystemMessage(content=system_prompt)

        self.agent_executor = create_react_agent(
            model, tools, checkpointer=memory,
            prompt=sys_message, response_format=InsightResponse
        )

    def _get_config(self):
        return {
            "configurable": {
                "thread_id": f"user_{self.user_id}",
                "user_id": self.user_id
            }
        }

    def query(self, prompt: str) -> InsightResponse:
        """
        Query the agent with a prompt and return structured response

        Args:
            prompt: The question or request to the agent

        Returns:
            InsightResponse: Structured response with items list
        """
        if not self.agent_executor:
            raise RuntimeError("Agent not initialized")

        input_message = {
            "role": "user",
            "content": prompt
        }

        try:
            last_message = None
            # Get the final response from the agent
            for step in self.agent_executor.stream(
                {"messages": [input_message]},
                self._get_config(),
                stream_mode="values"
            ):
                if step["messages"]:
                    last_message = step["messages"][-1]
            self._process_structured_output(last_message)
            return last_message
        except Exception as e:
            print(f"Error executing agent: {str(e)}")
            return None

    def stream_query(self, prompt: str):
        """
        Stream the agent response for real-time display

        Args:
            prompt: The question or request to the agent

        Yields:
            Agent response steps
        """
        if not self.agent_executor:
            raise RuntimeError("Agent not initialized")

        input_message = {
            "role": "user",
            "content": prompt
        }

        try:
            for step in self.agent_executor.stream(
                {"messages": [input_message]},
                self._get_config(),
                stream_mode="values"
            ):
                if 'structured_response' in step:
                    self.insight_response = step['structured_response']
                yield step
        except Exception as e:
            print(f"Error executing agent: {str(e)}")
            yield None

    def invoke(self, prompt: str):
        """
        Invoke the agent with a prompt and return structured response
        """
        input_message = {
            "role": "user",
            "content": prompt
        }
        return self.agent_executor.invoke({"messages": [input_message]}, self._get_config())

    def _process_structured_output(self, response):
        """
        @Deprecated
        Process the structured output from the agent
        """
        json_text = extract_json_from_content(response.content)
        self.insight_response = InsightResponse(**json_text)

    def get_structured_output(self):
        """
        Get the structured output from the agent
        """
        if self.insight_response is None:
            raise ValueError("Structured output not found or not processed yet")
        return self.insight_response

# Convenience function for backward compatibility
def initialize_agent():
    """Initialize and return a StructuredAgent instance"""
    return StructuredAgent()

def stream_agent_response(prompt, user_id="1472007"):
    """
    Stream agent response - backward compatibility function

    Args:
        prompt: The question or request
        user_id: User ID for the session

    Returns:
        The final agent response content
    """
    agent = StructuredAgent(user_id=user_id)
    return agent.query(prompt)


import re


def extract_json_from_content(content: str) -> dict:
    # Extract the JSON part
    start_idx = content.find('{\n  "items":')
    if start_idx == -1:
        raise ValueError("No structured JSON found")

    json_part = content[start_idx:]

    # Multiple cleaning steps
    json_part = json_part.replace("\\'", "'")  # Fix escaped quotes
    json_part = json_part.replace('\\n', ' ')  # Replace literal \n with spaces
    json_part = re.sub(r'\n\s+', ' ', json_part)  # Remove excessive whitespace/newlines
    json_part = re.sub(r'\s+', ' ', json_part)  # Normalize whitespace

    # Fix common JSON issues
    json_part = re.sub(r',(\s*[}\]])', r'\1', json_part)  # Remove trailing commas
    json_part = re.sub(r'([}\]])\s*([{\[])', r'\1,\2', json_part)  # Add missing commas between objects

    try:
        return json.loads(json_part)
    except json.JSONDecodeError as e:
        print(f"JSON error at position {e.pos}: {json_part[max(0, e.pos-50):e.pos+50]}")
        raise

# Example usage and testing
if __name__ == "__main__":
    # Test the agent in isolation

    agent = StructuredAgent(user_id="259137")

    # Test query
    test_prompt = "Give me the top 5 questions with their correct answers"

    step_count = 0
    for step in agent.stream_query(test_prompt):
        print(f'\n' + '-' * 100 + '\n')
        print(step)
        last_message = step["messages"][-1]
    print('\n\nStructured Output', agent.get_structured_output())


