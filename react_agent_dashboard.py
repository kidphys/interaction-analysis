import streamlit as st
import json
import pandas as pd
from structured_agent import (
    StructuredAgent,
    InsightResponse,
    MessageItem,
    TableItem,
    ChartItem,
    initialize_agent,
    stream_agent_response
)


def stream_agent_response_ui(agent: StructuredAgent, prompt):
    """Stream the agent response with UI updates"""

    # Create a placeholder for streaming output
    message_placeholder = st.empty()
    tool_executions = []

    try:
        for step in agent.stream_query(prompt):
            if step and step.get("messages"):
                print(f'\n' + '-' * 100 + '\n')
                print(step)
                last_message = step["messages"][-1]
                if hasattr(last_message, 'content') and last_message.content:
                    # Update the streaming display
                    if last_message.type == "ai":

                        # Display tool executions if any
                        if tool_executions:
                            for tool_info in tool_executions:
                                st.info(f"🔧 Executed: {tool_info}")

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
                        st.info(f"🔧 Executing: {tool_name}...")
        print(f'\n\nFinished streaming agent response\n')
        print(f'{type(agent.get_structured_output())}: {agent.get_structured_output()}')
        return agent.get_structured_output()

    except Exception as e:
        print(f'Error executing agent: {str(e)}')
        import traceback
        traceback.print_exc()
        st.error(f"Error executing agent: {str(e)}")
        return agent.get_structured_output()


def display_structured_response(response_content):
    """Helper function to display structured responses consistently"""
    if isinstance(response_content, InsightResponse):
        print(f'-'*100 + '\n')
        print(f'Instance of Insight response_content: {response_content}')
        # Handle structured response object
        for item in response_content.items:
            if item.type == "message":
                st.markdown(f"💬 **Analysis:** {item.content}")
            elif item.type == "table":
                if item.title and item.title.strip():
                    st.markdown(f"📊 **{item.title}**")
                df = pd.DataFrame(item.data)
                st.dataframe(df)
            elif item.type == "chart":
                if item.title and item.title.strip():
                    st.markdown(f"📈 **{item.title}**")
                df = pd.DataFrame(item.data)
                if item.chart_type == "bar":
                    st.bar_chart(df, x=df.columns[0], y=df.columns[1])
                elif item.chart_type == "line":
                    st.line_chart(df, x=df.columns[0], y=df.columns[1])
                elif item.chart_type == "area":
                    st.area_chart(df, x=df.columns[0], y=df.columns[1])
                else:
                    # Default to dataframe if chart type not supported
                    st.dataframe(df)
                    st.info(f"Chart type '{item.chart_type}' displayed as table")
        return True
    elif isinstance(response_content, str):
        print(f'-'*100 + '\n')
        print(f'Instance of legacy JSON format')
        print(f'{response_content}')
        print(f'-'*100 + '\n')
        # Handle legacy JSON format for backward compatibility
        try:
            if "```json" in response_content:
                # extract the inner text between ```json and ```
                message_content = response_content.split('```json')[1].split('```')[0]
                message_content = json.loads(message_content.replace("\n", ""))
                if "rows" in message_content and "cols" in message_content:
                    if "message" in message_content:
                        st.markdown(f"💬 **Analysis:** {message_content['message']}")
                    df = pd.DataFrame(message_content['rows'], columns=message_content['cols'])
                    st.dataframe(df)
                else:
                    st.markdown(response_content)
                return True
        except Exception as e:
            st.info(f'Cannot parse JSON content: {str(e)}')
            st.markdown(response_content)
            return True

    # Fallback for plain text
    st.markdown(response_content)
    return False


def create_configuration():
    st.header("Configuration")
    user_id = st.text_input("User ID", value=st.session_state.current_user_id, help="Enter the user ID for data filtering")

    # Update session state when user_id changes
    if user_id != st.session_state.current_user_id:
        st.session_state.current_user_id = user_id

    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This dashboard connects to your Redshift data warehouse and uses AI to:
    - Answer questions about your data
    - Provide recommendations based on analysis
    - Generate SQL queries automatically
    """)

    st.info("""
    💡 **Tips for better responses:**
    - Ask specific questions to avoid response truncation
    - Break complex requests into smaller parts
    - If you get a truncation warning, try rephrasing your question more concisely
    """)

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()



def create_agent_dashboard():
    # Page configuration
    st.set_page_config(
        page_title="AI Data Assistant",
        page_icon="🤖",
        layout="wide"
    )

    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'agent_executor' not in st.session_state:
        st.session_state.agent_executor = None
    if 'current_user_id' not in st.session_state:
        st.session_state.current_user_id = "1472007"

    if 'agent' not in st.session_state:
        st.session_state.agent = StructuredAgent(user_id=st.session_state.current_user_id)


    # Main UI
    st.title("🤖 AI Data Assistant")
    st.markdown("Ask questions about your data warehouse and get intelligent responses!")

    # Sidebar for configuration
    with st.sidebar:
        create_configuration()

    # Chat interface
    st.markdown("### Chat with your Data")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response(message['content'])
            else:
                st.markdown(message['content'])


    def st_process_user_prompt(prompt):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking and analyzing data..."):
                try:
                    response = stream_agent_response_ui(st.session_state.agent, prompt)
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


    # Chat input
    if prompt := st.chat_input("Ask me anything about your data..."):
        st_process_user_prompt(prompt)

    # Example queries section
    with st.expander("💡 Example Queries"):
        st.markdown("""
        Try these example queries to get started:
        """)

        example_queries = [
            "What are the most common slide types used?",
            "Show me engagement patterns by slide type",
            "Show me recent presentation activity",
            "Which questions have the lowest accuracy rates?",
            "Which presentations have the highest participation rates?",
            "What are the trending topics in open-ended responses?"
        ]

        for query in example_queries:
            if st.button(f"Try: {query}", key=f"example_{hash(query)}"):
                st_process_user_prompt(query)

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
            Powered by LangChain 🦜🔗 and Streamlit
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    create_agent_dashboard()