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

        # Create expander with slide information using index instead of slide ID
        with st.expander(f"**Slide {slide_index}: {slide_title}**", expanded=False):
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
    # Header with back button (simulated)
    col_back, col_title = st.columns([1, 4])
    with col_back:
        st.markdown("← Back to Dashboard")
    with col_title:
        st.markdown("## Slides Performance")
        st.markdown("*Performance metrics for all 6 slides in this session*")

    st.markdown("---")

    # Top 4 metric cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            '<div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;">'
            '<div style="display: flex; align-items: center; margin-bottom: 10px;">'
            '<div style="background: #4CAF50; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">'
            '<span style="color: white; font-size: 20px;">📊</span>'
            '</div>'
            '<div>'
            '<div style="font-size: 32px; font-weight: bold; color: #333;">77%</div>'
            '<div style="color: #666; font-size: 14px;">Avg Engagement</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            '<div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;">'
            '<div style="display: flex; align-items: center; margin-bottom: 10px;">'
            '<div style="background: #E91E63; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">'
            '<span style="color: white; font-size: 20px;">👥</span>'
            '</div>'
            '<div>'
            '<div style="font-size: 32px; font-weight: bold; color: #333;">73%</div>'
            '<div style="color: #666; font-size: 14px;">Avg Participation</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            '<div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;">'
            '<div style="display: flex; align-items: center; margin-bottom: 10px;">'
            '<div style="background: #9C27B0; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">'
            '<span style="color: white; font-size: 20px;">⏱️</span>'
            '</div>'
            '<div>'
            '<div style="font-size: 32px; font-weight: bold; color: #333;">6.5s</div>'
            '<div style="color: #666; font-size: 14px;">Avg Response Time</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            '<div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;">'
            '<div style="display: flex; align-items: center; margin-bottom: 10px;">'
            '<div style="background: #F44336; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px;">'
            '<span style="color: white; font-size: 20px;">⚠️</span>'
            '</div>'
            '<div>'
            '<div style="font-size: 32px; font-weight: bold; color: #333;">2</div>'
            '<div style="color: #666; font-size: 14px;">Need Attention</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Search and sort controls
    col_search, col_sort = st.columns([2, 1])

    with col_search:
        search_term = st.text_input("🔍", placeholder="Search slides...", label_visibility="collapsed")

    with col_sort:
        st.markdown("**Sort by:**")
        col_sort1, col_sort2, col_sort3 = st.columns(3)
        with col_sort1:
            if st.button("Engagement", key="sort_engagement", type="primary"):
                st.session_state.sort_by = "engagement"
        with col_sort2:
            if st.button("Participation", key="sort_participation"):
                st.session_state.sort_by = "participation"
        with col_sort3:
            if st.button("Response Time", key="sort_response"):
                st.session_state.sort_by = "response_time"

    st.markdown("---")

    # Slide performance table
    st.markdown("### Slide Performance Details")

    # Table header
    st.markdown(
        '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px;">'
        '<div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 20px; font-weight: bold; color: #666;">'
        '<div>Slide</div>'
        '<div>Type</div>'
        '<div>Engagement Rate</div>'
        '<div>Participation</div>'
        '<div>Response Time</div>'
        '<div>Accuracy</div>'
        '<div>Submissions</div>'
        '<div>Status</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Slide 3 - Word Cloud (Best performing)
    st.markdown(
        '<div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 10px;">'
        '<div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 20px; align-items: center;">'
        '<div>'
        '<div style="font-weight: bold; font-size: 16px;">Slide 3:</div>'
        '<div style="color: #666;">Share one word to describe your mood</div>'
        '</div>'
        '<div style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Word Cloud</div>'
        '<div style="color: #4CAF50; font-weight: bold; font-size: 18px;">● 97%</div>'
        '<div>'
        '<div style="font-weight: bold;">94%</div>'
        '<div style="font-size: 12px; color: #666;">168/179</div>'
        '</div>'
        '<div style="font-weight: bold;">2.1s</div>'
        '<div>N/A</div>'
        '<div>'
        '<div style="font-weight: bold;">168</div>'
        '<div style="font-size: 12px; color: #666;">+45 reactions</div>'
        '</div>'
        '<div>'
        '<span style="background: #4CAF50; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Good</span>'
        '<button style="background: #E91E63; color: white; border: none; padding: 6px 12px; border-radius: 4px; margin-left: 8px; font-size: 12px;">📊 View Details</button>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Slide 1 - Multiple Choice
    st.markdown(
        '<div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 10px;">'
        '<div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 20px; align-items: center;">'
        '<div>'
        '<div style="font-weight: bold; font-size: 16px;">Slide 1:</div>'
        '<div style="color: #666;">What is your primary learning goal today?</div>'
        '</div>'
        '<div style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Multiple Choice</div>'
        '<div style="color: #4CAF50; font-weight: bold; font-size: 18px;">● 94%</div>'
        '<div>'
        '<div style="font-weight: bold;">87%</div>'
        '<div style="font-size: 12px; color: #666;">156/179</div>'
        '</div>'
        '<div style="font-weight: bold;">5.2s</div>'
        '<div style="background: #E3F2FD; color: #1976D2; padding: 4px 8px; border-radius: 4px; font-size: 12px;">91%</div>'
        '<div>'
        '<div style="font-weight: bold;">156</div>'
        '<div style="font-size: 12px; color: #666;">+23 reactions</div>'
        '</div>'
        '<div>'
        '<span style="background: #4CAF50; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Good</span>'
        '<button style="background: #E91E63; color: white; border: none; padding: 6px 12px; border-radius: 4px; margin-left: 8px; font-size: 12px;">📊 View Details</button>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Slide 2 - Poll (Needs attention)
    st.markdown(
        '<div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 10px;">'
        '<div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 20px; align-items: center;">'
        '<div>'
        '<div style="font-weight: bold; font-size: 16px;">Slide 2:</div>'
        '<div style="color: #666;">Rate your current confidence level</div>'
        '</div>'
        '<div>'
        '<span style="background: #9C27B0; color: white; padding: 4px 8px; border-radius: 4px; font-size: 10px;">✨ AI Generated</span>'
        '<span style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-left: 4px;">Poll</span>'
        '</div>'
        '<div style="color: #FF9800; font-weight: bold; font-size: 18px;">● 81%</div>'
        '<div>'
        '<div style="font-weight: bold;">81%</div>'
        '<div style="font-size: 12px; color: #666;">145/179</div>'
        '</div>'
        '<div style="font-weight: bold;">3.8s</div>'
        '<div style="background: #FFF3E0; color: #F57C00; padding: 4px 8px; border-radius: 4px; font-size: 12px;">75%</div>'
        '<div>'
        '<div style="font-weight: bold;">145</div>'
        '<div style="font-size: 12px; color: #666;">+18 reactions</div>'
        '</div>'
        '<div>'
        '<span style="background: #FF9800; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Attention</span>'
        '<button style="background: #E91E63; color: white; border: none; padding: 6px 12px; border-radius: 4px; margin-left: 8px; font-size: 12px;">📊 View Details</button>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Slide 4 - Rating Scale (Needs attention)
    st.markdown(
        '<div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 10px;">'
        '<div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 20px; align-items: center;">'
        '<div>'
        '<div style="font-weight: bold; font-size: 16px;">Slide 4:</div>'
        '<div style="color: #666;">How would you rate today\'s session?</div>'
        '</div>'
        '<div style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Rating Scale</div>'
        '<div style="color: #F44336; font-weight: bold; font-size: 18px;">● 79%</div>'
        '<div>'
        '<div style="font-weight: bold;">79%</div>'
        '<div style="font-size: 12px; color: #666;">142/179</div>'
        '</div>'
        '<div style="font-weight: bold;">4.7s</div>'
        '<div style="background: #FFEBEE; color: #D32F2F; padding: 4px 8px; border-radius: 4px; font-size: 12px;">68%</div>'
        '<div>'
        '<div style="font-weight: bold;">142</div>'
        '<div style="font-size: 12px; color: #666;">+12 reactions</div>'
        '</div>'
        '<div>'
        '<span style="background: #F44336; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Needs Work</span>'
        '<button style="background: #E91E63; color: white; border: none; padding: 6px 12px; border-radius: 4px; margin-left: 8px; font-size: 12px;">📊 View Details</button>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Slide 5 - Open Text
    st.markdown(
        '<div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 10px;">'
        '<div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 20px; align-items: center;">'
        '<div>'
        '<div style="font-weight: bold; font-size: 16px;">Slide 5:</div>'
        '<div style="color: #666;">What topic would you like to explore next?</div>'
        '</div>'
        '<div style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Open Text</div>'
        '<div style="color: #FF9800; font-weight: bold; font-size: 18px;">● 75%</div>'
        '<div>'
        '<div style="font-weight: bold;">75%</div>'
        '<div style="font-size: 12px; color: #666;">134/179</div>'
        '</div>'
        '<div style="font-weight: bold;">8.3s</div>'
        '<div>N/A</div>'
        '<div>'
        '<div style="font-weight: bold;">134</div>'
        '<div style="font-size: 12px; color: #666;">+31 reactions</div>'
        '</div>'
        '<div>'
        '<span style="background: #9E9E9E; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Average</span>'
        '<button style="background: #E91E63; color: white; border: none; padding: 6px 12px; border-radius: 4px; margin-left: 8px; font-size: 12px;">📊 View Details</button>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

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