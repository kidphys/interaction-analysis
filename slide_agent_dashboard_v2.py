"""
This module provides a CSV data analysis agent which can run SQL queries on uploaded
CSV files using DuckDB.
"""
import time
from typing import List, Literal
from typing import Union
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, InstanceOf
import streamlit as st
from langchain.tools import tool
from react_agent_dashboard import display_visualization, st_process_user_prompt
# from slide_agents.data_analyst_graph import create_graph as create_data_analyst_graph
from slide_agents.insight_repository import InsightRepository, create_repository_from_duckdb_file
from slide_agents.message import InsightResponseV2, MessageWithCitation
from slide_agents.query_node import InsightItem
from structured_agent import (
    ChartItem,
    MessageItem,
    StructuredAgent,
    InsightResponse,
    TableItem,
    pre_model_hook,
)
import duckdb

from slide_agents.prompt_slide_agent import prompt_template as base_system_prompt_template

system_prompt_template = base_system_prompt_template

# Research tool definition - removed as we use flat graph


import pandas as pd

def display_insight_item(item: InsightItem):
    def _get_visual_item(item):
        if item.visualization:
            if item.visualization.type == "table":
                return TableItem(
                    type="table",
                    data=item.visualization.data,
                    title=item.visualization.title,
                )
            elif item.visualization.type == "chart":
                return ChartItem(
                    type="chart",
                    data=item.visualization.data,
                    chart_type=item.visualization.chart_type,
                    title=item.visualization.title,
                )
    visual_item = _get_visual_item(item)
    st.badge(item.id)
    st.markdown(item.message.content)
    display_visualization(visual_item)


def insight_response_v2_to_insight_response(insight_response: InsightResponseV2, insight_repo: InsightRepository) -> InsightResponse:
    items = []
    for item in insight_response.items:
        items.append(MessageItem(
            type="message",
            content=item.content,
        ))
        # check type
        if isinstance(item, MessageWithCitation):
            item = insight_repo.load(item.citation_id)
            if item.visualization:
                # create table item or chart item based on the visualization type
                if item.visualization.type == "table":
                    items.append(TableItem(
                        type="table",
                        data=item.visualization.data,
                        title=item.visualization.title,
                    ))
                elif item.visualization.type == "chart":
                    items.append(ChartItem(
                        type="chart",
                        data=item.visualization.data,
                        chart_type=item.visualization.chart_type,
                        title=item.visualization.title,
                    ))
    return InsightResponse(items=items)


def get_numbered_citation(insight_response: InsightResponseV2):
    """
    Run through the list of message and number each citation 1-2-3
    for reference
    """
    citation_list = [item.citation_id for item in insight_response.items if item.type == "message_with_citation"]
    return {
        citation_id: idx for idx, citation_id in enumerate(citation_list)
    }


from slide_agents.flat_combined_graph import create_flat_combined_graph

class AgentExecutor():

    def __init__(self, checkpointer=None):
        self.graph = create_flat_combined_graph(checkpointer=checkpointer)

    def stream(self, messages: dict, config: dict, stream_mode="values"):
        csv_paths = config['configurable']['csv_paths']
        name = config['configurable']['name']
        insight_duckdb_file = config['configurable']['insight_duckdb_file']
        state = {
            'name': name,
            'csv_paths': csv_paths,
            'insight_duckdb_file': insight_duckdb_file,
            'messages': messages["messages"]
        }
        for step in self.graph.stream(state, config=config):
            yield step

    def get_structured_response(self, thread_id):
        final_state = self.graph.get_state(
            config={"configurable": {"thread_id": thread_id}}
        )
        return final_state.values['structured_response']

class SlideStructuredAgent(StructuredAgent):
    def __init__(self, system_prompt: str, model_name: str, csv_paths: List[str],
        insight_duckdb_file: str = "insight_items.duckdb"):
        self.csv_paths = csv_paths
        # Override system_prompt and model_name before calling super
        # We need to set these before _initialize_agent is called
        self.system_prompt = system_prompt
        self.model_name = model_name
        # Don't call super().__init__ as it will call _initialize_agent with wrong params
        # Instead, initialize manually
        self.user_id = "1472007"  # Default user_id, not used in this context
        self.agent_executor = None
        self.insight_response = None
        self.insight_duckdb_file = insight_duckdb_file
        self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the flat combined graph agent"""
        from slide_agents.flat_combined_graph import create_flat_combined_graph
        memory = MemorySaver()

        # The flat graph handles model and prompt via config or defaults.
        # However, to inject our specific system prompt and model, we should probably rely on config.
        # But create_flat_graph uses config.get('model_name') etc.
        # We need to ensure when invoke is called, these are passed.
        # But _get_config is used for invoke config.

        # We create the graph.
        self.agent_executor = AgentExecutor(checkpointer=memory)

    def _get_config(self):
        return {
            "configurable": {
                "thread_id": f"user_{self.user_id}",
                "user_id": self.user_id,
                "csv_paths": self.csv_paths,
                "name": 'answer_stats',
                "insight_duckdb_file": self.insight_duckdb_file,
                "model_name": self.model_name,
                "system_prompt": self.system_prompt
            }
        }

    def get_structured_output(self):
        """
        Get the structured output from the agent
        Here we will convert InsightResponseWithCitation to InsightResponse
        to make it compatible with UI
        """
        thread_id = f"user_{self.user_id}"
        return self.agent_executor.get_structured_response(thread_id)
        # if self.insight_response is None:
        #     return InsightResponse(items=[
        #         MessageItem(
        #             type="message",
        #             content="⚠️ Structured output not found or not processed yet"
        #         )
        #     ])
        # return self.insight_response


def display_structured_response(response_content, insight_duckdb_file: str = "insight_items.duckdb" ):
    """Helper function to display structured responses consistently"""

    if isinstance(response_content, InsightResponseV2):
        numbered_citation = get_numbered_citation(response_content)
        # Handle structured response object
        for idx, item in enumerate(response_content.items):
            if item.type == "message":
                st.markdown(f"💬{item.content}")
            elif item.type == "message_with_citation":
                st.markdown(f"""{item.content}""")
                options = [f"{item.citation_id}"]
                selection = st.pills("Reference",
                    options,
                    key=f"pills_{item.citation_id}_{idx}",
                    selection_mode="single",
                    format_func=lambda citation_id: f"Ref: {numbered_citation[citation_id]}",
                    label_visibility="hidden"
                    )
                if selection:
                    insight_repo = create_repository_from_duckdb_file(insight_duckdb_file)
                    item = insight_repo.load(selection)
                    st.session_state.active_reference = item
            else:
                st.markdown(f"💬{item.content}")
    elif isinstance(response_content, str):
        st.markdown(response_content)
    return False


@st.dialog("Reference Details")
def show_reference(item: InsightItem):
    display_insight_item(item)


def create_slide_agent_dashboard():
    # Page configuration
    st.set_page_config(
        page_title="Slide Agent",
        page_icon="📊",
        layout="centered"
    )
    insight_duckdb_file = "insight_items.duckdb"
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
            csv_paths=['answer_stats_user_ids.csv'],
            insight_duckdb_file=insight_duckdb_file
            )

    # Chat input
    if prompt := st.chat_input("Ask about your data (e.g., 'Show me rows where column > 100')..."):
        st_process_user_prompt(st.session_state.agent, prompt)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response(message['content'], insight_duckdb_file)
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

    if "active_reference" in st.session_state:
        show_reference(st.session_state.active_reference)

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