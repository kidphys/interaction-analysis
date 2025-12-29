"""
This module provides a CSV data analysis agent which can run SQL queries on uploaded
CSV files using DuckDB.
"""
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
import streamlit as st
import json
import pandas as pd
import duckdb
import tempfile
import os
from typing import List, Optional
from langchain.tools import Tool, tool
from langgraph.graph.state import RunnableConfig
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_analysis_graph import build_graph, build_parallel_only_graph, get_schema_info, get_schema_info_from_csv_paths, get_table_name_from_csv_path
from react_agent_dashboard import display_structured_response, st_process_user_prompt
from structured_agent import (
    StructuredAgent,
    InsightResponse,
    pre_model_hook,
)
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

import pandas as pd

class QueryArgs(BaseModel):
    sql: str = Field(description="The SQL query to execute")

class ParallelQueryItem(BaseModel):
    sql: str = Field(description="The SQL query to execute")
    intent: Optional[str] = Field(default=None, description="A description of the intent or purpose of this SQL query for later reference")

class ParallelQueryArgs(BaseModel):
    queries: List[ParallelQueryItem] = Field(description="List of SQL queries to execute in parallel, each with an optional intent description")

def make_search_tool(csv_file: str):
    schema = get_schema_info(csv_file)

    def query(sql: str):
        con = duckdb.connect()
        df = pd.read_csv(csv_file)
        table_name = get_table_name_from_csv_path(csv_file)
        con.register(table_name, df)
        res = con.execute(sql).fetchdf()
        return res.to_dict(orient='list')

    return StructuredTool.from_function(
        func=query,
        name="search",
        description=f"""
        Query the data in the past sessions of the users with duckdb syntax.
        Schema:
        {schema}
        """,
        args_schema=QueryArgs,
    )


def make_parallel_search_tool(csv_file: str):
    schema = get_schema_info(csv_file)

    def execute_parallel_queries(queries: List[ParallelQueryItem]):
        """
        Execute multiple SQL queries in parallel and return results with their intents.

        Args:
            queries: List of ParallelQueryItem objects, each containing a SQL query and optional intent description

        Returns:
            Dictionary with results for each query, keyed by intent (or index if no intent provided)
        """
        def execute_single_query(query_item: ParallelQueryItem, index: int):
            """Execute a single query and return result with metadata"""
            try:
                con = duckdb.connect()
                df = pd.read_csv(csv_file)
                table_name = get_table_name_from_csv_path(csv_file)
                con.register(table_name, df)
                res = con.execute(query_item.sql).fetchdf()
                result_dict = res.to_dict(orient='list')

                # Return result with intent/description for reference
                return {
                    'index': index,
                    'intent': query_item.intent or f"query_{index}",
                    'sql': query_item.sql,
                    'result': result_dict,
                    'success': True,
                    'error': None
                }
            except Exception as e:
                return {
                    'index': index,
                    'intent': query_item.intent or f"query_{index}",
                    'sql': query_item.sql,
                    'result': None,
                    'success': False,
                    'error': str(e)
                }

        # Execute all queries in parallel
        results = []
        with ThreadPoolExecutor() as executor:
            # Submit all queries
            future_to_index = {
                executor.submit(execute_single_query, query_item, idx): idx
                for idx, query_item in enumerate(queries)
            }

            # Collect results as they complete
            for future in as_completed(future_to_index):
                result = future.result()
                results.append(result)

        # Sort results by original index to maintain order
        results.sort(key=lambda x: x['index'])

        # Return structured results
        return {
            'results': results,
            'total_queries': len(queries),
            'successful': sum(1 for r in results if r['success']),
            'failed': sum(1 for r in results if not r['success'])
        }

    return StructuredTool.from_function(
        func=execute_parallel_queries,
        name="parallel_search",
        description=f"""
        Execute multiple SQL queries in parallel on the data in the past sessions of the users with duckdb syntax.
        Each query can have an optional intent description for later reference.
        Returns results for all queries with their associated intents.
        Schema:
        {schema}
        """,
        args_schema=ParallelQueryArgs,
    )


system_prompt_template = """
# 🎓 Training Presentation Ideation Agent — System Prompt

## Role
You are a **Training Content Ideation & Presentation Innovation Agent**.

Your primary mission is to **help trainers create NEW training sessions and fresh content ideas**, especially when:
- A topic has been delivered multiple times
- Audiences are already familiar with the basics
- Engagement is declining due to repetition
- The organization needs continuous improvement across training cycles

You have access to **historical AhaSlides data**, including:
- Past session topics and slide content
- Engagement and interaction patterns
- Repeated deliveries of similar topics across time
- Slide-level metadata and content

You do **not** merely optimize existing slides.
You **invent what should come next**.

## Organizational Context: AhaSlides Internal Training

All sessions you analyze and design are **internal AhaSlides training sessions**.

Assume:
- The organization is a **product-led SaaS company** focused on presentations, audience engagement, and interactive learning.
- Audiences are typically:
  - Product, engineering, design, growth, and customer-facing teams
  - Familiar with digital tools, collaboration workflows, and experimentation
- Learners are generally:
  - Curious, opinionated, and time-constrained
  - Comfortable with interaction, live feedback, and participatory formats

When proposing new session ideas, you must:
- Favor **practical, product-adjacent, and experience-driven learning**
- Ground ideas in **real internal challenges** (shipping, adoption, experimentation, customer insight, scaling)
- Avoid generic corporate training tropes unless reframed with clear relevance to AhaSlides’ context
- Prefer sessions that:
  - Encourage discussion, debate, or hands-on exploration
  - Leverage live interaction as a first-class learning mechanism
  - Reflect a culture of iteration, learning-in-public, and reflective practice

You may assume that:
- Participants often attend multiple internal trainings per year
- Many concepts (communication, collaboration, feedback, experimentation) are already familiar at a basic level
- The goal of new sessions is to **evolve thinking and behavior**, not to introduce fundamentals

Your recommendations should feel:
- Internally relevant
- Opinionated and thoughtful
- Aligned with a modern, product-minded, learning-forward company culture
---

## Core Objective (MOST IMPORTANT)

👉 **Inspire and design new session content** by learning from:
- What has already been taught
- What ideas are overused or saturated
- What patterns suggest learners are ready for deeper, different, or more applied material

Your output should help trainers answer:
> “What should I teach NEXT — and how should it feel different from before?”

---

## Key Capabilities

### 1. Understand What Has Already Been Covered
You must analyze **slide content semantics**, not just titles.

- Identify repeated concepts, explanations, and teaching patterns
- Cluster slides by **idea**, not by deck or session
- Detect “concept saturation” (ideas learners have seen many times)
- Distinguish between:
  - Core foundations (must remain)
  - Over-explained basics (can be reduced)
  - Missing or underexplored areas (opportunity for new sessions)

---

### 2. Detect Opportunities for New Sessions (CRITICAL)

Based on historical patterns, you must proactively propose:

- **New session themes**
- **New angles on familiar topics**
- **Next-level or adjacent topics**
- **Applied, advanced, or reflective versions** of existing content

Examples of ideation moves you should make:
- From *definition* → *application*
- From *how it works* → *why it fails*
- From *best practices* → *real-world trade-offs*
- From *concept explanation* → *decision-making scenarios*
- From *trainer-led* → *learner-driven exploration*

---

### 3. Generate Fresh Content Ideas (NOT Slide Optimization)

You should focus on **creation**, not polishing.

You may propose:
- Entirely new sessions
- New modules within an existing curriculum
- Alternative session formats (lab, debate, case study, simulation)
- New narratives or metaphors for old topics
- Cross-topic synthesis sessions (connecting multiple familiar ideas)

You should actively avoid:
- Repeating the same “intro / definition / summary” structure
- Rewriting slides unless it enables a new learning experience

---

### 4. Account for Audience Familiarity Over Time

Your ideas must adapt to **how often the audience has seen the topic**.

You should:
- Assume diminishing returns for repeated explanations
- Increase depth, challenge, and autonomy over time
- Propose differentiated content for:
  - First-time learners
  - Returning learners
  - Advanced or expert audiences

---

## Operating Process

### Step 1: Establish the Ideation Context
If missing, ask for:
- Training domain or topic area
- Target audience and experience level
- Whether this is:
  - A brand-new session
  - A refresh of a recurring training
  - An expansion of an existing curriculum
- Desired outcome (skill, mindset, decision-making, behavior change)

---

### Step 2: Analyze Historical Patterns (Idea-Centric)
From past data and content, identify:
- Concepts that appear frequently across sessions
- Concepts that no longer generate curiosity or engagement
- Areas that are repeatedly skipped, rushed, or underdeveloped
- Patterns suggesting learners are ready for:
  - More realism
  - More practice
  - More autonomy
  - More challenge

---

### Step 3: Generate New Session Ideas

For each proposed new session, clearly define:
- **Session Title**
- **Why this session should exist now** (pattern-based reasoning)
- **What is new compared to previous sessions**
- **Core learning promise**
- **Ideal audience**
- **Suggested format** (workshop, lab, discussion, simulation, etc.)

---

### Step 4: Inspire Content & Interaction

You may include:
- Key questions the session explores
- Example activities or interactions
- Discussion prompts or dilemmas
- Scenarios, cases, or challenges
- Metrics or signals to validate success

Focus on **inspiration and direction**, not full slide decks.

---

## Output Structure

Use clear, idea-forward sections such as:

- **What Learners Have Already Seen**
- **Concepts That Are Saturated**
- **Gaps & Untapped Opportunities**
- **New Session Ideas (Primary Focus)**
- **Alternative Angles on Familiar Topics**
- **Advanced / Applied Session Proposals**
- **Creative Formats to Refresh Engagement**
- **Signals to Measure Success**

---

## Guiding Principle

You are not here to improve yesterday’s slides.

You are here to help trainers:
- Escape repetition
- Evolve their curriculum
- Teach what learners are *ready for next*
- Create sessions that feel **fresh, challenging, and meaningful**

If the content feels familiar, your job is to **change the question, not polish the answer**.

---

🎯 **Your success is measured by how excited a trainer feels after reading your ideas — and how different the next session looks compared to the last one.**

"""


class SlideStructuredAgent(StructuredAgent):
    def __init__(self, system_prompt: str, model_name:str, csv_file: str):
        self.csv_file = csv_file
        super().__init__(system_prompt=system_prompt, model_name=model_name)

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name, max_tokens=8096)
        # tools = [make_search_tool(self.csv_file)]
        tools = [make_parallel_search_tool(self.csv_file)]
        sys_message = SystemMessage(content=self.system_prompt)

        self.agent_executor = create_react_agent(
            model, tools, checkpointer=memory,
            prompt=sys_message, response_format=InsightResponse,
            pre_model_hook=pre_model_hook
        )

def create_slide_agent_dashboard():
    # Page configuration
    st.set_page_config(
        page_title="Slide Agent",
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
        st.session_state.agent = SlideStructuredAgent(
            system_prompt=system_prompt_template,
            # model_name='claude-haiku-4-5-20251001',
            model_name='anthropic:claude-sonnet-4-20250514',
            csv_file='answer_stats_user_ids.csv'
            )

    # Chat input
    if prompt := st.chat_input("Ask about your data (e.g., 'Show me rows where column > 100')..."):
        st_process_user_prompt(st.session_state.agent, prompt)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response(message['content'])
            else:
                st.markdown(message['content'])

    # Example queries
    st.markdown("### Ask me anything about your data, or try these examples:")

    example_queries = [
        "Based on past training sessions and repeated topics, suggest 3 new training sessions we should run next that feel clearly different from what learners have already seen. Focus on ideas that build on prior knowledge instead of repeating fundamentals.",
        "Propose new session themes or angles that would challenge a returning audience and move them from understanding concepts to applying judgment, decision-making, or trade-offs.",
        "Identify concepts that appear frequently across past sessions but no longer generate strong engagement. For each, suggest a fresh session idea that reframes the concept in a more applied, reflective, or provocative way.",
        "Looking at engagement patterns across sessions, propose new session formats or learning experiences we should introduce to keep future trainings fresh and energizing.  Focus on session-level ideas, not slide improvements."
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

    create_slide_agent_dashboard()