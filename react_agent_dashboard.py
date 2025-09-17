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



def display_structured_response(response_content):
    """Helper function to display structured responses consistently"""
    if isinstance(response_content, InsightResponse):
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
                    st.bar_chart(df)
                elif item.chart_type == "line":
                    st.line_chart(df)
                elif item.chart_type == "area":
                    st.area_chart(df)
                else:
                    # Default to dataframe if chart type not supported
                    st.dataframe(df)
                    st.info(f"Chart type '{item.chart_type}' displayed as table")
        return True
    elif isinstance(response_content, str):
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



def stream_agent_response_ui(prompt, user_id="1472007"):
    """Stream the agent response with UI updates"""
    # Set the current user_id in session state for the tool to access
    st.session_state.current_user_id = user_id

    agent = StructuredAgent(user_id=user_id)

    # Create a placeholder for streaming output
    message_placeholder = st.empty()
    full_response = ""
    tool_executions = []

    try:
        for step in agent.stream_query(prompt):
            if step and step.get("messages"):
                last_message = step["messages"][-1]
                if hasattr(last_message, 'content') and last_message.content:
                    # Update the streaming display
                    if last_message.type == "ai":
                        full_response = last_message.content

                        # Display tool executions if any
                        if tool_executions:
                            for tool_info in tool_executions:
                                st.info(f"🔧 Executed: {tool_info}")

                        # Use helper function to display response
                        message_placeholder.empty()
                        with message_placeholder.container():
                            st.markdown("🤖 **AI Response:**")
                            display_structured_response(last_message.content)
                    elif last_message.type == "tool":
                        # Track tool execution
                        tool_name = getattr(last_message, 'name', 'Unknown Tool')
                        tool_executions.append(f"{tool_name}")
                        st.info(f"🔧 Executing: {tool_name}...")

        return full_response

    except Exception as e:
        st.error(f"Error executing agent: {str(e)}")
        return None

# Main UI
st.title("🤖 AI Data Assistant")
st.markdown("Ask questions about your data warehouse and get intelligent responses!")

# Sidebar for configuration
with st.sidebar:
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

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Chat interface
st.markdown("### Chat with your Data")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        display_structured_response(message['content'])

# Chat input
if prompt := st.chat_input("Ask me anything about your data..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking and analyzing data..."):
            response = stream_agent_response_ui(prompt, user_id)
            if response:
                st.session_state.messages.append({"role": "assistant", "content": response})

            else:
                error_msg = "Sorry, I encountered an error processing your request."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Example queries section
with st.expander("💡 Example Queries"):
    st.markdown("""
    Try these example queries to get started:

    - "Give me the top 10 questions with their accuracy rates"
    - "What are the most common wrong answers for quiz questions?"
    - "Show me engagement patterns by slide type"
    - "Which presentations have the highest participation rates?"
    - "What are the trending topics in open-ended responses?"
    """)

    example_queries = [
        "Give me the top 10 questions with their accuracy rates",
        "What are the most common slide types used?",
        "Show me recent presentation activity",
        "Which questions have the lowest accuracy rates?"
    ]

    for query in example_queries:
        if st.button(f"Try: {query}", key=f"example_{hash(query)}"):
            # Simulate clicking the chat input
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("Thinking and analyzing data..."):
                    response = stream_agent_response_ui(query, user_id)

                    if response:
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    else:
                        error_msg = "Sorry, I encountered an error processing your request."
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})

            st.rerun()

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
