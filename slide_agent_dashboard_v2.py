"""
This module provides a CSV data analysis agent which can run SQL queries on uploaded
CSV files using DuckDB.
"""
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
from react_agent_dashboard import st_process_user_prompt, display_structured_response
from slide_agents.data_analyst_graph import create_graph as create_data_analyst_graph
from slide_agents.insight_repository import InsightRepository, create_repository_from_duckdb_file
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

class ResearchInput(BaseModel):
    questions: List[str] = Field(..., description="List of questions to answer")


message_with_cititation_prompt = """
An analysis with data reference (using citation_id) to support your argument.
Keep the tone playful yet scientific.
"""

message_prompt = """
Simple message, including reply, recommendation, arugment or encouragement from the agent.
Keep the tone playful yet scientific.
"""

class Message(BaseModel):
    type: Literal["message"] = "message"
    content: str = Field(description=message_prompt)

class MessageWithCitation(BaseModel):
    type: Literal["message_with_citation"] = "message_with_citation"
    content: str = Field(description=message_with_cititation_prompt)
    citation_id: str = Field(description="ID of the InsightItem this message references (if there is no citation, leave it blank)")


class InsightResponseV2(BaseModel):
    items: List[Union[Message, MessageWithCitation]] = Field(description="List of messages")


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
    try:
        g = create_data_analyst_graph()
        res = g.invoke(state)
        insights = []
        for item in res['results']:
            for insight in item['analysis']['items']:
                insights.append({
                    'question': item['question'],
                    'message': insight['message']['content'],
                    'citation_id': insight['id']
                })
    except Exception as e:
        print('\n' + '-' * 100 + '\n')
        print(f'Exception type: {type(e)}')
        print(f'Args: {e.args}')
        print('Full traceback:')
        import traceback
        traceback.print_exc()
        raise e
    return insights


class SlideStructuredAgent(StructuredAgent):
    def __init__(self, system_prompt: str, model_name: str, csv_paths: List[str]):
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
        self.insight_duckdb_file = "insight_items.duckdb"
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
        items = []
        insight_repo = create_repository_from_duckdb_file(self.insight_duckdb_file)

        print(f'\n\nOriginal response: {self.insight_response}')

        for item in self.insight_response.items:
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
            csv_paths=['answer_stats_user_ids.csv']
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