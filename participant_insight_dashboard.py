import streamlit as st
from participant_insight.participant_agent import ParticipantInsightAgent, query_participant_answers
from react_agent_dashboard import display_chart
from st_agent import create_agent_dashboard
from structured_agent import InsightResponse


def display_structured_response(response_content):
    """Helper function to display structured responses consistently"""

    if isinstance(response_content, InsightResponse):
      for item in response_content.items:
        if item.type == "message":
          st.markdown(f"💬{item.content}")
        elif item.type == "table":
          st.dataframe(item.data)
        elif item.type == "chart":
          display_chart(item)
    else:
      st.markdown(f'Unknown response content: {response_content}')

def add_preload_sidebar(presentation_id: str = "7880449"):
    # Initialize session state for presentation_id
    if 'presentation_id' not in st.session_state:
        st.session_state.presentation_id = presentation_id
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False

    # Sidebar for data loading
    with st.sidebar:
        st.header("📊 Data Management")
        presentation_id_input = st.text_input(
            "Presentation ID",
            value=st.session_state.presentation_id,
            key="presentation_id_input"
        )

        # Check if presentation_id changed
        if presentation_id_input != st.session_state.presentation_id:
            st.session_state.data_loaded = False

        if st.button("🔄 Load Data", type="primary", use_container_width=True):
            if not presentation_id_input:
                st.error("❌ Please enter a presentation ID")
            else:
                with st.spinner("Loading participant data..."):
                    try:
                        query_participant_answers(presentation_id_input)
                        st.session_state.presentation_id = presentation_id_input
                        st.success(f"✅ Data loaded for presentation {presentation_id_input}")
                        st.session_state.data_loaded = True
                        st.session_state.data_reloaded = True  # Signal that data was reloaded
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error loading data: {str(e)}")
                        st.session_state.data_loaded = False

        if st.session_state.data_loaded:
            st.info(f"✅ Data preloaded for presentation {st.session_state.presentation_id}")
        else:
            st.warning("⚠️ Data not loaded. Click 'Load Data' to preload.")


def stream_agent_response_ui(agent: ParticipantInsightAgent, prompt):
    """Stream the agent response with UI updates"""

    try:
        output = agent.invoke(str(prompt))
        return output
    except Exception as e:
        print(f'Error executing agent: {str(e)}')
        import traceback
        traceback.print_exc()
        st.error(f"Error executing agent: {str(e)}")
        return agent.get_structured_output()


def create_participant_insight_dashboard():
    add_preload_sidebar()

    # Clear messages if data was reloaded (handled here to keep sidebar clean)
    if st.session_state.get('data_reloaded', True):
        refresh_messages = True
        st.session_state.data_reloaded = False  # Reset flag
    else:
        refresh_messages = False

    if st.session_state.presentation_id:
      agent = ParticipantInsightAgent(presentation_id=st.session_state.presentation_id)
      create_agent_dashboard(agent,
        stream_response_ui_func=stream_agent_response_ui,
        display_structured_response_func=display_structured_response, refresh_messages=refresh_messages)


if __name__ == "__main__":
  # create_participant_insight_dashboard()
    agent = ParticipantInsightAgent(presentation_id='7890915')
    output = agent.invoke("What is the completion rate of the presentation?")
    print(type(output))
    print(output)