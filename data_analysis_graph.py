"""
analysis_agent_parallel.py

Your original file, modified to:
- Remove router recursion loop
- Run all sub-tasks IN PARALLEL using LangGraph Send()
- Keep your planner/query_builder/executor/aggregator logic
- Maintain your DB + debugging output
"""

from __future__ import annotations

import json
import operator
from re import T
from typing import Any, Dict, List, Optional, TypedDict, Annotated

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langchain_core.messages import HumanMessage

import pandas as pd
import pyarrow as pa
import duckdb

from structured_agent import StructuredAgent


# =========================
# 1. STATE DEFINITION
# =========================

class AnalysisState(TypedDict, total=False):
    question: str

    # planner output
    sub_tasks: List[Dict[str, Any]]

    # task used by worker node
    task: Dict[str, Any]

    # Parallel worker results (list merge)
    results: Annotated[List[Dict[str, Any]], operator.add]

    current_csv_path: str

    # final output
    final_answer: Optional[str]


# =========================
# 2. LLM
# =========================

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    temperature=0,
    max_tokens=1024,
)


def safe_parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except:
        start = text.find("[")
        if start == -1:
            start = text.find("{")
        end = max(text.rfind("]"), text.rfind("}"))
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise ValueError(f"Cannot parse JSON:\n{text}")


# =========================
# 3. DB LAYER
# =========================

def run_query(sql: str, conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    res = conn.execute(sql).fetchdf()
    return {
        "columns": list(res.columns),
        "head": res.head(10).to_dict(orient="records"),
        "shape": list(res.shape),
    }


# =========================
# 4. NODES
# =========================

def entry_node(state: AnalysisState) -> AnalysisState:
    state.setdefault("sub_tasks", [])
    state.setdefault("results", [])
    return state


def planner_node(state: AnalysisState) -> AnalysisState:
    question = state["question"]

    prompt = f"""
You are a data analysis planner.

User's question:
{question}

Break the question into 2–6 sub-tasks.
Return ONLY JSON list:
[
  {{ "id": "task_1", "description": "..." }},
  ...
]
"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    sub_tasks = safe_parse_json(resp.content)

    state["sub_tasks"] = sub_tasks
    return state


# === FAN OUT NODE — replaces router loop ===

def map_tasks_node(state: AnalysisState) -> AnalysisState:
    """
    Just prints and returns state.
    The actual fan-out is in fanout() below.
    """
    print("\n=== NODE: map_tasks ===")
    print("Sub tasks:", state["sub_tasks"])
    return state


def fanout_to_worker(state: AnalysisState):
    """
    Return a list of Send() instructions — one per sub-task.
    LangGraph runs all of them IN PARALLEL.
    """
    send_list = []
    for task in state.get("sub_tasks", []):
        print("[fanout] scheduling:", task["id"])
        send_list.append(
            Send(
                "worker",
                {
                    "question": state["question"],
                    "task": task,
                    "results": [],   # local init
                    "current_csv_path": state["current_csv_path"]
                }
            )
        )
    return send_list


# === WORKER NODE: query_builder + executor combined ===


def get_schema_info(df: pd.DataFrame) -> str:
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype('string')
        elif 'time' in col:
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception as e:
                df['col'] = df[col].astype('string')

    con = duckdb.connect(":memory:")
    con.register("user_table", pa.Table.from_pandas(df))
    res = con.execute("DESCRIBE user_table;").fetchdf()
    res = res[["column_name", "column_type"]]
    return str(res)

def worker_node(state: AnalysisState) -> Dict[str, Any]:
    """
    Worker for ONE sub-task (runs in parallel across tasks).

    Does BOTH:
    - Generate SQL for this one task (DuckDB-safe prompt)
    - Execute SQL with 1 retry if DuckDB errors
    Returns: {"results": [ {task_id, sql, summary} ]}
    """
    task = state["task"]
    desc = task["description"]
    current_csv_path = state["current_csv_path"]
    df = pd.read_csv(current_csv_path)

    conn = duckdb.connect(":memory:")
    table_name = current_csv_path.split('/')[-1].replace('.csv', '')
    conn.register(table_name, pa.Table.from_pandas(df))

    schema_info = get_schema_info(df)
    print("\n=== NODE: worker ===")
    print("Running:", task["id"], "-", desc)

    # ---------- 1) Build initial SQL ----------
    prompt = f"""
You are a precise DuckDB SQL generator.
Your ONLY job is to output a single valid DuckDB SQL query.

You MUST follow these rules:

## 🎯 Goal
Generate SQL that retrieves the data needed to answer the following analytical task:
{desc}

## Schema information
Use exactly the columns below. Do NOT invent or query any other tables.
Table name: {table_name}
Schema:
{schema_info}

You MUST:
- Use ONLY the tables and columns appearing in the schema above.
- Reject and avoid any column or table that is not present in the schema.

## Important DuckDB rules
- DuckDB does NOT allow aggregate functions around window functions.
  Example of INVALID:
      SELECT AVG(LAG(x) OVER (...)) FROM ...
- If both window functions AND aggregates are needed:
  1. Compute window functions in a CTE
  2. Then aggregate from the CTE
- Use CTEs liberally to keep logic readable and avoid nested window expressions.


## ⚠️ Required Safety Constraints
- NEVER use backticks or double quotes around identifiers (DuckDB recommended style).
- ALWAYS wrap literal text values with single quotes.
- For date comparisons, explicitly CAST if needed.
- Use COALESCE for nullable columns where appropriate to avoid NULL propagation.
- For joins, ALWAYS specify explicit join conditions.

## 🔒 Output Format (MANDATORY)
Output **ONLY a SQL query**, no explanation, no markdown, no prose.
Do NOT wrap in ```sql```.

Example of correct output:
SELECT ...

Example of incorrect outputs:
- "Here is the SQL: SELECT ..."
- ```sql SELECT ...```
- Any natural language commentary

Begin now.
"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    sql = resp.content.strip()
    print("[worker] Initial SQL:\n", sql)

    # ---------- 2) Execute with one retry on DuckDB error ----------
    summary: Dict[str, Any] = {}
    last_error_text: Optional[str] = None

    try:
        for attempt in range(2):  # attempt 0 = original, 1 = corrected
            try:
                summary = run_query(sql, conn)
                last_error_text = None
                break
            except Exception as e:
                last_error_text = str(e)
                print(f"[worker] Error executing SQL on attempt {attempt+1} for {task['id']}: {last_error_text}")

                if attempt == 1:
                    # Give up after one fix attempt – record error in summary
                    summary = {
                        "error": last_error_text,
                        "sql": sql,
                    }
                    break

                sql = get_fixed_sql(sql, desc, last_error_text)
    finally:
        conn.close()
    # ---------- 3) Return mergeable result ----------
    return {
        "results": [
            {
                "task_id": task["id"],
                "description": desc,
                "sql": sql,
                "summary": summary,
            }
        ]
    }


def get_fixed_sql(sql: str, task_description: str, error: str) -> str:
            # Ask LLM to fix SQL given DuckDB error
    fix_prompt = f"""
You previously wrote this SQL for DuckDB:

{sql}

When executing it, DuckDB returned this error:

{error}

Rewrite the SQL to correctly answer this sub-task:

{task_description}

Remember:
- DuckDB does NOT allow aggregate functions whose arguments contain window functions.
  Use a subquery: compute window values first, then aggregate in an outer query.
- Use ONLY the reaction_stats table.
- Do NOT add explanations or comments.
- Do NOT add backticks.
Return only the corrected SQL.
"""
    resp = llm.invoke([HumanMessage(content=fix_prompt)])
    sql = resp.content.strip()
    print("[worker] Corrected SQL:\n", sql)
    return sql


# === AGGREGATOR ===

from langchain_core.prompts import PromptTemplate

senior_data_analyst_prompt = PromptTemplate.from_template("""
You are a **helpful senior data analyst** that provides **concise, structured insights** about the data.
You will be given the user question, all sub-task results from a pool of workers which query the data to answer the task question and then give your final analysis in the correct format.


## User question
{question}

## All task results
{context}

---
## 🔑 Guidelines
- Be **concise**: avoid long explanations (token limits)
- Prioritize **key insights** over verbose analysis
- Always provide **actionable takeaways**
- Keep data visualizations and tables **focused on what supports the insight**
---

## ⚡ Response Format
It is critical that your final response must contain an `items` list. Each item can be one of:

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
     {{column_name: [list_of_values]}}
     ```

3. **chart** – for visualizing data
   - Always include a **descriptive title**
   - Only **2 columns allowed**:
     - 1st column → x-axis
     - 2nd column → y-axis
   - Supported types: `bar`, `line`, `area`, `pie`, etc.
   - Use creativity to pick the best visualization for the insight

"""
)
def insight_aggregator_node(state: AnalysisState) -> AnalysisState:
    return "OK"

def insight_aggregator_node(state: AnalysisState) -> AnalysisState:
    results = state.get("results", [])

    print("\n=== NODE: aggregator ===")
    print("Collected results:", len(results))

    def try_dump(obj):
        try:
            return json.dumps(obj, indent=2)
        except:
            return str(obj)

    context = "\n\n".join(
        f"Task {r['task_id']}:\n{r['description']}\nSQL:\n{r['sql']}\nSummary:\n{try_dump(r['summary'])}"
        for r in results
    )

    state['context'] = context
    return state


# =========================
# 5. BUILD PARALLEL GRAPH
# =========================

def build_graph():
    g = StateGraph(AnalysisState)

    g.add_node("entry", entry_node)
    g.add_node("planner", planner_node)
    g.add_node("map_tasks", map_tasks_node)
    g.add_node("worker", worker_node)
    g.add_node("aggregator", insight_aggregator_node)

    g.set_entry_point("entry")

    g.add_edge("entry", "planner")
    g.add_edge("planner", "map_tasks")
    g.add_edge("worker", "aggregator")
    g.add_edge("aggregator", END)

    # Fan-out from map_tasks
    g.add_conditional_edges(
        "map_tasks",
        fanout_to_worker,
        ["worker"],
    )

    return g.compile()


def build_parallel_only_graph():
    """
    Build a graph that:
    - Assumes `sub_tasks` is already in the state (provided by the ReAct agent)
    - Fans out each task to a parallel `worker` node via Send()
    - Aggregates all worker results in `insight_aggregator_node`
    - Does NOT contain any planner / LLM for insight generation

    Expected initial state:
    {
        "question": "<original user question>",   # optional but useful for logs
        "sub_tasks": [                            # required
            {"id": "task_1", "description": "..."},
            {"id": "task_2", "description": "..."},
            ...
        ],
        "results": [],                            # will be filled by workers
    }
    """
    g = StateGraph(AnalysisState)

    # Reuse your existing nodes
    g.add_node("map_tasks", map_tasks_node)           # just logs sub_tasks
    g.add_node("worker", worker_node)                 # builds + runs SQL
    g.add_node("aggregator", insight_aggregator_node) # data-only aggregator

    # Entry: we start from map_tasks, since planner is now done by ReAct agent
    g.set_entry_point("map_tasks")

    # Workers feed into aggregator, aggregator then ends
    g.add_edge("worker", "aggregator")
    g.add_edge("aggregator", END)

    # Fan-out: for each sub_task, Send() to `worker` in parallel
    g.add_conditional_edges(
        "map_tasks",
        fanout_to_worker,  # returns [Send("worker", {...}), ...]
        ["worker"],
    )

    return g.compile()


def print_step(step):
    print("\n=== EVENT ===")
    if 'aggregator' in step.keys():
        for result in step['aggregator']['results']:
            print(f'task_id: {result["task_id"]}: {result["description"]}\n')
            print(f'sql: {result["sql"]}\n')
            df = pd.DataFrame(columns=result['summary']['columns'], data=result['summary']['head'])
            print(df.to_csv(sep='\t', index=False))
        print(step['aggregator']['final_answer'])
    else:
        # print(json.dumps(step, indent=2))
        print(step)
    print('-' * 100)


# =========================
# 6. CLI
# =========================

if __name__ == "__main__":
    # app = build_graph()
    sub_tasks = ['Analyze database schema including table names, column names, data types, and table relationships', 'Get data summary statistics including record counts, data ranges, and sample data from each table']
    sub_tasks = [{"id": f"task_{i}", "description": task} for i, task in enumerate(sub_tasks)]
    init_state = {'question': 'Describe the database structure and data contents', 'sub_tasks': sub_tasks, 'results': [], 'current_csv_path': '/var/folders/b3/hrj2lh1d06n_0ldwgv0m27xh0000gn/T/cheryl_answers.csv'}
    # q = input("Enter your analytics question:\n> ").strip()
    # init_state = {"question": q}
    app = build_parallel_only_graph()
    res = app.invoke(init_state)
    print(res)
