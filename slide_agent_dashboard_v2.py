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
from slide_agents.data_analyst_graph import create_graph as create_data_analyst_graph
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

@tool
def research(questions: List[str], config: RunnableConfig):
    """
    Research the data to answer the questions.
    Returns insights with full visualization data.
    Args:
        questions: List of questions to answer
    Returns:
        List of answers to the questions, each containing message and visualization data
    """
    csv_paths = config['configurable']['csv_paths']
    name = config['configurable']['name']
    insight_duckdb_file = config['configurable']['insight_duckdb_file']
    state = {
        'name': name,
        'csv_paths': csv_paths,
        'questions': questions,
        'insight_duckdb_file':insight_duckdb_file
    }
    # try:
        # g = create_data_analyst_graph()
        # res = g.invoke(state)
        # insights = []
        # for item in res['results']:
        #     for insight in item['analysis']['items']:
        #         insights.append({
        #             'question': item['question'],
        #             'message': insight['message']['content'],
        #             'citation_id': insight['id']
        #         })
    return [{"question": "What advanced or applied topics are underrepresented or missing entirely?", "message": "The data only covers \'Basic/General\' topics, suggesting that advanced or applied topics are missing entirely, with no data available on their engagement, participation, or content coverage. This matters because it implies a significant gap in the curriculum or content offerings. It suggests that there is a need to develop and include more advanced or applied topics to cater to the needs of learners who are looking for more in-depth knowledge.", "citation_id": "8e2d63fd086dc151"}, {"question": "What engagement patterns show where audiences might be experiencing fatigue with familiar content?", "message": "The audience may be experiencing fatigue with familiar content in the \'Brainstorm\' slide type, which has the lowest average engagement of 29.47 and a significant decline in engagement of -21.99. This suggests that the content may be too repetitive or stale, leading to decreased audience interest. To combat this, it\'s recommended to refresh the content or introduce new formats to re-engage the audience.", "citation_id": "dda8ee7378904124"}, {"question": "What engagement patterns show where audiences might be experiencing fatigue with familiar content?", "message": "The \'Pick Answer\' slide type has the highest occurrence count of 135, but its average engagement decline is 3.14, indicating potential fatigue. The \'Match Pairs\' slide type has a relatively high engagement volatility of 20.59, suggesting that the audience may be experiencing fatigue due to the repetitive nature of the content. To mitigate this, it\'s recommended to introduce more varied and dynamic content to keep the audience engaged.", "citation_id": "ff206c2a57e0c838"}, {"question": "What practical, hands-on, or decision-making focused training approaches are least used?", "message": "NO_INSIGHT", "citation_id": "ba668956f260c6f0"}, {"question": "What AhaSlides-specific features or use cases could be explored more deeply in training?", "message": "The \'Pick Answer\' slide type has the highest total number of slides with 135, and an average engagement of 71.07%, suggesting it is a widely used and moderately engaging feature that could be explored more deeply in training. Additionally, the \'Scales\' slide type has a high average number of answers per slide with 222.34, indicating its potential for in-depth discussion and exploration in training. The \'Word Cloud\' and \'Brainstorm\' slide types have low average engagement, with 47.55% and 30.55% respectively, suggesting they may require additional training or support to increase their effectiveness.", "citation_id": "6dc00c757aa5e8f7"}, {"question": "What AhaSlides-specific features or use cases could be explored more deeply in training?", "message": "The \'Short Answer\' slide type has the highest average engagement with 73.99%, and the \'Open Ended\' slide type has the lowest average engagement with 34.32%, indicating a need for more targeted training on effective question design and facilitation techniques. Furthermore, the \'Pick Answer\' slide type has the highest number of high-engagement slides with 75, suggesting its potential for creating engaging and interactive presentations.", "citation_id": "7c123df8e59aa612"}]
    # except Exception as e:
    #     print('\n' + '-' * 100 + '\n')
    #     print(f'Exception type: {type(e)}')
    #     print(f'Args: {e.args}')
    #     print('Full traceback:')
    #     import traceback
    #     traceback.print_exc()
    #     raise e
    # return insights

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
    st.markdown(item.message.message)
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
        """Initialize the React agent with memory - override to use research tool instead of fast_query"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name, max_tokens=8096)
        tools = [research]
        sys_message = SystemMessage(content=self.system_prompt)

        self.agent_executor = create_react_agent(
            model, tools, checkpointer=memory,
            prompt=sys_message, response_format=InsightResponseV2,
            pre_model_hook=pre_model_hook
        )

    def _get_config(self):
        return {
            "configurable": {
                "thread_id": f"user_{self.user_id}",
                "user_id": self.user_id,
                "csv_paths": self.csv_paths,
                "name": 'answer_stats',
                "insight_duckdb_file": self.insight_duckdb_file
            }
        }

    def get_structured_output(self):
        """
        Get the structured output from the agent
        Here we will convert InsightResponseWithCitation to InsightResponse
        to make it compatible with UI
        """
        if self.insight_response is None:
            return InsightResponse(items=[
                MessageItem(
                    type="message",
                    content="⚠️ Structured output not found or not processed yet"
                )
            ])
        return self.insight_response


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