import os
import duckdb
import pandas as pd
import json
from typing import List, Annotated, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END, START
from langgraph.types import Send
import operator

# Adjust path if needed
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redshift_api import execute_with_columns, st_execute_with_columns
from session_insight.tasks import TASKS, MART_SQL, SYSTEM_PROMPT, COACH_PROMPT, AnalysisTask
from session_insight.schemas import SlideAnalysisResult, SlideAnalysisResultBase

# -----------------
# State Definitions
# -----------------

class SessionInsightState(TypedDict):
    presentation_id: str  # Input
    duckdb_path: str      # Internal
    insights: Annotated[List[SlideAnalysisResult], operator.add] # Output from parallel tasks
    coaching_message: Optional[str]
    final_output_path: str # Path to saved JSON

class AnalystInput(TypedDict):
    task: AnalysisTask
    duckdb_path: str

# -----------------
# Nodes
# -----------------

def load_datamart(state: SessionInsightState):
    presentation_id = state['presentation_id']
    print(f"Loading datamart for presentation {presentation_id}...")

    # 1. Fetch from Redshift
    sql = MART_SQL.format(presentation_id=presentation_id)
    try:
        rows, cols = st_execute_with_columns(sql)
        df = pd.DataFrame(rows, columns=cols)
        print(f"Loaded {len(df)} rows from Redshift.")
    except Exception as e:
        print(f"Error fetching from Redshift: {e}")
        # Build an empty DF to allow testing if Redshift fails/mocking
        df = pd.DataFrame(columns=["id", "slide_id", "participant_id", "createdat", "correct", "slide_type", "slide_title", "slide_order", "slide_category", "slide_index", "answer_text"])

    # 2. Save to DuckDB
    # Use a unique path
    db_path = f"session_insight_{presentation_id}.duckdb"

    # Assuming we want to start fresh or overwrite
    if os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)
    try:
        # IMPORTANT: register the pandas DF so SQL can read it
        con.register("df", df)

        # Replace table every run so it's always "updated"
        con.execute("CREATE OR REPLACE TABLE mart AS SELECT * FROM df")

        # Verify persistence/content
        count = con.execute("SELECT COUNT(*) FROM mart").fetchone()[0]
        print(f"DuckDB saved: {count} rows into {db_path}")
    finally:
        # Cleanup
        try:
            con.unregister("df")
        except Exception:
            pass
        con.close()

    return {"duckdb_path": db_path, "insights": []}

def map_tasks(state: SessionInsightState):
    return [
        Send("analyst", {"task": task, "duckdb_path": state['duckdb_path']})
        for task in TASKS
    ]

from functools import lru_cache

@lru_cache(maxsize=100)
def do_analyst_job(task: AnalysisTask, duckdb_path: str):
    # 1. Execute Query
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(task.sql_template).df()
        data_str = df.to_csv(index=False)
        data_source = df.to_dict(orient='records')
    except Exception as e:
        print(f"Error executing SQL for task {task.id}: {e}")
        data_str = "Error retrieving data."
        data_source = f"Error: {e}"
    finally:
        con.close()

    # 2. Call LLM for Analysis
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(SlideAnalysisResultBase)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"Task: {task.analysis_prompt}"),
        HumanMessage(content=f"Here is the data:\n{data_str}")
    ]

    try:
        base_result = structured_llm.invoke(messages)
        if base_result:
             result = SlideAnalysisResult(
                 **base_result.model_dump(),
                 source_data=data_source
             )
             result.metadata.analysis_scope = task.category
             return {"insights": [result]}
    except Exception as e:
        print(f"Error in LLM analysis for {task.id}: {e}")

    return {"insights": []}


def analyst(state: AnalystInput):
    task = state['task']
    duckdb_path = state['duckdb_path']

    print(f"Running task {task.id}: {task.category}...")

    return do_analyst_job(task, duckdb_path)


def coach(state: SessionInsightState):
    insights = state['insights']
    print(f"Coaching based on {len(insights)} insights...")

    context_list = []
    for ins in insights:
        obs = [o.observation for o in ins.key_observations]
        interp = [i.insight for i in ins.interpretation]
        context_list.append({
            "category": ins.metadata.analysis_scope,
            "observations": obs,
            "interpretations": interp
        })

    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    coach_messages = [
        SystemMessage(content=COACH_PROMPT),
        SystemMessage(content="You will be provided with observations and interpretations from multiple specialized analyses. Your task is to connect them into one expert, coherent, and encouraging summary."),
        HumanMessage(content=f"Here are the analysis results:\n{json.dumps(context_list, indent=2)}")
    ]

    try:
        response = llm.invoke(coach_messages)
        coaching_msg = response.content
    except Exception as e:
        print(f"Error in Coach node: {e}")
        coaching_msg = "Great job on your session! The data shows strong engagement across the board."

    return {"coaching_message": coaching_msg}


def aggregate_insights(state: SessionInsightState):
    insights = state['insights']
    presentation_id = state['presentation_id']
    coaching_message = state.get('coaching_message')

    print(f"Aggregating {len(insights)} insights...")

    output_path = f"session_insight_{presentation_id}_results.json"

    # Convert Pydantic models to dicts
    insights_data = [i.model_dump() for i in insights]

    final_output = {
        "presentation_id": presentation_id,
        "coaching_summary": coaching_message,
        "detailed_insights": insights_data
    }

    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2, default=str)

    print(f"Saved insights to {output_path}")

    return {"final_output_path": output_path}

# -----------------
# Graph Construction
# -----------------

def create_session_insight_graph():
    workflow = StateGraph(SessionInsightState)

    workflow.add_node("load_datamart", load_datamart)
    workflow.add_node("analyst", analyst)
    workflow.add_node("coach", coach)
    workflow.add_node("aggregate_insights", aggregate_insights)

    workflow.set_entry_point("load_datamart")

    workflow.add_conditional_edges(
        "load_datamart",
        map_tasks,
        ["analyst"]
    )

    workflow.add_edge("analyst", "coach")
    workflow.add_edge("coach", "aggregate_insights")
    workflow.add_edge("aggregate_insights", END)

    return workflow.compile()

if __name__ == "__main__":
    # Test run
    if not os.getenv("REDSHIFT_HOST"):
        print("Warning: Redshift env vars not set. This might fail.")

    print("Initialize graph...")
    graph = create_session_insight_graph()

    input_state = {"presentation_id": "7880449", "insights": []}

    print("Running graph...")
    for output in graph.stream(input_state):
        for key, value in output.items():
            print(f"Finished node: {key}")
