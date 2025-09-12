# Import relevant functionality
from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from redshift_api import execute
from tool_redshift import run_query


@tool
def run_query_tool(sql):
    """
    Run a query on the Redshift data warehouse given the following table:
    `aha_report_v5`.`fact_answers`
        user_id (varchar)
        slide_id (varchar)
        question_id (varchar)
        participant_id (varchar)
        presentation_id (varchar)
        slide_type (varchar): can be 'Pick Answer', 'Poll', 'Open Ended'
        submitted_answer_text (varchar): the answer that this participant submitted
        correct (boolean)
        createdat (timestamp)
    """
    rows = execute(sql)
    return str(rows)


def main():
    # Create the agent
    memory = MemorySaver()
    model = init_chat_model("openai:gpt-4o-mini")
    tools = [run_query_tool]
    agent_executor = create_react_agent(model, tools, checkpointer=memory)

    # Use the agent
    config = {"configurable": {"thread_id": "abc123"}}

    input_message = {
        "role": "user",
        "content": "Give me the top 10 questions with its accuracy rate (number of participant who got it right / total participant answered) for user_id = 1472007. The return format should be in JSON records, with col: question_id, accuracy, participant who got it right, total participants"
    }
    for step in agent_executor.stream(
        {"messages": [input_message]}, config, stream_mode="values"
    ):
        step["messages"][-1].pretty_print()
        last_message = step["messages"][-1]

    return last_message

if __name__ == "__main__":
    last_message = main()
    print('--------------------------------')
    print(last_message)