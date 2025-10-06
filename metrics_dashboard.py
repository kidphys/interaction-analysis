import streamlit as st
from presentation_agent import PresentationAgent
from react_agent_dashboard import display_structured_response, st_process_user_prompt
from warehouse_v5_repo import PresentationData, PresentationDataSQL, get_recent_presentations

# Set page configuration
st.set_page_config(
    page_title="Metrics Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dashboard header with presentation selector
col_title, col_selector = st.columns([2, 1])

with col_title:
    st.title("📊 Metrics Dashboard")

user_id = 2992027
recent_presentations = get_recent_presentations(user_id)

with col_selector:
    st.markdown("")  # Add spacing to align with title

    # Create options for selectbox
    presentation_options = []
    for _, row in recent_presentations.iterrows():
        presentation_options.append({
            'id': row['Id'],
            'title': row['Title'],
            'last_answered': row['Last Answered At']
        })

    # Default selection (first presentation)
    default_presentation = presentation_options[0] if presentation_options else None

    selected_presentation = st.selectbox(
        "Select Presentation:",
        options=presentation_options,
        format_func=lambda x: f"{x['title'][:50]}{'...' if len(x['title']) > 50 else ''}",
        index=0 if presentation_options else None,
        key="selected_presentation"
    )

    if selected_presentation:
        st.caption(f"Last activity: {selected_presentation['last_answered']}")

# Store selected presentation ID for use throughout the dashboard
presentation_id = selected_presentation['id'] if selected_presentation else None


def st_show_sub_header_grey_text(text: str):
    st.markdown(f'<p style="color: #666666; font-size: 14px; margin-top: -10px;">{text}</p>', unsafe_allow_html=True)

# Tab navigation
# tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Slides", "Participant", "Trends", "Show AI Insights"])
tab1, tab2, tab3 = st.tabs(["Overview", "Slides", "Participant"])

with tab1:
    if presentation_id:

        # prez_data = PresentationData(presentation_id)
        prez_data = PresentationDataSQL(presentation_id)

        # Get real data for the selected presentation
        total_joined = prez_data.get_total_participants_joined()
        total_submitted = prez_data.get_total_participants_submitted()

        # Calculate engagement rate
        engagement_rate = prez_data.get_engagement_rate()

        # Create 4 columns for the metric cards
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric(
                label="Engagement Rate",
                value=f"{engagement_rate:.1f}%"
            )
            st_show_sub_header_grey_text(f"{total_submitted} of {total_joined} participants submit answers")


        average_response_time = prez_data.get_average_response_time()
        with col2:
            st.metric(
                label="Average Response Time",
                value=f"{average_response_time:.1f}s"
            )
            st_show_sub_header_grey_text("Across all answers")


        most_engaging_slide = prez_data.get_most_engaging_slide()
        with col3:
            st.metric(
                label="Most engaging slide",
                value=f"{most_engaging_slide['Engagement Rate']:.1f}%"
            )
            st_show_sub_header_grey_text(f'Title: {most_engaging_slide["Slide Title"]}')


        total_submissions = prez_data.get_total_submissions()
        submission_ratio = prez_data.get_submission_ratio()
        with col4:
            st.metric(
                label="Total Submissions",
                value=f"{total_submissions:.0f}"
            )
            st_show_sub_header_grey_text(f"{submission_ratio:.1f} per participant")

        low_engagement_threshold = 20 # in percent
        slides_need_attention_count = prez_data.get_slides_need_attention_count(low_engagement_threshold)
        with col5:
            st.metric(
                label="Slide needs attention",
                value=f"{slides_need_attention_count}"
            )
            st_show_sub_header_grey_text(f"<60% engagement")
    else:
        st.warning("Please select a presentation to view metrics.")

    # Add some spacing
    st.markdown("---")

    # Slide Performance Overview Section with inline badges
    col_title, col_badges = st.columns([2, 1])

    with col_title:
        st.markdown("## Slide Performance Overview")
        st.markdown("*Engagement rates, response times, and participation metrics*")

    total_slides_count = prez_data.get_total_slides_count()
    with col_badges:
        st.markdown("")  # Add some spacing to align with title
        st.markdown(
            '<div style="text-align: right; margin-top: 10px;">'
            f'<span style="background-color: #4CAF50; color: white; padding: 4px 12px; border-radius: 15px; font-size: 14px; margin-right: 8px;">{total_slides_count} Slides Total</span>'
            f'<span style="background-color: #F44336; color: white; padding: 4px 12px; border-radius: 15px; font-size: 14px;">{slides_need_attention_count} Need Attention</span>'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    slide_stats_df = prez_data.get_slides_engagement_stats()

    # Dynamic slide expanders from dataframe
    for index, slide in slide_stats_df.iterrows():
        slide_index = index + 1  # Use 1-based index instead of slide ID
        slide_title = slide['Slide Title']
        slide_type = slide['Slide Type']
        participants = int(slide['Participant Id'])
        avg_time = slide['Answer Time Seconds']
        engagement_rate = slide['Engagement Rate']

        # Determine engagement status and color
        if engagement_rate >= 90:
            status = "Excellent"
            status_color = "normal"
        elif engagement_rate >= 80:
            status = "Good"
            status_color = "normal"
        elif engagement_rate >= 60:
            status = "Attention"
            status_color = "inverse"
        else:
            status = "Needs Work"
            status_color = "inverse"

        # Create expander with slide information and type bubble
        expander_header = f"**Slide {slide_index}: {slide_title}** | {slide_type}"
        with st.expander(expander_header, expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Participants", f"{participants}/{total_joined}")
            with col2:
                st.metric("💬 Submissions", f"{participants}")
            with col3:
                st.metric("⏱️ Avg Time", f"{avg_time:.1f}s")
            with col4:
                st.metric("📊 Engagement", f"{engagement_rate:.1f}%", delta=status, delta_color=status_color)

with tab2:
    if presentation_id:
        prez_data_tab2 = PresentationData(presentation_id)
        slide_stats_df_tab2 = prez_data_tab2.get_slides_engagement_stats()
        total_joined_tab2 = prez_data_tab2.get_total_participants_joined()

        # Header with back button
        col_back, col_title = st.columns([1, 4])
        with col_back:
            # Create a clickable back button using HTML/JavaScript
            st.markdown("""
                <script>
                function goBackToDashboard() {
                    // Find the Overview tab and click it
                    const tabs = document.querySelectorAll('[data-testid="stTabs"] button');
                    if (tabs.length > 0) {
                        tabs[0].click(); // Click the first tab (Overview)
                    }
                }
                </script>
                <button onclick="goBackToDashboard()" style="
                    background: none;
                    border: none;
                    color: #666;
                    cursor: pointer;
                    font-size: 14px;
                    padding: 5px 0;
                    text-decoration: none;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                ">
                    ← Back to Dashboard
                </button>
            """, unsafe_allow_html=True)
        with col_title:
            st.markdown("## Slides Performance")
            total_slides_tab2 = len(slide_stats_df_tab2)
            st.markdown(f"*Performance metrics for all {total_slides_tab2} slides in this session*")

        st.markdown("---")

        # Calculate aggregated metrics
        avg_engagement = slide_stats_df_tab2['Engagement Rate'].mean()
        avg_participation = (slide_stats_df_tab2['Participant Id'].sum() / total_joined_tab2) / len(slide_stats_df_tab2) * 100
        avg_response_time = slide_stats_df_tab2['Answer Time Seconds'].mean()
        slides_need_attention = len(slide_stats_df_tab2[slide_stats_df_tab2['Engagement Rate'] < 60])

        # Top 4 metric cards with real data
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="📊 Avg Engagement",
                value=f"{avg_engagement:.0f}%"
            )
            st_show_sub_header_grey_text("Across all slides")

        with col2:
            st.metric(
                label="👥 Avg Participation",
                value=f"{avg_participation:.0f}%"
            )
            st_show_sub_header_grey_text("Average per slide")

        with col3:
            st.metric(
                label="⏱️ Avg Response Time",
                value=f"{avg_response_time:.1f}s"
            )
            st_show_sub_header_grey_text("Across all answers")

        with col4:
            st.metric(
                label="⚠️ Need Attention",
                value=f"{slides_need_attention}"
            )
            st_show_sub_header_grey_text("<60% engagement")

        st.markdown("<br>", unsafe_allow_html=True)

        # Search control
        search_term = st.text_input("🔍", placeholder="Search slides...", label_visibility="collapsed", key="slides_search")

        st.markdown("---")

        # Slide performance table
        st.markdown("### Slide Performance Details")

        # Get formatted table data from warehouse
        all_table_data = prez_data_tab2.get_slides_performance_table()

        # Filter table data based on search term
        table_data = []
        if search_term:
            for row in all_table_data.iterrows():
                if search_term.lower() in row['Slide'].lower():
                    table_data.append(row)
        else:
            table_data = all_table_data

        # Display table
        if table_data:
            import pandas as pd
            # df_display = pd.DataFrame(table_data)
            # st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.dataframe(all_table_data)
        else:
            st.info("No slides found matching your search criteria.")
    else:
        st.warning("Please select a presentation to view slide performance details.")

with tab3:
    if presentation_id:
        prez_data_tab3 = PresentationData(presentation_id)

        # Header with back button
        col_back, col_title = st.columns([1, 4])
        with col_back:
            # Create a clickable back button using HTML/JavaScript
            st.markdown("""
                <script>
                function goBackToDashboard() {
                    // Find the Overview tab and click it
                    const tabs = document.querySelectorAll('[data-testid="stTabs"] button');
                    if (tabs.length > 0) {
                        tabs[0].click(); // Click the first tab (Overview)
                    }
                }
                </script>
                <button onclick="goBackToDashboard()" style="
                    background: none;
                    border: none;
                    color: #666;
                    cursor: pointer;
                    font-size: 14px;
                    padding: 5px 0;
                    text-decoration: none;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                ">
                    ← Back to Dashboard
                </button>
            """, unsafe_allow_html=True)
        with col_title:
            st.markdown("## Participant Performance")
            total_participants = prez_data_tab3.total_participants
            st.markdown(f"*Individual performance metrics for all {total_participants} participants*")

        st.markdown("---")

        # Get summary metrics
        summary_metrics = prez_data_tab3.get_participant_engagement_summary()

        # Top 4 metric cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="👥 Active Participants",
                value=f"{summary_metrics['active_participants']}"
            )
            st_show_sub_header_grey_text("≥90% response rate")

        with col2:
            st.metric(
                label="🎯 Avg Response Rate",
                value=f"{summary_metrics['avg_response_rate']:.0f}%"
            )
            st_show_sub_header_grey_text("Average across all participants")

        with col3:
            st.metric(
                label="⏱️ Avg Response Time",
                value=f"{summary_metrics['avg_response_time']:.1f}s"
            )
            st_show_sub_header_grey_text("Average across all answers")

        with col4:
            st.metric(
                label="💬 Total Q&A Questions",
                value=f"{summary_metrics['total_qa_questions']}"
            )
            st_show_sub_header_grey_text("Interactive slides")

        st.markdown("<br>", unsafe_allow_html=True)

        # Search and sort controls
        col_search, col_sort = st.columns([2, 1])

        with col_search:
            search_term = st.text_input("🔍", placeholder="Search participants...", label_visibility="collapsed", key="participants_search")

        with col_sort:
            sort_options = ["Response Rate", "Accuracy", "Response Time"]
            sort_by = st.selectbox("Sort by:", options=sort_options, key="participants_sort")

        st.markdown("---")

        # Participant performance table
        st.markdown("### Participant Performance Details")

        # Get formatted table data from warehouse
        all_table_data = prez_data_tab3.get_participant_performance_table()

        # Filter table data based on search term
        table_data = []
        if search_term:
            for row in all_table_data:
                if (search_term.lower() in row['Participant'].lower() or
                    search_term.lower() in row['Email'].lower()):
                    table_data.append(row)
        else:
            table_data = all_table_data

        # Sort the data based on selected sort option
        if table_data:
            if sort_by == "Response Rate":
                table_data.sort(key=lambda x: float(x['Response Rate'].split('%')[0]), reverse=True)
            elif sort_by == "Accuracy":
                table_data.sort(key=lambda x: float(x['Accuracy'].split('%')[0]) if x['Accuracy'] != "N/A" else 0, reverse=True)
            elif sort_by == "Response Time":
                table_data.sort(key=lambda x: float(x['Avg Response Time'].split('s')[0]))

        # Display table
        if table_data:
            import pandas as pd
            df_display = pd.DataFrame(table_data)

            # Style the dataframe for better display
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Participant": st.column_config.TextColumn("Participant", width="medium"),
                    "Email": st.column_config.TextColumn("Email", width="medium"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Response Rate": st.column_config.TextColumn("Response Rate", width="medium"),
                    "Accuracy": st.column_config.TextColumn("Accuracy", width="small"),
                    "Avg Response Time": st.column_config.TextColumn("Avg Response Time", width="medium"),
                    "Q&A Questions": st.column_config.NumberColumn("Q&A Questions", width="small"),
                    "Most/Least Engaged": st.column_config.TextColumn("Most/Least Engaged", width="medium"),
                    "Session Time": st.column_config.TextColumn("Session Time", width="medium")
                }
            )
        else:
            st.info("No participants found matching your search criteria.")
    else:
        st.warning("Please select a presentation to view participant performance details.")

# with tab4:
#     st.markdown("## 📈 Trends Dashboard")
#     st.info("Historical trends and performance over time will be displayed here.")
#     st.markdown("### Coming Soon")
#     st.markdown("- Time-series engagement analysis")
#     st.markdown("- Comparative performance metrics")
#     st.markdown("- Seasonal trends")

with st.sidebar:
    # Page configuration
    st.set_page_config(
        layout="wide"
    )

    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    agent = PresentationAgent(presentation_id=presentation_id)


    # Chat interface
    st.markdown("### Chat with your Data")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                display_structured_response(message['content'])
            else:
                st.markdown(message['content'])



    # Chat input
    if prompt := st.chat_input("Ask me anything about your data..."):
        st_process_user_prompt(agent, prompt)

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
            "What are the trending topics in open-ended responses?"
        ]

        for query in example_queries:
            if st.button(f"Try: {query}", key=f"example_{hash(query)}"):
                st_process_user_prompt(agent, query)

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