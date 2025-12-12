"""
This module provides a CSV data analysis agent which can run SQL queries on uploaded
CSV files using DuckDB.
"""
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
import streamlit as st
import json
import pandas as pd
import duckdb
import tempfile
import os
from typing import Optional
from langchain.tools import tool
from langgraph.graph.state import RunnableConfig
from data_analysis_graph import build_graph, build_parallel_only_graph
from react_agent_dashboard import display_structured_response, st_process_user_prompt
from structured_agent import (
    StructuredAgent,
    InsightResponse,
    MessageItem,
    TableItem,
    ChartItem,
    pre_model_hook,
    system_prompt
)


# Global variable to store the current CSV data path
_current_csv_path = None


@tool
def run_duckdb_query_tool(sql: str, config: RunnableConfig):
    """
    Run a SQL query on the uploaded CSV data using DuckDB.
    The CSV data is available as a table named 'data'.

    Available columns and data types depend on the uploaded CSV file.
    Use standard SQL syntax for querying the data.

    Examples:
    - SELECT * FROM data LIMIT 10
    - SELECT COUNT(*) FROM data
    - SELECT column1, AVG(column2) FROM data GROUP BY column1
    """
    _current_csv_path = config['configurable']['current_csv_path']

    if _current_csv_path is None:
        return {
            'rows': [],
            'cols': [],
            'message': 'No CSV data loaded. Please upload a CSV file first.'
        }

    try:
        # Create DuckDB connection
        conn = duckdb.connect()

        # Register the CSV file as a table
        conn.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{_current_csv_path}')")

        # Execute the query
        result = conn.execute(sql).fetchall()
        columns = [desc[0] for desc in conn.description]

        conn.close()

        return {
            'rows': str(result),
            'cols': str(columns),
            'message': 'Query executed successfully'
        }

    except Exception as e:
        import traceback
        print(f'Exception type: {type(e)}')
        print(f'Args: {e.args}')
        traceback.print_exc()
        return {
            'rows': [],
            'cols': [],
            'message': f'Error executing query: {str(e)}'
        }


@tool
def ask_data_analysis_agent(prompt: str):
    """
    Ask our expert in data analysis to answer the user's question
    """
    app = build_graph()
    init_state = {"question": prompt}
    return app.invoke(init_state)


system_prompt = """
You are a **helpful senior data analyst** who produces **concise, structured insights** for the user.

You have access to an **expert data-analysis tool** that can run SQL queries in parallel and return structured results.

---

# 🧠 Your Responsibilities

## 1. PLAN FIRST
Before calling any tool, you must perform a **short, explicit planning step**:

1. **Understand the question**
   - Identify what metrics, comparisons, or breakdowns are needed to answer the user.

2. **Break the question into exactly 2 independent sub-questions**
   - Each sub-question must be **answerable by a single SQL query**.
   - Sub-questions must be **parallelizable**: no sub-question should depend on another.

3. **Define exactly what the expert tool should output**
   - For each sub-question, specify:
     * The measure or metric
     * Dimensions or grouping
     * Any filters
     * Column names expected in the output

Your planning should be **concise and structured** — no long paragraphs.

For follow-ups, only call the tool again **if new or different data is required**.

---

## 2. INTERPRET RESULTS
Once the tool returns raw data:

- Compare across subtasks
- Identify patterns, correlations, anomalies
- Focus on **meaningful takeaways**, not long text
- Avoid any restatement of raw data unless needed for an insight

---

3. **Produce the final answer** in the required structured format (`InsightResponse`).

---

## ⚡ Response Format (REQUIRED)
It is critical that you follow the structured format below.
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

"""

parallel_app = build_parallel_only_graph()

@tool
def run_parallel_queries(question: str, sub_tasks: list[str], config: RunnableConfig) -> dict:
    """
    Run multiple analysis sub-tasks in parallel over the database.
    `sub_tasks` should be a list of str, do not send sql over the task, let the worker determine which sql to generate
    """
    current_csv_path = config['configurable']['current_csv_path']
    sub_tasks = [{"id": f"task_{i}", "description": task} for i, task in enumerate(sub_tasks)]
    init_state = {
        "question": question,
        "sub_tasks": sub_tasks,
        "results": [],
        "current_csv_path": current_csv_path
    }
    final_state = parallel_app.invoke(init_state)
    return {"results": final_state.get("results", [])}



class CSVStructuredAgent(StructuredAgent):
    """StructuredAgent configured for CSV analysis with DuckDB"""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path

        # Initialize the base StructuredAgent but override the tool
        super().__init__(user_id=None)  # No user_id needed for CSV analysis

        # Replace the agent's tools with our DuckDB tool
        # self._setup_csv_agent()

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name, max_tokens=8096)
        tools = [run_parallel_queries]
        sys_message = SystemMessage(content=system_prompt)

        self.agent_executor = create_react_agent(
            model, tools, checkpointer=memory,
            prompt=sys_message, response_format=InsightResponse,
            pre_model_hook=pre_model_hook,
        )

    def _get_config(self):
        """Override config method since we don't need user_id"""
        return {"configurable": {
            "thread_id": "csv_analysis_thread",
            "current_csv_path": self.csv_path
            }}


def create_csv_dashboard():
    # Page configuration
    st.set_page_config(
        page_title="CSV Data Assistant",
        page_icon="📊",
        layout="centered"
    )

    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'csv_data' not in st.session_state:
        st.session_state.csv_data = None
    if 'csv_path' not in st.session_state:
        st.session_state.csv_path = None
    if 'agent' not in st.session_state:
        st.session_state.agent = None

    # Chat input
    if st.session_state.csv_data is not None:
        if prompt := st.chat_input("Ask about your data (e.g., 'Show me rows where column > 100')..."):
            st_process_user_prompt(st.session_state.agent, prompt)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response(message['content'])
            else:
                st.markdown(message['content'])

    # Show metrics if data is loaded
    if 'query' not in st.session_state and st.session_state.csv_data is not None:
        st.markdown("### Quick Insights")
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True, height=150):
                st.metric('Total Rows', len(st.session_state.csv_data))
        with col2:
            with st.container(border=True, height=150):
                st.metric('Total Columns', len(st.session_state.csv_data.columns))
        with col3:
            with st.container(border=True, height=150):
                numeric_cols = len(st.session_state.csv_data.select_dtypes(include=['number']).columns)
                st.metric('Numeric Columns', numeric_cols)

    # Example queries
    if st.session_state.csv_data is not None:
        st.markdown("### Ask me anything about your data, or try these examples:")

        example_queries = [
            "Show me the first 10 rows",
            "What are the column names and types?",
            "Count total rows",
            "Show summary statistics for numeric columns"
        ]

        with st.container():
            cols = st.columns(2)
            for i, query in enumerate(example_queries):
                with cols[i % 2]:
                    if st.button(f"{query}", key=f"example_{hash(query)}", use_container_width=True):
                        st.session_state.query = query
                        st.rerun()

    # Process queued queries
    if 'query' in st.session_state and st.session_state.query:
        query_to_process = st.session_state.query
        st.session_state.query = None  # Clear it BEFORE processing
        st_process_user_prompt(st.session_state.agent, query_to_process)
    else:
        st.info('⬅ Upload your CSV file in sidebar to get started')

    with st.sidebar:
        st.subheader("CSV Data Assistant")
        st.markdown("Upload a CSV file and ask questions about your data using natural language.")

        # CSV upload
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type="csv",
            help="Upload a CSV file to analyze with AI"
        )

        if uploaded_file is not None:
            try:
                # Read the CSV file
                df = pd.read_csv(uploaded_file)
                st.session_state.csv_data = df

                # Save to temporary file for DuckDB
                temp_dir = tempfile.gettempdir()
                csv_filename = uploaded_file.name.replace('.csv', '')
                temp_csv_path = os.path.join(temp_dir, f"{csv_filename}.csv")
                df.to_csv(temp_csv_path, index=False)
                st.session_state.csv_path = temp_csv_path

                # Initialize agent with CSV data
                st.session_state.agent = CSVStructuredAgent(csv_path=temp_csv_path)

                st.success(f"✅ Loaded {len(df)} rows and {len(df.columns)} columns from {uploaded_file.name}")

                # Show data preview
                with st.expander("Data Preview", expanded=False):
                    st.dataframe(df.head())

                # Show column information
                with st.expander("Column Information", expanded=False):
                    col_info = []
                    for col in df.columns:
                        col_info.append({
                            'Column': col,
                            'Type': str(df[col].dtype),
                            'Non-null Count': df[col].count(),
                            'Null Count': df[col].isnull().sum()
                        })
                    st.dataframe(pd.DataFrame(col_info))
                st.rerun()

            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

        elif st.session_state.csv_data is None:
            st.markdown("""
            ### What you can do:
            - Upload any CSV file
            - Ask questions in natural language
            - Get SQL-powered insights automatically
            - View data summaries and statistics
            """)
            return  # Don't show the rest of the UI until file is uploaded



if __name__ == "__main__":
    st.markdown("""
    <style>
        div[data-testid="stAppDeployButton"] {
            display: none !important;
        }
        div[data-testid="stDecoration"] {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)
    st.logo('https://ahaslides.com/wp-content/uploads/2025/05/logo-full.png')

    create_csv_dashboard()