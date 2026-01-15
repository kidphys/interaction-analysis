"""
This module supports quickly create an agent UI using streamlit
"""
from typing import List
import streamlit as st

from slide_agent_dashboard_v2 import display_structured_response
from structured_agent import InsightResponse, MessageItem, StructuredAgent

def stream_agent_response_ui(agent: StructuredAgent, prompt):
    """Stream the agent response with UI updates"""

    # Create a placeholder for streaming output
    message_placeholder = st.empty()
    tool_executions = []
    info_placeholder = st.empty()

    try:
        for step in agent.stream_query(prompt):
            # print(f'UI STEP')
            # print(f'\n' + '-' * 100 + '\n')
            # print(f'\nUI Step: {step}')
            if step and step.get("messages"):
                print(step)
                last_message = step["messages"][-1]
                if hasattr(last_message, 'content') and last_message.content:
                    # Update the streaming display
                    if last_message.type == "ai":

                        # Display tool executions if any
                        if tool_executions:
                            for tool_info in tool_executions:
                                info_placeholder.info(f"🔧 Executed: {tool_info}")
                                # st.info(f"🔧 Executed: {tool_info}")

                        # Use helper function to display response
                        message_placeholder.empty()
                        with message_placeholder.container():
                            try:
                                markdown_content = last_message.content[0]['text']
                            except Exception as e:
                                markdown_content = 'Giving my conclusion...'
                            st.markdown(markdown_content)
                    elif last_message.type == "tool":
                        # Track tool execution
                        tool_name = getattr(last_message, 'name', 'Unknown Tool')
                        tool_executions.append(f"{tool_name}")
                        # st.info(f"🔧 Executing: {tool_name}...")
                        info_placeholder.info(f"🔧 Executing: {tool_name}...")
        print(f'\n\n1. Finished streaming agent response\n')
        print(f'{type(agent.get_structured_output())}: {agent.get_structured_output()}')
        return agent.get_structured_output()

    except Exception as e:
        print(f'Error executing agent: {str(e)}')
        import traceback
        traceback.print_exc()
        st.error(f"Error executing agent: {str(e)}")
        return agent.get_structured_output()


def st_process_user_prompt(agent, prompt, stream_response_ui_func=None):
    st.session_state.messages.append({"role": "user", "content": prompt})

    if stream_response_ui_func is None:
        stream_response_ui_func = stream_agent_response_ui

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("..."):
            try:
                response = stream_response_ui_func(agent, prompt)
                print(f'RESPONSE: {response}')
                if response:
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    error_msg = "Sorry, I encountered an error processing your request."
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = str(e)
                if "max_tokens" in error_msg.lower() or "truncated" in error_msg.lower():
                    st.warning("⚠️ The response was truncated. Try asking a more specific question or break your request into smaller parts.")
                    fallback_response = InsightResponse(items=[
                        MessageItem(
                            type="message",
                            content="The response was truncated due to length limits. Please try asking a more specific question."
                        )
                    ])
                    st.session_state.messages.append({"role": "assistant", "content": fallback_response})
                else:
                    st.error(f"Error: {error_msg}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {error_msg}"})
    st.rerun()


def create_agent_dashboard(
  agent: StructuredAgent,
  display_structured_response_func=None,
  example_queries: List[str]=[],
  stream_response_ui_func=None,
  refresh_messages=False
  ):

    if stream_response_ui_func is None:
        stream_response_ui_func = stream_agent_response_ui

    if display_structured_response_func is None:
        display_structured_response_func = display_structured_response

    # Page configuration
    st.set_page_config(
        page_title="AI Data Assistant",
        page_icon="🤖",
        layout="centered"
    )

    # Initialize session state
    if refresh_messages:
        st.session_state.messages = []
    else:
        if 'messages' not in st.session_state:
            st.session_state.messages = []


    st.session_state.agent = agent

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response_func(message['content'])
            else:
                st.markdown(message['content'])


    with st.container(horizontal=True):
        for query in example_queries:
            if st.button(f"{query}", key=f"example_{hash(query)}", icon=":material/search_insights:"):
                st.session_state.query = query
                st.rerun()  # Explicit rerun after setting the query

    if 'query' in st.session_state and st.session_state.query:
        query_to_process = st.session_state.query
        st.session_state.query = None  # Clear it BEFORE processing
        st_process_user_prompt(st.session_state.agent, query_to_process)
        st.rerun()  # Explicit rerun after setting the query


    if prompt := st.chat_input("Ask about your sessions, slides, or audience insights..."):
        st_process_user_prompt(st.session_state.agent, prompt, stream_response_ui_func=stream_response_ui_func)