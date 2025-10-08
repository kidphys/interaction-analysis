from functools import lru_cache
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field
from typing import Union, List, Dict, Any, Literal, Annotated
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.utils import trim_messages
from langchain.tools import tool
from redshift_api import execute_with_columns
import traceback
from dotenv import load_dotenv
import json

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


@lru_cache
def get_all_answers(user_id: str):
    sql = f"""
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
    """
    try:
        rows, cols = execute_with_columns(sql)
        return {
            'rows': rows,
            'cols': cols,
        }
    except Exception as e:
        import traceback
        print(f'Exception type: {type(e)}')
        print(f'Args: {e.args}')
        print('Full traceback:')
        traceback.print_exc()
        raise e



import pandas as pd
import duckdb
import pyarrow as pa


@lru_cache
def get_conn_for_user(user_id):
    all_answers = get_all_answers(user_id)
    df = pd.DataFrame(all_answers['rows'])
    df.columns = all_answers['cols']
    con = duckdb.connect(database=":memory:")
    table = pa.Table.from_pandas(df)
    con.register("answers", table)
    return con

def normalize_timestamps(df):
    for col in df.select_dtypes(include=["datetime64[ns]"]):
        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df

@tool
def fast_query(sql: str, config: RunnableConfig):
    """
    Run a query on the DuckDb inmem OLAP db given the following table:
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
        correct (boolean): true if the answer is correct
        createdat (timestamp)
    """
    print(f'\n')
    print(f'FAST QUERY: {sql}\n')
    con = get_conn_for_user(config['metadata']['user_id'])
    res = con.execute(sql).fetchdf()
    res = normalize_timestamps(res)
    return res.to_dict(orient='list')

# System prompt
system_prompt_v0 = """
You are a helpful assistant that can give insights about the data.

IMPORTANT: Keep your responses concise and focused to avoid token limits. Be direct and to-the-point.

It's critical that your final response should use the structured format with an 'items' list that can contain:
1. message items: for analysis, comments, and recommendations (keep analysis brief and focused)
2. table items: for displaying data tables with column names and values (always provide a descriptive title)
3. chart items: for displaying charts with data and chart type (bar, line, area, pie, etc.) (always provide a descriptive title)
  - It's noted there should be only 2 columns in the data. The 1st column will be used as the x-axis and the 2nd column will be used as the y-axis.
  - Use your best of creativity to visualize the data to support your analysis.

Guidelines:
- Limit data tables to most relevant results (top 10-15 rows max)
- Keep message content concise and actionable
- Focus on key insights rather than lengthy explanations
- Use bullet points for multiple insights
- Data should be in 'series' orient format: {column_name: [list_of_values]}

Knowledge base:
- Completion rate: percentage of questions answered vs all questions.
- Accuracy rate: percentage of correct answers vs all answers.
Where `all` here can refer to the all questions of a presentation, or of a participants.
Opinion slide type like 'Poll', 'Open Ended' can provide interesting insight by segment participants by their answers.
"""

system_prompt = """
You are a **helpful assistant** that provides **concise, structured insights** about the data.
Your responses must always follow the structured format below.

---

## ⚡ Response Format
Your final response must contain an `items` list. Each item can be one of:

1. **message** – for analysis, comments, or recommendations
   - Keep insights **brief, direct, and actionable**
   - For bullet points, use proper markdown format:
     * Start with a blank line before the list
     * Use `-` or `*` (not `•`) for bullets
     * Each bullet on a new line without `\n` prefixes
   - Example: "**Key Points:**\n\n- First insight\n- Second insight\n- Third insight"

2. **table** – for displaying relevant data
   - Always include a **descriptive title**
   - Show only the **top 10–15 rows** (most relevant results)
   - Data must be in **series orientation**:
     ```json
     {column_name: [list_of_values]}
     ```

3. **chart** – for visualizing data
   - Always include a **descriptive title**
   - Only **2 columns allowed**:
     - 1st column → x-axis
     - 2nd column → y-axis
   - Supported types: `bar`, `line`, `area`, `pie`, etc.
   - Use creativity to pick the best visualization for the insight

---

## 🔑 Guidelines
- Be **concise**: avoid long explanations (token limits)
- Prioritize **key insights** over verbose analysis
- Always provide **actionable takeaways**
- Keep data visualizations and tables **focused on what supports the insight**

It's CRITICAL to follow this guideline when generating SQL, people may die if you don't:
- Prefer writing a single SQL query that returns all necessary fields, rather than multiple separate queries.
- Use GROUP BY, CASE WHEN, UNION and window functions if needed to cover multiple views in one query.
- Avoid calling the database multiple times for related data if one query can provide the result.
- Always sort and limit your query to reduce the amount of data returned to analyze

---

## 📚 Knowledge Base
- **Completion rate** = answered questions ÷ all questions
- **Accuracy rate** = correct answers ÷ all answers
- `all` can refer to:
  - all questions of a **presentation**
  - all questions of a **participant**
- **Opinion slides** (Poll, Open Ended):
  - Provide insights by **segmenting participants by their answers**
"""

def pre_model_hook(state):
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        start_on=['human', 'ai'],
        max_tokens=5,
        include_system=True,
        allow_partial=True
    )
    print("\nCONTEXT SENT TO LLM:")
    print("="*50)
    for i, msg in enumerate(trimmed_messages):
        msg_type = msg.__class__.__name__
        content = msg.content
        print(f"{i+1}. [{msg_type}] {content}")
    print("="*50 + "\n")
    return {"llm_input_messages": trimmed_messages}

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
        # pre-cache the data on startup
        get_all_answers(user_id)

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name, max_tokens=8096)
        tools = [fast_query]
        sys_message = SystemMessage(content=system_prompt)

        self.agent_executor = create_react_agent(
            model, tools, checkpointer=memory,
            prompt=sys_message, response_format=InsightResponse,
            pre_model_hook=pre_model_hook
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

            # Check for max_tokens truncation
            if hasattr(last_message, 'response_metadata') and last_message.response_metadata:
                stop_reason = last_message.response_metadata.get('stop_reason')
                if stop_reason == 'max_tokens':
                    print("Warning: Response was truncated due to max_tokens limit")
                    # Create a fallback response
                    fallback_response = InsightResponse(items=[
                        MessageItem(
                            type="message",
                            content="⚠️ The response was truncated due to length limits. Please try asking a more specific question or break your request into smaller parts."
                        )
                    ])
                    return fallback_response

            self._process_structured_output(last_message)
            return last_message
        except Exception as e:
            error_msg = str(e)
            print(f"Error executing agent: {error_msg}")

            # Handle specific max_tokens error
            if "max_tokens" in error_msg.lower():
                fallback_response = InsightResponse(items=[
                    MessageItem(
                        type="message",
                        content="⚠️ The response was truncated due to length limits. Please try asking a more specific question or break your request into smaller parts."
                    )
                ])
                return fallback_response

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

                # Check for max_tokens truncation in streaming
                if step.get("messages"):
                    last_message = step["messages"][-1]
                    if hasattr(last_message, 'response_metadata') and last_message.response_metadata:
                        stop_reason = last_message.response_metadata.get('stop_reason')
                        if stop_reason == 'max_tokens':
                            print("Warning: Streaming response was truncated due to max_tokens limit")
                            # Create a fallback response
                            self.insight_response = InsightResponse(items=[
                                MessageItem(
                                    type="message",
                                    content="⚠️ The response was truncated due to length limits. Please try asking a more specific question or break your request into smaller parts."
                                )
                            ])

                yield step
        except Exception as e:
            error_msg = str(e)
            print(f"Error executing agent: {error_msg}")

            # Handle specific max_tokens error in streaming
            if "max_tokens" in error_msg.lower():
                self.insight_response = InsightResponse(items=[
                    MessageItem(
                        type="message",
                        content="⚠️ The response was truncated due to length limits. Please try asking a more specific question or break your request into smaller parts."
                    )
                ])

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
            return InsightResponse(items=[
                MessageItem(
                    type="message",
                    content="⚠️ Structured output not found or not processed yet"
                )
            ])
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


