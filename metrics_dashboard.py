import streamlit as st
from warehouse_v5_repo import PresentationData, get_all_answers_full, get_average_response_time, get_most_engaging_slides, get_recent_presentations, get_total_participants_joined, get_total_participants_submitted, get_total_submissions

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

user_id = 3146502
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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Slides", "Participant", "Trends", "Show AI Insights"])

with tab1:
    if presentation_id:

        prez_data = PresentationData(presentation_id)

        # Get real data for the selected presentation
        total_joined = get_total_participants_joined(presentation_id)
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


        total_submissions = get_total_submissions(presentation_id)
        with col4:
            st.metric(
                label="Total Submissions",
                value=f"{total_submissions.iloc[0]['Total Submissions']:.0f}"
            )
            st_show_sub_header_grey_text(f"{total_submissions.iloc[0]['Submission Ratio']:.1f} per participant")

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
        total_joined_tab2 = get_total_participants_joined(presentation_id)

        # Header with back button (simulated)
        col_back, col_title = st.columns([1, 4])
        with col_back:
            st.markdown("← Back to Dashboard")
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

        # Filter slides based on search term
        filtered_slides = slide_stats_df_tab2.copy()
        if search_term:
            filtered_slides = filtered_slides[filtered_slides['Slide Title'].str.contains(search_term, case=False, na=False)]

        # Prepare data for table display
        table_data = []
        for index, slide in filtered_slides.iterrows():
            slide_index = slide['Slide Order']
            slide_title = slide['Slide Title']
            slide_type = slide['Slide Type']
            participants = int(slide['Participant Id'])
            avg_time = slide['Answer Time Seconds']
            engagement_rate = slide['Engagement Rate']

            # Determine engagement status
            if engagement_rate >= 90:
                status = "🟢 Excellent"
            elif engagement_rate >= 80:
                status = "🟢 Good"
            elif engagement_rate >= 60:
                status = "🟡 Attention"
            else:
                status = "🔴 Needs Work"

            table_data.append({
                "Slide": f"Slide {slide_index}: {slide_title}",
                "Type": slide_type,
                "Engagement Rate": f"{engagement_rate:.1f}%",
                "Participation": f"{(participants/total_joined_tab2*100):.0f}% ({participants}/{total_joined_tab2})",
                "Response Time": f"{avg_time:.1f}s",
                "Submissions": f"{participants}",
                "Status": status
            })

        # Display table
        if table_data:
            import pandas as pd
            df_display = pd.DataFrame(table_data)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("No slides found matching your search criteria.")
    else:
        st.warning("Please select a presentation to view slide performance details.")

with tab3:
    st.markdown("## 👥 Participant Dashboard")
    st.info("Participant engagement patterns and demographics will be displayed here.")
    st.markdown("### Coming Soon")
    st.markdown("- Participant journey tracking")
    st.markdown("- Engagement heatmaps")
    st.markdown("- Demographic breakdowns")

with tab4:
    st.markdown("## 📈 Trends Dashboard")
    st.info("Historical trends and performance over time will be displayed here.")
    st.markdown("### Coming Soon")
    st.markdown("- Time-series engagement analysis")
    st.markdown("- Comparative performance metrics")
    st.markdown("- Seasonal trends")

with tab5:
    st.markdown("## 🤖 AI Insights Dashboard")
    st.info("AI-powered insights and recommendations will be displayed here.")
    st.markdown("### Coming Soon")
    st.markdown("- Automated performance recommendations")
    st.markdown("- Content optimization suggestions")
    st.markdown("- Predictive engagement modeling")