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
    'Last 30 days': (30, 'W'),
    'Last 3 months': (90, 'W'),
    'Last 6 months': (180, 'M'),
    'All time': (None, 'M'),
}


def generate_period_range(days, granularity, earliest_date=None):
    """Generate complete period range for consistent chart x-axis."""
    end_date = datetime.now()
    if days is None:
        start_date = earliest_date or end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=days)

    date_range = pd.date_range(start=start_date, end=end_date, freq=granularity)
    return pd.PeriodIndex(date_range, freq=granularity).unique().sort_values()


def get_data(time_filter):
    user_ids = tuple(pd.read_csv('cherry/users.csv')['ID'].tolist())

    sessions, presentations, users = parallelize([
        (fetch_sessions_by_users, (user_ids,), {'prefix': 'cherry_'}),
        (fetch_presentations_by_users, (user_ids,), {'prefix': 'cherry_'}),
        (fetch_users, (user_ids,), {'prefix': 'cherry_'}),
    ])

    all_session_ids = tuple(sessions['id'].tolist()) if len(sessions) > 0 else (0,)

    participants, answers = parallelize([
        (fetch_participants_by_presentations, (all_session_ids,), {'prefix': 'cherry_'}),
        (fetch_answers_by_presentations, (all_session_ids,), {'prefix': 'cherry_'}),
    ])

    # Add hosted_by_id to participants and answers via sessions
    session_user_map = sessions.set_index('id')['hosted_by_id']
    participants = participants.assign(hosted_by_id=participants['presentation_id'].map(session_user_map))
    answers = answers.assign(hosted_by_id=answers['presentation_id'].map(session_user_map))

    # Calculate active members (last 30 days) - before time filter
    cutoff_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cutoff_60d = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    active_from_sessions = set(sessions[sessions['hosted_date'] >= cutoff_30d]['hosted_by_id'].tolist())
    active_from_presentations = set(presentations[presentations['createdat_date'] >= cutoff_30d]['user_id'].tolist())
    active_user_ids = active_from_sessions | active_from_presentations
    active_members_count = len(active_user_ids)
    total_members_count = len(users)

    # Previous 30 days (30-60 days ago) for comparison
    prev_active_sessions = set(sessions[(sessions['hosted_date'] >= cutoff_60d) & (sessions['hosted_date'] < cutoff_30d)]['hosted_by_id'].tolist())
    prev_active_presentations = set(presentations[(presentations['createdat_date'] >= cutoff_60d) & (presentations['createdat_date'] < cutoff_30d)]['user_id'].tolist())
    prev_active_members_count = len(prev_active_sessions | prev_active_presentations)
    print('aaa', prev_active_sessions | prev_active_presentations)

    # Calculate last active date for each user (from sessions and presentations)
    last_hosted = pd.to_datetime(sessions.groupby('hosted_by_id')['hosted_date'].max()).rename('last_hosted')
    last_hosted.index.name = 'id'
    last_created = pd.to_datetime(presentations.groupby('user_id')['createdat_date'].max()).rename('last_created')
    last_created.index.name = 'id'
    last_active_df = pd.concat([last_hosted, last_created], axis=1)
    last_active_df['last_active'] = last_active_df[['last_hosted', 'last_created']].max(axis=1)

    # Apply time filter on returned data for cacheability
    days, granularity = TIME_FILTERS[time_filter]
    sessions_unfiltered, participants_unfiltered, answers_unfiltered = sessions, participants, answers
    cutoff = None
    if days is not None:
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        sessions = sessions[sessions['hosted_date'] >= cutoff]
        presentations = presentations[presentations['createdat_date'] >= cutoff]
        filtered_session_ids = set(sessions['id'].tolist())
        participants = participants[
            (participants['presentation_id'].isin(filtered_session_ids)) &
            (participants['createdat_date'] >= cutoff)
        ]
        answers = answers[
            (answers['presentation_id'].isin(filtered_session_ids)) &
            (answers['createdat_date'] >= cutoff)
        ]

    # Overview metrics
    participants_with_answers = answers['participant_id'].nunique()
    total_participants = participants['participant_id'].nunique()
    avg_engagement_rate = participants_with_answers / total_participants if total_participants > 0 else 0

    # Previous period engagement rate (for comparison)
    prev_engagement_rate = None
    if days is not None:
        prev_cutoff = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')
        prev_sessions = sessions_unfiltered[(sessions_unfiltered['hosted_date'] >= prev_cutoff) & (sessions_unfiltered['hosted_date'] < cutoff)]
        prev_session_ids = set(prev_sessions['id'].tolist()) if len(prev_sessions) > 0 else set()
        prev_participants = participants_unfiltered[
            (participants_unfiltered['presentation_id'].isin(prev_session_ids)) &
            (participants_unfiltered['createdat_date'] >= prev_cutoff) &
            (participants_unfiltered['createdat_date'] < cutoff)
        ]
        prev_answers = answers_unfiltered[
            (answers_unfiltered['presentation_id'].isin(prev_session_ids)) &
            (answers_unfiltered['createdat_date'] >= prev_cutoff) &
            (answers_unfiltered['createdat_date'] < cutoff)
        ]
        prev_participants_with_answers = prev_answers['participant_id'].nunique()
        prev_total_participants = prev_participants['participant_id'].nunique()
        prev_engagement_rate = prev_participants_with_answers / prev_total_participants if prev_total_participants > 0 else 0

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
    member_stats = member_stats.merge(last_active_df[['last_active']].reset_index().rename(columns={'index': 'id'}), on='id', how='left')
    member_stats[['presentations', 'sessions']] = member_stats[['presentations', 'sessions']].fillna(0).astype(int)

    # Per-user participants and engagement
    user_participants = participants.groupby('hosted_by_id')['participant_id'].nunique().rename('participants')
    user_engaged = answers.groupby('hosted_by_id')['participant_id'].nunique().rename('engaged')
    user_engagement = pd.concat([user_participants, user_engaged], axis=1).fillna(0)
    user_engagement['engagement'] = (user_engagement['engaged'] / user_engagement['participants'] * 100).fillna(0).round(0).astype(int)

    member_stats = member_stats.merge(user_engagement.reset_index().rename(columns={'hosted_by_id': 'id'}), on='id', how='left')
    member_stats[['participants', 'engagement']] = member_stats[['participants', 'engagement']].fillna(0).astype(int)
    member_stats = member_stats[['name', 'email', 'last_active', 'presentations', 'sessions', 'participants', 'engagement']]

    # Time series for charts - generate complete period range
    all_dates = pd.concat([
        pd.to_datetime(presentations['createdat_date']),
        pd.to_datetime(sessions['hosted_date']),
        pd.to_datetime(participants['createdat_date']),
        pd.to_datetime(answers['createdat_date']),
    ])
    earliest_date = all_dates.min() if len(all_dates) > 0 else None
    all_periods = generate_period_range(days, granularity, earliest_date)

    presentations_ts = presentations.assign(period=pd.to_datetime(presentations['createdat_date']).dt.to_period(granularity)).groupby('period').size().rename('Created presentations')
    sessions_ts = sessions.assign(period=pd.to_datetime(sessions['hosted_date']).dt.to_period(granularity)).groupby('period').size().rename('Hosted events')
    presentation_activity = pd.concat([presentations_ts, sessions_ts], axis=1).reindex(all_periods).fillna(0).astype(int)
    presentation_activity.index.name = 'period'

    participants_ts = participants.assign(period=pd.to_datetime(participants['createdat_date']).dt.to_period(granularity)).groupby('period').size().rename('Participants')
    answers_ts = answers.assign(period=pd.to_datetime(answers['createdat_date']).dt.to_period(granularity)).groupby('period').size().rename('Responses')
    engagement_performance = pd.concat([answers_ts, participants_ts], axis=1).reindex(all_periods).fillna(0).astype(int)
    engagement_performance.index.name = 'period'

    return {
        'avg_engagement_rate': avg_engagement_rate,
        'prev_engagement_rate': prev_engagement_rate,
        'active_members_count': active_members_count,
        'prev_active_members_count': prev_active_members_count,
        'total_members_count': total_members_count,
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
        # Daily: "Jan 15" or "Jan 15 2024"
        date_str = period.strftime('%b %d')
        return date_str if period.year == current_year else f"{date_str} {str(period.year)}"
    elif granularity == 'W':
        # Weekly: "Jan 1" or "Jan 1-24"
        date_str = period.start_time.strftime('%b %d')
        return date_str if period.year == current_year else f"{date_str} {str(period.year)}"
    else:
        # Monthly: "Jan" or "Jan-24"
        month_str = period.strftime('%b')
        return month_str if period.year == current_year else f"{month_str} {str(period.year)}"


def render_dashboard():
    st.markdown("""
    <style>
        div[data-testid="stAppDeployButton"] {
            display: none !important;
        }
        div[data-testid="stDecoration"] {
            display: none !important;
        }
        .st-key-overview-cards .stVerticalBlock {
            gap: 0.25rem !important;
        }
    </style>
    """, unsafe_allow_html=True)
    st.logo('https://ahaslides.com/wp-content/uploads/2025/05/logo-full.png')
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
    overview_card_height = 150
    with st.container(key="overview-cards"):
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True, height=overview_card_height):
                st.markdown('**Active members (last 30 days)**')
                st.markdown(f"<span style='font-size: 2rem; font-weight: 600;'>{data['active_members_count']}</span><span style='font-size: 1.2rem; color: #666;'>/{data['total_members_count']}</span>", unsafe_allow_html=True)
                prev_active = data['prev_active_members_count']
                if prev_active > 0:
                    active_pct_change = (data['active_members_count'] - prev_active) / prev_active * 100
                    delta_color = '#16C49A' if active_pct_change >= 0 else '#E85D4A'
                    delta_arrow = '▲' if active_pct_change >= 0 else '▼'
                    st.markdown(f"<span style='color: {delta_color}; font-size: 0.85rem;'>{delta_arrow} {abs(active_pct_change):.0f}%</span> <span style='color: #888; font-size: 0.85rem;'>compared to previous period</span>", unsafe_allow_html=True)
        with col2:
            with st.container(border=True, height=overview_card_height):
                st.markdown('**Avg. engagement rate**')
                st.markdown(f"<span style='font-size: 2rem; font-weight: 600;'>{data['avg_engagement_rate']:.1%}</span>", unsafe_allow_html=True)
                if data['prev_engagement_rate'] is not None and data['prev_engagement_rate'] > 0:
                    eng_pct_change = (data['avg_engagement_rate'] - data['prev_engagement_rate']) / data['prev_engagement_rate'] * 100
                    eng_delta_color = '#16C49A' if eng_pct_change >= 0 else '#E85D4A'
                    eng_delta_arrow = '▲' if eng_pct_change >= 0 else '▼'
                    st.markdown(f"<span style='color: {eng_delta_color}; font-size: 0.85rem;'>{eng_delta_arrow} {abs(eng_pct_change):.1f}%</span> <span style='color: #888; font-size: 0.85rem;'>compared to previous period</span>", unsafe_allow_html=True)
        with col3:
            with st.container(border=True, height=overview_card_height):
                st.markdown('**Most active**')
                for _, row in data['most_active'].iterrows():
                    st.html(f"<div><b>{row['first_name']} {row['last_name']}</b> &nbsp; {int(row['presentations'])} prez, {int(row['sessions'])} sessions</div>")

    # Member statistics
    st.markdown("<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>Member statistics</p>", unsafe_allow_html=True)
    member_stats_display = data['member_stats'].sort_values('sessions', ascending=False).rename(columns={
        'name': 'Member',
        'email': 'Email',
        'last_active': 'Last active',
        'presentations': 'Presentations',
        'sessions': 'Hosted',
        'participants': 'Participants',
        'engagement': 'Engagement %',
    })
    st.dataframe(member_stats_display, use_container_width=True, hide_index=True, column_config={
        'Member': st.column_config.Column(width='medium'),
        'Email': st.column_config.Column(width='medium'),
        'Last active': st.column_config.DateColumn(width='small', format='DD MMM YYYY'),
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
