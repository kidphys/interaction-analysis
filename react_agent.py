# Import relevant functionality
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.tools import InjectedToolArg
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from redshift_api import execute_with_columns
from typing_extensions import Annotated


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
        slide_type (varchar): can be 'Pick Answer', 'Poll', 'Open Ended'
        slide_title (varchar): the title of the question asked in the slide
        submitted_answer_text (varchar): the answer that this participant submitted
        correct (boolean)
        createdat (timestamp)
    """
    user_id = config['metadata']['user_id']
    final_sql = f"""
   WITH answers AS (
    SELECT
        fa.user_id,
        fa.slide_id,
        fa.question_id,
        fa.participant_id,
        fa.master_presentation_id,
        fa.slide_type,
        dq.slide_title,
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
    print(f'final_sql: {final_sql}')
    rows, cols = execute_with_columns(final_sql)

    message = f"The result of the query is: {rows} {cols}"
    print(f'message: {message}')
    return str({
        'rows': str(rows),
        'cols': str(cols)
    })

system_prompt = """
You are a helpful assistant that can answer questions about the data warehouse.
Alwasy say: `Hola` before response.
The response should be in JSON format with fields:
1. cols: the columns of the data result
2. rows: the rows of the data result
3. message: your own assessment/recommendation based on the data
"""
sys_message = SystemMessage(content=system_prompt)

def main():
    # Create the agent
    memory = MemorySaver()
    model = init_chat_model("openai:gpt-4o-mini")
    tools = [run_query_tool]

    # Use the agent
    user_id = '1472007'
    config = {"configurable": {"thread_id": "abc123", "user_id": user_id}}

    agent_executor = create_react_agent(model, tools, checkpointer=memory, prompt=sys_message)
    input_message = {
        "role": "user",
        "content": "Give me the top 10 questions with its accuracy rates, inspect its title and give me your recommendation"
    }
    for step in agent_executor.stream(
        {"messages": [input_message]}, config, stream_mode="values"
    ):
        step["messages"][-1].pretty_print()
        last_message = step["messages"][-1]

    return last_message


def temp():
    return run_query_tool.get_input_schema().model_json_schema()

if __name__ == "__main__":
    # last_message = temp()
    last_message = main()
    print('--------------------------------')
    print(last_message)