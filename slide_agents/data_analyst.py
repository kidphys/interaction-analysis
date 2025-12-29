"""
This module forms the base for the data analyst role.
It is responsible for analyzing the data and providing insights about it.
Use case:
- Support data scientist to answer questions about the data
- Support slide designer to leverage insights from past sessions
"""

from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, TypedDict
import operator
import duckdb
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from data_analysis_graph import get_table_name_from_csv_path
from slide_agents.query_node import analyze_data, create_sql_query, get_table_schemas, query_db


class AnalysisState(TypedDict, total=False):
    # name of this run, to store data
    name: str

    # list of questions to answer
    questions: List[Dict[str, Any]]

    # task used by worker node
    task: Dict[str, Any]

    # Parallel worker results (list merge)
    results: Annotated[List[Dict[str, Any]], operator.add]

    # A list of data to load into the graph
    csv_paths: List[str]

    # Duckdb file
    duckdb_file: str


models = [
  'gpt-4o-mini',
  'gpt-4.1-nano',
  'gpt-4.1-mini',
  'claude-haiku-4-5-20251001',
  'anthropic:claude-sonnet-4-20250514',
  'gemini-2.5-flash-lite',
]

def map_tasks_node(state: AnalysisState) -> AnalysisState:
    filename = state["name"] + ".duckdb"
    conn = duckdb.connect(filename)

    for csv_file in state["csv_paths"]:
        table_name = get_table_name_from_csv_path(csv_file)
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT * FROM read_csv_auto('{csv_file}')
        """)
        print(f"persisted table: {table_name} from {csv_file}")

    conn.close()
    state["duckdb_file"] = filename
    return state


def fanout_to_worker(state: AnalysisState):
    """
    Return a list of Send() instructions — one per sub-task.
    LangGraph runs all of them IN PARALLEL.
    """
    send_list = []
    for question in state.get("questions", []):
        print("[fanout] scheduling:", question)
        send_list.append(
            Send(
                "query_node",
                {
                    "task": {
                        "question": question,
                    },
                    "results": [],   # local init
                    "duckdb_file": state["duckdb_file"]
                }
            )
        )
    return send_list


def query_node(state: AnalysisState) -> Dict[str, Any]:
    conn = duckdb.connect(state['duckdb_file'])
    table_schemas = get_table_schemas(conn)
    task = state['task']
    question = task['question']
    sql = create_sql_query(question, table_schemas, model='anthropic:claude-sonnet-4-20250514')
    data = query_db(sql, conn).to_dict(orient='list')
    analysis = analyze_data(question, str(data), model='llama-3.3-70b-versatile', model_provider='groq')
    return {
      'results': [
        {
          'question': question,
          'sql': sql,
          'data': str(data),
          'analysis': analysis
        }
      ]
    }


import json
def persist_analysis_node(state: AnalysisState) -> AnalysisState:
    """
    Persist the `AnalysisState` to a file so that we can review the analysis later
    """
    filename = state['name'] + '-analysis-' + '.json'
    import pdb; pdb.set_trace()
    with open(filename, 'w') as f:
      json.dump(state, f, indent=2)
    return state


"""
Init a graph that first create a temp duckdb from the csv input file
Then span the tasks to multiple query node to get insight from the data
Finally, aggregate the insights from the query nodes to get the final answer
"""
def create_graph():
  g = StateGraph(AnalysisState)
  g.add_node('map_tasks_node', map_tasks_node)
  g.add_node("query_node", query_node)                 # builds + runs SQL
  g.add_node('persist_analysis_node', persist_analysis_node)
  g.add_conditional_edges("map_tasks_node", fanout_to_worker, ["query_node"])
  g.add_edge("query_node", "persist_analysis_node")
  g.add_edge(START, "map_tasks_node")
  g.add_edge("persist_analysis_node", END)
  return g.compile()


if __name__ == "__main__":
    # Test out the graph in cli

    csv_paths = [
        'answer_stats_user_ids.csv',
    ]
    sample_queries_2 = [
    "What are the top 20 most frequently appearing presentation titles, and how many times has each been delivered?",
    "What are the most common slide topics or themes across all presentations (identify by slide_title and slide_description patterns)?",
    "Which presentations have been delivered multiple times to similar audiences? Look for repeated presentation_titles across different delivery dates.",
    # "What is the distribution of slide types across all presentations? Which formats dominate (e.g., text, interactive, visual)?",
    # "Which slides or topics show the lowest engagement (answer_percentage)? What are their titles and descriptions?",
    # "Are there presentations that have high participant counts but low answer engagement? What topics do these cover?"
    ]
    questions = sample_queries_2
    state = {
        'name': 'answers_stats',
        'csv_paths': csv_paths,
        'questions': questions
    }
    g = create_graph()
    res = g.invoke(state)
    print(res)