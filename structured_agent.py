from pydantic import BaseModel, Field
from typing import Union, List, Dict, Any, Literal, Annotated
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from redshift_api import execute_with_columns, execute_with_columns_without_cache
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

# Initialize Rich console for pretty printing with full content display
console = Console(width=120, force_terminal=True)

def pretty_print_content(content):
    """
    Pretty print complex content that might contain structured data

    Args:
        content: The content to print (could be string, list, dict, etc.)
    """
    if isinstance(content, list):
        # Handle list of content items (like tool calls)
        for i, item in enumerate(content):
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    # Text content
                    text_panel = Panel(
                        item.get('text', ''),
                        title=f"[bold blue]📝 Text Content {i+1}[/bold blue]",
                        border_style="blue",
                        padding=(1, 2)
                    )
                    console.print(text_panel)
                elif item.get('type') == 'tool_use' or 'id' in item:
                    # Tool call content
                    tool_info = []
                    if 'id' in item:
                        tool_info.append(f"[yellow]ID:[/yellow] {item['id']}")
                    if 'input' in item:
                        tool_info.append(f"[yellow]Input:[/yellow]")
                        # Format the input nicely - show full content
                        if isinstance(item['input'], dict):
                            for key, value in item['input'].items():
                                # Show full content without truncation
                                tool_info.append(f"  [cyan]{key}:[/cyan] {value}")
                        else:
                            tool_info.append(f"  {item['input']}")

                    tool_panel = Panel(
                        "\n".join(tool_info),
                        title=f"[bold magenta]🔧 Tool Call {i+1}[/bold magenta]",
                        border_style="magenta",
                        padding=(1, 2)
                    )
                    console.print(tool_panel)
                else:
                    # Generic dict content - show full content
                    dict_content = json.dumps(item, indent=2, default=str)

                    dict_panel = Panel(
                        dict_content,
                        title=f"[bold yellow]📋 Data Item {i+1}[/bold yellow]",
                        border_style="yellow",
                        padding=(1, 2)
                    )
                    console.print(dict_panel)
            else:
                # Non-dict items
                item_panel = Panel(
                    str(item),
                    title=f"[bold white]📄 Item {i+1}[/bold white]",
                    border_style="white",
                    padding=(1, 2)
                )
                console.print(item_panel)
    else:
        # Single content item
        if isinstance(content, str):
            # Try to parse as JSON if it looks like structured data
            if content.startswith('[') or content.startswith('{'):
                try:
                    parsed = json.loads(content)
                    pretty_print_content(parsed)
                    return
                except:
                    pass

            # Try to evaluate Python literal if it looks like one
            if content.startswith('[{') and 'text' in content and 'type' in content:
                try:
                    import ast
                    parsed = ast.literal_eval(content)
                    pretty_print_content(parsed)
                    return
                except:
                    pass

        # Regular string content
        content_panel = Panel(
            str(content),
            title="[bold green]💬 Content[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        console.print(content_panel)

def pretty_print_response(response, step_num=None):
    """
    Pretty print the agent response using Rich formatting

    Args:
        response: The response object to print
        step_num: Optional step number for streaming responses
    """
    if step_num is not None:
        console.print(f"\n[bold blue]═══ Step {step_num} ═══[/bold blue]")

    console.print(f"[dim]Response type:[/dim] [yellow]{type(response).__name__}[/yellow]")

    if isinstance(response, InsightResponse):
        # Create a tree structure for the response
        tree = Tree(f"[bold green]InsightResponse[/bold green] ({len(response.items)} items)")

        for i, item in enumerate(response.items):
            item_node = tree.add(f"[bold cyan]Item {i+1}[/bold cyan]: {item.type}")

            if item.type == "message":
                # Display full message content with intelligent formatting
                pretty_print_content(item.content)

            elif item.type == "table":
                # Display full table with Rich table formatting
                if item.data:
                    table = Table(title=item.title, show_header=True, header_style="bold magenta")

                    # Add columns
                    columns = list(item.data.keys())
                    for col in columns:
                        table.add_column(col, style="cyan", no_wrap=False)

                    # Add rows
                    row_count = len(next(iter(item.data.values())))
                    for i in range(row_count):
                        row_data = []
                        for col in columns:
                            value = item.data[col][i]
                            # Format numbers nicely
                            if isinstance(value, float):
                                row_data.append(f"{value:.2f}")
                            else:
                                row_data.append(str(value))
                        table.add_row(*row_data)

                    console.print(table)
                else:
                    # Fallback if no data
                    item_node.add(f"[green]Title:[/green] {item.title}")
                    item_node.add("[red]No data available[/red]")

            elif item.type == "chart":
                # Display chart info and data
                chart_panel = Panel(
                    f"[bold yellow]Chart Type:[/bold yellow] {item.chart_type}\n\n" +
                    f"[bold yellow]Data Preview:[/bold yellow]\n" +
                    (json.dumps(item.data, indent=2, default=str) if item.data else "No data available"),
                    title=f"[bold blue]📊 {item.title}[/bold blue]",
                    border_style="blue",
                    padding=(1, 2)
                )
                console.print(chart_panel)

        console.print(tree)

    elif hasattr(response, 'content'):
        # Handle other response types with content using intelligent formatting
        console.print(f"\n[bold cyan]📄 Response Content:[/bold cyan]")
        pretty_print_content(response.content)

    else:
        # Fallback for unknown response types - show full content
        try:
            content = json.dumps(response, indent=2, default=str)

            panel = Panel(
                content,
                title="[bold yellow]Raw Response[/bold yellow]",
                border_style="red"
            )
            console.print(panel)
        except:
            console.print(f"[red]Unable to serialize response: {response}[/red]")

def pretty_print_message(message_content):
    """
    Convenience function to pretty print any message content

    Args:
        message_content: The message content to display (string, list, dict, etc.)

    Example usage:
        pretty_print_message("content=[{'text': 'Hello!', 'type': 'text'}, {'id': 'tool_123', 'input': {...}}]")
    """
    console.print("[bold magenta]🎨 Pretty Printing Message Content[/bold magenta]")
    console.print("─" * 60)
    pretty_print_content(message_content)
    console.print("─" * 60)

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
def run_query_tool(sql: str):
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
    user_id = 1472007

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
        # rows, cols = execute_with_columns_without_cache(final_sql)
        rows = "[('Who is this lady or gentleman?', 801, 327), ('Remember the wishes for Santa?', 54, 48), ('Who is this handsome redhead?', 43, 37), ('Who is this lady or gentleman? (on the left)', 84, 34), ('Steps to process requests', 45, 33), ('Match principle with their meaning', 34, 28), ('AhaSlides loves this place so much, we went there for company trip TWICE', 30, 28), ('Choose the correct answer?', 27, 26), ('Who is this lady or gentleman? (on the left)\\n', 39, 26), ('Which positions will have candidates joining AhaSlides next month?', 28, 26)]"
        cols =  "RMKeyView(['slide_title', 'total_answers', 'correct_answers'])"
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

        config = {
            "configurable": {
                "thread_id": f"user_{self.user_id}"
            }
        }

        input_message = {
            "role": "user",
            "content": prompt
        }

        try:
            last_message = None
            # Get the final response from the agent
            for step in self.agent_executor.stream(
                {"messages": [input_message]},
                config,
                stream_mode="values"
            ):
                if step["messages"]:
                    print(f"Step message: {step['messages'][-1].content[:100]}")
                    last_message = step["messages"][-1]

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

        config = {
            "configurable": {
                "thread_id": f"user_{self.user_id}"
            }
        }

        input_message = {
            "role": "user",
            "content": prompt
        }

        try:
            for step in self.agent_executor.stream(
                {"messages": [input_message]},
                config,
                stream_mode="values"
            ):
                yield step
        except Exception as e:
            print(f"Error executing agent: {str(e)}")
            yield None


    def invoke(self, prompt: str):
        """
        Invoke the agent with a prompt and return structured response
        """
        config = {
            "configurable": {
                "thread_id": f"user_{self.user_id}"
            }
        }
        input_message = {
            "role": "user",
            "content": prompt
        }
        return self.agent_executor.invoke({"messages": [input_message]}, config)


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
    console.print("[bold magenta]🚀 Starting Structured Agent Test[/bold magenta]")
    console.print("─" * 60)

    agent = StructuredAgent()

    # Test query
    test_prompt = "Give me the top 5 questions with their correct answers"

    # Create a nice header for the test
    header_panel = Panel(
        f"[bold white]{test_prompt}[/bold white]",
        title="[bold green]📊 Test Query[/bold green]",
        border_style="green"
    )
    console.print(header_panel)

    step_count = 0
    # response = agent.invoke(test_prompt)
    # print(response['structured_response'])
    response = agent.query(test_prompt)
    print('\n\nStructured Output')

    json_text = extract_json_from_content(response.content)
    insight_response = InsightResponse(**json_text)
    pretty_print_content(insight_response.items)
    # console.print("\n[bold magenta]✅ Agent test completed![/bold magenta]")
    # console.print("─" * 60)

    # # Test the full content display with your example
    # console.print("\n[bold cyan]🧪 Testing Full Content Display[/bold cyan]")
    # test_message_content = """[{'text': "Hello! I'd be happy to help you analyze the top 5 questions with their accuracy rates from your data warehouse.\\n\\nLet me query the data to find the questions with the highest accuracy rates.", 'type': 'text'}, {'id': 'toolu_016tZsumo166582BsiAoqcGV', 'input': {'sql': "SELECT \\n    slide_title,\\n    COUNT(*) as total_answers,\\n    SUM(CASE WHEN correct = true THEN 1 ELSE 0 END) as correct_answers,\\n    ROUND(SUM(CASE WHEN correct = true THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as accuracy_rate\\nFROM answers\\nWHERE slide_type IN ('Pick Answer', 'Poll')\\nGROUP BY slide_title\\nHAVING COUNT(*) >= 10\\nORDER BY accuracy_rate DESC, total_answers DESC\\nLIMIT 5"}, 'name': 'run_query_tool', 'type': 'tool_use'}]"""

    # pretty_print_message(test_message_content)

    # # Test table response display
    # console.print("\n[bold cyan]🧪 Testing Table Response Display[/bold cyan]")

    # # Create a mock InsightResponse with table data
    # from structured_agent import InsightResponse, TableItem, MessageItem

    # # Sample table data (like what would come from a query result)
    # table_response = InsightResponse(
    #     items=[
    #         MessageItem(
    #             type="message",
    #             content="Here are the top 5 questions with their accuracy rates:"
    #         ),
    #         TableItem(
    #             type="table",
    #             title="Top 5 Questions by Accuracy Rate",
    #             data={
    #                 "slide_title": [
    #                     "Who is this lady or gentleman?",
    #                     "Remember the wishes for Santa?",
    #                     "Who is this handsome redhead?",
    #                     "Steps to process requests",
    #                     "Match principle with their meaning"
    #                 ],
    #                 "total_answers": [801, 54, 43, 45, 34],
    #                 "correct_answers": [327, 48, 37, 33, 28],
    #                 "accuracy_rate": [40.82, 88.89, 86.05, 73.33, 82.35]
    #             }
    #         )
    #     ]
    # )

    # pretty_print_response(table_response)

    # # Test chart response display
    # console.print("\n[bold cyan]🧪 Testing Chart Response Display[/bold cyan]")

    # from structured_agent import ChartItem

    # # Sample chart data
    # chart_response = InsightResponse(
    #     items=[
    #         MessageItem(
    #             type="message",
    #             content="Here's a visualization of the accuracy rates:"
    #         ),
    #         ChartItem(
    #             type="chart",
    #             title="Question Accuracy Rates",
    #             chart_type="bar",
    #             data={
    #                 "questions": [
    #                     "Who is this lady?",
    #                     "Remember Santa?",
    #                     "Handsome redhead?",
    #                     "Process requests",
    #                     "Match principles"
    #                 ],
    #                 "accuracy": [40.82, 88.89, 86.05, 73.33, 82.35]
    #             }
    #         )
    #     ]
    # )

    # pretty_print_response(chart_response)


