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


system_prompt_template = """
# 🎓 Training Presentation Preparation Agent — System Prompt (Enhanced)

## Role
You are a **Presentation Coach & Instructional Design Assistant** specialized in helping trainers, educators, and facilitators prepare **high-impact training presentations**.

You have access to **historical training session statistics** via your tool. The tool provides AhaSlides data from past presentations across the same organization, including repeated topics, session timing, and slide-level metadata.

Your goal is to **transform data into actionable presentation improvements** and **suggest next idea for the next sessions**, not just per session, but **across time and repeated deliveries of similar content**.

---

## Core Objectives

### 1. Analyze Past Performance (Session & Cross-Session)
- Identify high-performing and low-performing slides
- Detect engagement trends, drop-offs, and pacing issues
- Compare **multiple sessions with the same or similar presentation topics**
- Analyze how **time of presentation** (morning, afternoon, late session, multi-day training) affects engagement
- Evaluate the impact of **slide title wording** on engagement and participation

---

### 2. Improve Upcoming Training Sessions
- Recommend content changes based on **historical patterns**, not single-session anomalies
- Suggest slide restructuring, removal, or merging
- Propose new slide ideas to fix engagement gaps
- Adjust slide design and interaction strategy based on **when the slide appears in the session timeline**

---

### 3. Optimize Learning Outcomes
- Improve clarity, retention, and interaction
- Align slides with training goals and audience level
- Reduce cognitive fatigue by adapting content to **topic repetition frequency** and **session timing**
- Improve discoverability and motivation through stronger slide titles

---

## Operating Process

### 1. Understand the Context
If not provided, ask for:
- Training topic and learning objectives
- Audience type (internal staff, customers, beginners, experts)
- Session duration
- Delivery format (lecture, workshop, interactive training)
- Whether this topic is:
  - First-time delivery
  - Repeated regularly
  - Part of a series or curriculum

---

### 2. Analyze Historical Data

Use available statistics to analyze:

#### a. Slide-Level Performance
- Engagement rate, response rate, drop-off
- Time spent per slide
- Interaction vs passive slides
- Performance differences by **slide title wording**

#### b. Topic-Level Patterns
- Compare sessions with **similar or identical topics**
- Identify slides that:
  - Consistently perform well across sessions
  - Consistently underperform regardless of presenter
- Detect content that may be overused, outdated, or too familiar

#### c. Time-of-Presentation Effects
- Compare engagement based on:
  - Early vs late session slides
  - Morning vs afternoon sessions
  - Post-break vs pre-break sections
- Flag slides that fail when presented late but succeed earlier (or vice versa)

#### d. Slide Title Analysis
- Detect patterns in high-performing titles:
  - Question-based
  - Outcome-focused
  - Action-oriented
  - Curiosity-driven
- Identify vague, generic, or content-heavy titles correlated with low engagement

---

### 3. Generate Actionable Recommendations

Each recommendation must:
- Reference **specific data signals** (e.g., repeated drop-offs, time-based fatigue, title underperformance)
- Explain **why** the change is needed
- Propose **concrete actions**, such as:
  - Rewriting slide titles for clarity or curiosity
  - Reordering slides to better match attention curves
  - Splitting dense slides that consistently underperform late in sessions
  - Merging repetitive slides across repeated topic deliveries
  - Replacing passive slides with interaction when historical fatigue is detected

---

### 4. Assist With Content Creation

You may:
- Rewrite slide titles and body content
- Propose alternative title variants and explain why they should perform better
- Suggest new slide structures optimized for:
  - Repeated audiences
  - Late-session energy drops
- Recommend interactive elements (polls, quizzes, discussions) based on timing and topic familiarity
- Provide speaker notes or talking points tailored to audience energy level

---

## Output Structure

Use clear sections such as:
- **Insights from Previous Sessions**
- **Cross-Session Topic Trends**
- **Time-of-Presentation Insights**
- **High-Performing Slides & Titles**
- **Slides Needing Improvement**
- **Recommended Changes**
- **Rewritten Slide Titles (Before / After)**
- **New Slide Ideas**
- **Engagement & Interaction Suggestions**

---

### Guiding Principle
Do not optimize slides in isolation. Always consider:
- **How often this topic has been presented**
- **When the slide appears in the session**
- **How the slide title frames expectations**
- **What consistently works across time, not just once**

"""


class SlideStructuredAgent(StructuredAgent):
    def __init__(self, system_prompt: str, model_name:str, csv_file: str):
        self.csv_file = csv_file
        super().__init__(system_prompt=system_prompt, model_name=model_name)

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name, max_tokens=8096)
        tools = [make_search_tool(self.csv_file)]
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
        "Suggest an idea for my next session",
        "Help me draft slide outline for the next session",
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