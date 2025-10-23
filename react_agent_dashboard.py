import streamlit as st
import json
import pandas as pd
from amber_dashboard import build_reaction_dashboard
from structured_agent import (
    StructuredAgent,
    InsightResponse,
    MessageItem,
    TableItem,
    ChartItem,
    get_all_answers,
    get_presentation_count,
    get_response_count,
    get_slide_count,
    initialize_agent,
    stream_agent_response
)


def stream_agent_response_ui(agent: StructuredAgent, prompt):
    """Stream the agent response with UI updates"""

    # Create a placeholder for streaming output
    message_placeholder = st.empty()
    tool_executions = []
    info_placeholder = st.empty()

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


    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    with st.spinner("Speed up query..."):
        print(f'Preload data for {st.session_state.current_user_id}')
        get_all_answers(st.session_state.current_user_id)
        print(f'DONE Preload data for {st.session_state.current_user_id}')



def st_process_user_prompt(agent, prompt):
    st.session_state.messages.append({"role": "user", "content": prompt})


    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("..."):
            try:
                response = stream_agent_response_ui(agent, prompt)
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

def create_agent_dashboard(username, user_id):
    # Page configuration
    st.set_page_config(
        page_title="AI Data Assistant",
        page_icon="🤖",
        layout="centered"
    )

    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'agent_executor' not in st.session_state:
        st.session_state.agent_executor = None
    if 'current_user_id' not in st.session_state:
        st.session_state.current_user_id = user_id

    if 'agent' not in st.session_state:
        st.session_state.agent = StructuredAgent(user_id=st.session_state.current_user_id)


    # Main UI
    st.subheader(f"Hi {username.capitalize()}")
    st.markdown("Welcome to Data Chat - your assistant for session analytics.")

    if 'query' not in st.session_state:
        st.markdown("Here are some quick insights from all your sessions:")
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True, height=150):
                presentation_count = get_presentation_count(st.session_state.current_user_id)
                st.metric('Total sessions', presentation_count)
        with col2:
            with st.container(border=True, height=150):
                response_count = get_response_count(st.session_state.current_user_id)
                st.metric('Responses Collected', response_count)
        with col3:
            with st.container(border=True, height=150):
                slide_count = get_slide_count(st.session_state.current_user_id)
                st.metric('Slides Created', slide_count)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response(message['content'])
            else:
                st.markdown(message['content'])



    st.markdown("""
    Want deeper insight? Ask me anything about your presentations, or click a suggestion
    """)

    example_queries = [
        "Show engagement & completion rates",
        "Who engaged the most?",
        "Which questions were most commonly wrong?",
        "Compare sessions over time"
    ]

    with st.container(horizontal=True):
        for query in example_queries:
            if st.button(f"{query}", key=f"example_{hash(query)}", icon=":material/search_insights:"):
                st.session_state.query = query
                st.rerun()  # Explicit rerun after setting the query

    if 'query' in st.session_state and st.session_state.query:
        query_to_process = st.session_state.query
        st.session_state.query = None  # Clear it BEFORE processing
        st_process_user_prompt(st.session_state.agent, query_to_process)


    if prompt := st.chat_input("Ask about your sessions, slides, or audience insights..."):
        st_process_user_prompt(st.session_state.agent, prompt)

    # # Sidebar for configuration
    # with st.sidebar:
    #     create_configuration()
    # def query_builder_page():
    #     st.title("Query builder")

    # pg = st.navigation(["query_builder_dashboard.py", query_builder_page])
    # pg.run()

user_map = {
    'tara': 3146502,
    'april': 2992027,
    'kiotViet': 259137,
    'cheryl': 1918789,
    'duke': 1472007,
    'don': 1851905,
}

def agent_dashboard_page():
    query_params = st.query_params
    user = query_params.get("user", "duke")  # Default to "home"
    if user in user_map:
        create_agent_dashboard(user, user_map.get(user))
    else:
        st.write(f'Not supported user: {user}')


def reaction_dashboard_page():
    query_params = st.query_params
    user = query_params.get("user", "duke")  # Default to "home"
    if user in user_map:
        st.set_page_config(layout="wide")
        build_reaction_dashboard(user_map.get(user))
    else:
        st.write(f'Not supported user: {user}')

if __name__ == "__main__":
    st.logo('https://ahaslides.com/wp-content/uploads/2025/05/logo-full.png')
    pg = st.navigation([
        st.Page(agent_dashboard_page, title="Agent"),
        st.Page('metrics_dashboard.py', title="Presentation metrics"),
        st.Page(reaction_dashboard_page, title="Reaction Metrics"),
        st.Page("query_builder_dashboard.py", title="Build your own report"),
    ])
    pg.run()