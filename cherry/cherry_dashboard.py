from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

from fetch_data import (
    fetch_sessions_by_users,
    fetch_users,
    fetch_presentations_by_users,
    fetch_participants_by_presentations,
    fetch_answers_by_presentations,
)
from utils import parallelize

TIME_FILTERS = {
    'Last 7 days': (7, 'D'),
    'Last 30 days': (30, 'D'),
    'Last 3 months': (90, 'W'),
    'Last 6 months': (180, 'M'),
    'All time': (None, 'M'),
}


def get_data(time_filter):
    user_ids = tuple(pd.read_csv('cherry/users.csv')['ID'].tolist())

    sessions, presentations, users = parallelize([
        (fetch_sessions_by_users, (user_ids,), {'prefix': 'cherry_'}),
        (fetch_presentations_by_users, (user_ids,), {'prefix': 'cherry_'}),
        (fetch_users, (user_ids,), {'prefix': 'cherry_'}),
    ])

    # Apply time filter
    days, granularity = TIME_FILTERS.get(time_filter)
    if days is not None:
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        sessions = sessions[sessions['hosted_date'] >= cutoff]
        presentations = presentations[presentations['createdat_date'] >= cutoff]

    session_ids = tuple(sessions['id'].tolist()) if len(sessions) > 0 else (0,)

    participants, answers = parallelize([
        (fetch_participants_by_presentations, (session_ids,), {'prefix': 'cherry_'}),
        (fetch_answers_by_presentations, (session_ids,), {'prefix': 'cherry_'}),
    ])

    # Add hosted_by_id to participants and answers via sessions
    session_user_map = sessions.set_index('id')['hosted_by_id']
    participants = participants.assign(hosted_by_id=participants['presentation_id'].map(session_user_map))
    answers = answers.assign(hosted_by_id=answers['presentation_id'].map(session_user_map))

    # Overview metrics
    participants_with_answers = answers['participant_id'].nunique()
    total_participants = participants['participant_id'].nunique()
    avg_engagement_rate = participants_with_answers / total_participants if total_participants > 0 else 0

    # Most active users (by presentations + sessions)
    prez_counts = presentations.groupby('user_id').size().rename('presentations')
    session_counts = sessions.groupby('hosted_by_id').size().rename('sessions')
    user_activity = pd.concat([prez_counts, session_counts], axis=1).fillna(0)
    user_activity['total'] = user_activity['presentations'] + user_activity['sessions']
    most_active = user_activity.nlargest(2, 'total').reset_index().rename(columns={'index': 'user_id'})
    most_active = most_active.merge(users[['id', 'first_name', 'last_name']], left_on='user_id', right_on='id', how='left')

    # Member stats
    member_stats = users.copy()
    member_stats['name'] = member_stats['first_name'] + ' ' + member_stats['last_name']
    member_stats = member_stats.merge(prez_counts.reset_index().rename(columns={'user_id': 'id'}), on='id', how='left')
    member_stats = member_stats.merge(session_counts.reset_index().rename(columns={'hosted_by_id': 'id'}), on='id', how='left')
    member_stats[['presentations', 'sessions']] = member_stats[['presentations', 'sessions']].fillna(0).astype(int)

    # Per-user participants and engagement
    user_participants = participants.groupby('hosted_by_id')['participant_id'].nunique().rename('participants')
    user_engaged = answers.groupby('hosted_by_id')['participant_id'].nunique().rename('engaged')
    user_engagement = pd.concat([user_participants, user_engaged], axis=1).fillna(0)
    user_engagement['engagement'] = (user_engagement['engaged'] / user_engagement['participants'] * 100).fillna(0).round(0).astype(int)

    member_stats = member_stats.merge(user_engagement.reset_index().rename(columns={'hosted_by_id': 'id'}), on='id', how='left')
    member_stats[['participants', 'engagement']] = member_stats[['participants', 'engagement']].fillna(0).astype(int)
    member_stats = member_stats[['name', 'email', 'presentations', 'sessions', 'participants', 'engagement']]

    # Time series for charts
    presentations_ts = presentations.assign(period=pd.to_datetime(presentations['createdat_date']).dt.to_period(granularity)).groupby('period').size().rename('Created presentations')
    sessions_ts = sessions.assign(period=pd.to_datetime(sessions['hosted_date']).dt.to_period(granularity)).groupby('period').size().rename('Hosted events')
    presentation_activity = pd.concat([presentations_ts, sessions_ts], axis=1).fillna(0).astype(int)

    participants_ts = participants.assign(period=pd.to_datetime(participants['createdat_date']).dt.to_period(granularity)).groupby('period').size().rename('Participants')
    answers_ts = answers.assign(period=pd.to_datetime(answers['createdat_date']).dt.to_period(granularity)).groupby('period').size().rename('Responses')
    engagement_performance = pd.concat([answers_ts, participants_ts], axis=1).fillna(0).astype(int)

    return {
        'avg_engagement_rate': avg_engagement_rate,
        'most_active': most_active,
        'member_stats': member_stats,
        'presentation_activity': presentation_activity,
        'engagement_performance': engagement_performance,
        'granularity': granularity,
    }


def format_period(period, granularity):
    """Format period based on granularity."""
    current_year = datetime.now().year
    if granularity == 'D':
        # Daily: "Jan 15" or "Jan 15-24"
        date_str = period.strftime('%b %d')
        return date_str if period.year == current_year else f"{date_str}-{str(period.year)[-2:]}"
    elif granularity == 'W':
        # Weekly: "Jan 1" or "Jan 1-24"
        date_str = period.start_time.strftime('%b %d')
        return date_str if period.year == current_year else f"{date_str}-{str(period.year)[-2:]}"
    else:
        # Monthly: "Jan" or "Jan-24"
        month_str = period.strftime('%b')
        return month_str if period.year == current_year else f"{month_str}-{str(period.year)[-2:]}"


def render_dashboard():
    st.header('Analytics', anchor=False)

    # Time filter
    filter_col, _ = st.columns([1, 4])
    with filter_col:
        st.markdown('''<style>
            .st-key-time-filter-select [data-testid="stSelectbox"] > div > div {
                border: 1px solid #ddd !important;
                border-radius: 8px;
                font-size: 14px;
            }
            .st-key-time-filter-select [data-testid="stSelectbox"] input { caret-color: transparent; }
            [data-baseweb="popover"] li { font-size: 14px; }
            [data-baseweb="select"] div { cursor: pointer; }
        </style>''', unsafe_allow_html=True)
        with st.container(key="time-filter-select"):
            time_filter = st.selectbox('Time period', options=list(TIME_FILTERS.keys()), index=4, label_visibility='collapsed')

    data = get_data(time_filter)

    # Overview section
    st.markdown("<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>Overview</p>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    overview_card_height = 160

    with col1:
        with st.container(border=True, height=overview_card_height):
            st.markdown('**Avg. engagement rate**')
            st.markdown(f"<span style='font-size: 2rem; font-weight: 600;'>{data['avg_engagement_rate']:.1%}</span>", unsafe_allow_html=True)

    with col2:
        with st.container(border=True, height=overview_card_height):
            st.markdown('**Most active**')
            for _, row in data['most_active'].iterrows():
                st.html(f"<div><b>{row['first_name']} {row['last_name']}</b> &nbsp; {int(row['presentations'])} presentations, {int(row['sessions'])} sessions</div>")

    # Member statistics
    st.markdown("<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>Member statistics</p>", unsafe_allow_html=True)
    member_stats_display = data['member_stats'].sort_values('sessions', ascending=False).rename(columns={
        'name': 'Member',
        'email': 'Email',
        'presentations': 'Presentations',
        'sessions': 'Hosted',
        'participants': 'Participants',
        'engagement': 'Engagement %',
    })
    st.dataframe(member_stats_display, use_container_width=True, hide_index=True, column_config={
        'Name': st.column_config.Column(width='medium'),
        'Email': st.column_config.Column(width='medium'),
        'Participants': st.column_config.Column(width='small'),
        'Engagement %': st.column_config.NumberColumn(width='small', format='%d%%'),
        'Hosted': st.column_config.Column(width='small'),
        'Presentations': st.column_config.Column(width='small'),
    })

    # Charts
    chart_col1, chart_col2 = st.columns(2)

    granularity = data['granularity']

    with chart_col1:
        with st.container(border=True):
            st.markdown("<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>Presentation activity</p>", unsafe_allow_html=True)
            st.caption('See the total number of presentations your team has created and hosted.')
            prez_df = data['presentation_activity'].reset_index()
            prez_df['period'] = prez_df['period'].apply(lambda p: format_period(p, granularity))
            prez_df = prez_df.melt(id_vars='period', var_name='Type', value_name='Count')
            prez_colors = ['#C47BE4', '#16C49A']
            chart1 = alt.Chart(prez_df).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X('period:N', title=None, axis=alt.Axis(labelAngle=0), sort=None),
                y=alt.Y('Count:Q', title=None, scale=alt.Scale(domain=[0, prez_df['Count'].max() * 1.1])),
                color=alt.Color('Type:N', scale=alt.Scale(range=prez_colors), legend=alt.Legend(orient='bottom', direction='horizontal', title=None)),
            ).properties(height=250).configure_view(strokeWidth=0).configure_axis(grid=True, gridColor='#eee')
            st.altair_chart(chart1, use_container_width=True)

    with chart_col2:
        with st.container(border=True):
            st.markdown("<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>Engagement performance</p>", unsafe_allow_html=True)
            st.caption('Monitor participant numbers and their responses over time.')
            eng_df = data['engagement_performance'].reset_index()
            eng_df['period'] = eng_df['period'].apply(lambda p: format_period(p, granularity))
            eng_df = eng_df.melt(id_vars='period', var_name='Type', value_name='Count')
            eng_colors = ['#FF9068', '#FF4081']
            chart2 = alt.Chart(eng_df).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X('period:N', title=None, axis=alt.Axis(labelAngle=0), sort=None),
                y=alt.Y('Count:Q', title=None, scale=alt.Scale(domain=[0, eng_df['Count'].max() * 1.1])),
                color=alt.Color('Type:N', scale=alt.Scale(range=eng_colors), legend=alt.Legend(orient='bottom', direction='horizontal', title=None)),
            ).properties(height=250).configure_view(strokeWidth=0).configure_axis(grid=True, gridColor='#eee')
            st.altair_chart(chart2, use_container_width=True)


if __name__ == '__main__':
    render_dashboard()
