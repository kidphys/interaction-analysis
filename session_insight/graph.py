import os
import duckdb
import pandas as pd
import json
from typing import List, Annotated, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END, START
from langgraph.types import Send
import operator

# Adjust path if needed
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redshift_api import execute_with_columns
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

# -----------------
# Nodes
# -----------------

class CoachingResult(TypedDict):
    message: str

def load_datamart(state: SessionInsightState):
    presentation_id = state['presentation_id']
    print(f"Loading datamart for presentation {presentation_id}...")

    # 1. Fetch from Redshift
    sql = MART_SQL.format(presentation_id=presentation_id)
    try:
        rows, cols = execute_with_columns(sql)
        df = pd.DataFrame(rows, columns=cols)
        print(f"Loaded {len(df)} rows from Redshift.")
    except Exception as e:
        print(f"Error fetching from Redshift: {e}")
        # Build an empty DF to allow testing if Redshift fails/mocking
        df = pd.DataFrame(columns=["id", "slide_id", "participant_id", "createdat", "correct", "slide_type", "slide_title", "slide_order", "slide_index", "answer_text"])

    # 2. Save to DuckDB
    # Use a unique path
    db_path = f"session_insight_{presentation_id}.duckdb"

    # Assuming we want to start fresh or overwrite
    if os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE mart AS SELECT * FROM df")
    con.close()

    return {"duckdb_path": db_path, "insights": []}

def map_tasks(state: SessionInsightState):
    # Returns a list of Send objects to fan out to 'analyst' node
    sends = [
        Send("analyst", {"task": task, "duckdb_path": state['duckdb_path']})
        for task in TASKS
    ]
    # To run Coach in parallel, it cannot depend on 'analyst' outputs yet.
    # But Coach NEEDS insights from analysts.
    # "Run coach node in parallel with analyst (1 analyst 1 coach)" implies
    # each analyst might have a coach or coach runs while analysts run.
    # However, Coach aggregates ALL insights. It CANNOT run in parallel with analysts if it needs their output.
    # Unless the user means "Run A coach for EACH analyst"? "1 analyst 1 coach"?
    # "1 analyst 1 coach" sounds like 1-to-1 mapping.
    # But usually Coach summarizes everything.
    # If the user means "Make the coach node run in parallel with analyst",
    # and "1 analyst 1 coach", maybe they mean each analyst task also produces a coaching message?
    # Or maybe they mean "run the single aggregation coach in parallel with analysts" (impossible if dependency exists).

    # Let's re-read: "Make the coach node run in parallel with analyst (1 analyst 1 coach)"
    # This likely means: For EACH analyst task, also run a coach task (or combined).
    # But if Coach summarizes EVERYTHING, it must be after.
    # If "1 analyst 1 coach", it implies fan-out to Coach as well?
    # Or maybe the user wants: `load` -> `map` -> [`analyst_1`, `coach_1`], [`analyst_2`, `coach_2`], ...
    # i.e., Coach is per-task?
    # "recommendation is too vague... give revised version of Slide 9".
    # This implies the Coach helps with specific slide recommendations.
    # So "Coach" here might be a "Revision Specialist" for that specific task?
    # If so, we can chain Analyst -> Coach per task.
    # Structure: `load` -> map -> `analyst` -> `coach` -> `aggregate`.
    # This would mean for each task, we analyze THEN coach (refine).
    # THIS makes "1 analyst 1 coach" sense.

    # So we change the edge: `map` -> `analyst`.
    # `analyst` -> `coach` (linear chain per branch).
    # `coach` -> `aggregate`.

    # But previously `coach` was an aggregator.
    # Now `coach` transforms the `SlideAnalysisResult`?
    # Or adds `coaching_message` to it?
    # The user also complains about recommendations being vague.

    # Hypothesis: The user wants a per-task Coach that refines the Analyst's output.
    # Let's assume this.

    return [
        Send("analyze_and_refine", {"task": task, "duckdb_path": state['duckdb_path']})
        for task in TASKS
    ]

def analyze_and_refine(state: AnalystInput):
    task = state['task']
    duckdb_path = state['duckdb_path']

    print(f"Running task {task.id}: {task.category}...")

    # 1. Execute Query
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(task.sql_template).df()
        df.to_csv(f'session_insight_{task.id}.csv', index=False)
        data_str = df.to_csv(index=False)
        data_source = df.to_dict(orient='records')
    except Exception as e:
        print(f"Error executing SQL for task {task.id}: {e}")
        data_str = "Error retrieving data."
        data_source = f"Error: {e}"
    finally:
        con.close()

    # 2. Call LLM
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
             # Convert to full model with source_data
             result = SlideAnalysisResult(
                 **base_result.model_dump(),
                 source_data=data_source
             )
        else:
            return {"insights": []}

    except Exception as e:
        print(f"Error in LLM analysis for {task.id}: {e}")
        return {"insights": []}

    return {"insights": [result]}


# We need to pass the result from Analyst to Coach.
# Standard LangGraph: Nodes receive State.
# If we chain `analyst` -> `coach` inside a branch, we need a state that carries the intermediate result.
# Analyst returns `{"insights": [result]}` which merges to global state.
# But inside the branch, `analyst` Output is not automatically passed as Input to `coach` unless `coach` is part of the `Send` or strict sequence.
# BUT `Send` targets a single Node.
# If we want a sequence `analyst` -> `coach`, we can typically define a subgraph or change `analyst` to call `coach`?
# OR we use `map_tasks` to send to a "worker_graph" (subgraph) which contains A -> C.
# OR we make `analyst` return a distinct key/type that `coach` picks up?
# But `insights` is a reducer.

# Simpler approach:
# Modify `analyst` to NOT return to global `insights` immediately?
# Or keep `analyst` behavior, but have `coach` run on the result?
# If we use `Send("analyst", ...)` and add edge `analyst` -> `coach`.
# `coach` will receive the output of `analyst` IF the graph is built that way?
# No, nodes receive the State.
# If `analyst` updates `insights`, then `coach` sees the global list?
# BUT `coach` is running in parallel branches (1 per analyst).
# Each `coach` instance needs to know WHICH insight to process.
# This implies we need to pass the specific task/insight context.

# Let's define a SubState or Intermediate dict.
# Actually, if we use `Send`, we can pass arbitrary state to the target node.
# But `analyst` is already running.
# If `analyst` finishes, we want `coach` to run on THAT SPECIFIC result.
# So `analyst` should probably just call the LLM for coaching too?
# Merging them into one node `analyst_and_coach`?
# That violates "1 analyst 1 coach" (implies separation) but achieves the goal perfectly.
# "Node" concept.
# If we keep them specific nodes:
# `analyst` -> returns `{"task": ..., "partial_result": ...}` -> `coach` -> returns `{"insights": ...}`.
# This requires `analyst` to NOT return to `insights` reducer directly.
# And we need a state definition that handles the flow.

# Let's try merging for simplicity first?
# "Make the coach node run in parallel with analyst (1 analyst 1 coach)"
# This phrasing suggests distinct nodes. "1 analyst 1 coach" sounds like pairs.

# Let's use `analyst` returning a temporary state that `coach` consumes.
# But `Send` is from `map_tasks`.
# Edge `analyst` -> `coach`.
# `coach` needs to accept `AnalystInput` + `result`.
# Let's define `CoachInput`.

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(SlideAnalysisResultBase)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"Task: {task.analysis_prompt}"),
        HumanMessage(content=f"Here is the data:\n{data_str}")
    ]

    try:
        draft_result = structured_llm.invoke(messages)
    except Exception as e:
        print(f"Error in Analyst {task.id}: {e}")
        return {"insights": []}

    if not draft_result:
        return {"insights": []}

    # --- Phase 2: Coach (Refinement) ---
    print(f"Coaching (Refining) task {task.id}...")

    # Use a slightly higher temperature for creative improvements
    coach_llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    structured_coach_llm = coach_llm.with_structured_output(SlideAnalysisResultBase)

    refinement_prompt = f"""
    {COACH_PROMPT}

    Review the following analysis draft.
    Improve the recommendations to be VERY specific and concrete.
    If a recommendation suggests changing content (like a question or title), provide the EXACT new wording.
    Examples:
    - Instead of "Critique the question", say "Change question to 'What is the capital of France?'"
    - Instead of "Reorder slides", say "Move Slide 5 to position 2".

    Maintain the JSON structure.
    """

    draft_json = draft_result.model_dump_json()

    coach_messages = [
        SystemMessage(content=refinement_prompt),
        # HumanMessage(content=f"Original Data Context (Summary): {str(data_source)[:500]}..."),
        HumanMessage(content=f"Draft Analysis:\n{draft_json}")
    ]

    try:
        refined_result = structured_coach_llm.invoke(coach_messages)
        final_base = refined_result if refined_result else draft_result
    except Exception as e:
        print(f"Error in Coach Refinement {task.id}: {e}")
        final_base = draft_result

    # Construct final object with source data
    # coaching_message is now part of Base, so it will be carried over from final_base.model_dump()
    result = SlideAnalysisResult(
         **final_base.model_dump(),
         source_data=data_source
    )

    return {"insights": [result]}

def aggregate_insights(state: SessionInsightState):
    insights = state['insights']
    presentation_id = state['presentation_id']

    print(f"Aggregating {len(insights)} insights...")

    output_path = f"session_insight_{presentation_id}_results.json"

    # Convert Pydantic models to dicts
    insights_data = [i.model_dump() for i in insights]

    with open(output_path, "w") as f:
        json.dump(insights_data, f, indent=2, default=str)

    print(f"Saved insights to {output_path}")

    return {"final_output_path": output_path}

# -----------------
# Graph Construction
# -----------------

def create_session_insight_graph():
    workflow = StateGraph(SessionInsightState)

    workflow.add_node("load_datamart", load_datamart)
    workflow.add_node("analyze_and_refine", analyze_and_refine)
    workflow.add_node("aggregate_insights", aggregate_insights)

    workflow.set_entry_point("load_datamart")

    workflow.add_conditional_edges(
        "load_datamart",
        map_tasks,
        ["analyze_and_refine"]
    )

    workflow.add_edge("analyze_and_refine", "aggregate_insights")
    workflow.add_edge("aggregate_insights", END)

    return workflow.compile()

if __name__ == "__main__":
    # Test run
    # Mocking Redshift connection could be hard, so assuming environment is set
    # or we can mock execute_with_columns if needed.

    # Check if we have env vars or we mocked it
    if not os.getenv("REDSHIFT_HOST"):
        print("Warning: Redshift env vars not set. This might fail.")

    print("Initialize graph...")
    graph = create_session_insight_graph()

    # Using a dummy presentation_id for testing structure
    # In real usage, use a valid one
    input_state = {"presentation_id": "7880449", "insights": []}

    print("Running graph...")
    # This invokes the graph.
    # Note: 'analyst' runs in parallel/sequence depending on executor
    for output in graph.stream(input_state):
        for key, value in output.items():
            print(f"Finished node: {key}")
