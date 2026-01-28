import time
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from fetch_data import (
    fetch_sessions_by_users,
    fetch_users,
    fetch_presentations_by_users,
    fetch_participants_by_users,
    fetch_answers_by_users,
    fetch_presentations_by_ids,
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
    end_date = datetime.now()
    start_date = (earliest_date or end_date - timedelta(days=365)) if days is None else end_date - timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq=granularity)
    return pd.PeriodIndex(date_range, freq=granularity).unique().sort_values()


def build_events_table(participants, answers, presentation_names, sessions, users):
    """Build per-session event stats used by both biggest and most engaging tables."""
    participant_counts = participants.groupby('presentation_id')['participant_id'].nunique().rename('participant_count')
    valid_participant_keys = participants[['presentation_id', 'participant_id']].drop_duplicates()
    valid_answers = answers.merge(valid_participant_keys, on=['presentation_id', 'participant_id'])
    responding_counts = valid_answers.groupby('presentation_id')['participant_id'].nunique().rename('responding_participants')
    response_counts = valid_answers.groupby('presentation_id').size().rename('total_responses')

    events = pd.concat([participant_counts, responding_counts, response_counts], axis=1).fillna(0).reset_index()

    session_info = sessions[['id', 'hosted_by_id', 'hosted_date']].rename(columns={'id': 'presentation_id'})
    events = events.merge(session_info, on='presentation_id', how='left')
    events = events.merge(
        presentation_names[['id', 'title']].rename(columns={'id': 'presentation_id'}),
        on='presentation_id', how='left',
    )
    events = events.merge(
        users[['id', 'first_name', 'last_name']].assign(
            hosted_by_name=lambda df: df['first_name'] + ' ' + df['last_name']
        )[['id', 'hosted_by_name']].rename(columns={'id': 'hosted_by_id'}),
        on='hosted_by_id', how='left',
    )
    events['engagement_pct'] = (events['responding_participants'] / events['participant_count'] * 100).fillna(0).round(0).astype(int)
    events['submissions_per_participant'] = (events['total_responses'] / events['participant_count']).fillna(0)
    return events


def get_data(time_filter):
    user_ids = tuple(pd.read_csv('data_dump/abu_dhabi_university_users.csv')['id'].tolist())

    sessions, presentations, users = parallelize([
        (fetch_sessions_by_users, (user_ids,), {'prefix': 'adu_'}),
        (fetch_presentations_by_users, (user_ids,), {'prefix': 'adu_'}),
        (fetch_users, (user_ids,), {'prefix': 'adu_'}),
    ])

    all_session_ids = tuple(sessions['id'].tolist()) if len(sessions) > 0 else (0,)

    participants, answers, presentation_names = parallelize([
        (fetch_participants_by_users, (user_ids,), {'prefix': 'adu_'}),
        (fetch_answers_by_users, (user_ids,), {'prefix': 'adu_'}),
        (fetch_presentations_by_ids, (all_session_ids,), {'prefix': 'adu_'}),
    ])

    # Add hosted_by_id to participants and answers via sessions
    session_user_map = sessions.set_index('id')['hosted_by_id']
    participants = participants.assign(hosted_by_id=participants['presentation_id'].map(session_user_map))
    answers = answers.assign(hosted_by_id=answers['presentation_id'].map(session_user_map))

    # Active members (last 30 days) - before time filter
    cutoff_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cutoff_60d = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    active_from_sessions = set(sessions[sessions['hosted_date'] >= cutoff_30d]['hosted_by_id'].tolist())
    active_from_presentations = set(presentations[presentations['createdat_date'] >= cutoff_30d]['user_id'].tolist())
    active_members_count = len(active_from_sessions | active_from_presentations)
    total_members_count = len(users)

    # Previous 30 days for comparison
    prev_active_sessions = set(sessions[(sessions['hosted_date'] >= cutoff_60d) & (sessions['hosted_date'] < cutoff_30d)]['hosted_by_id'].tolist())
    prev_active_presentations = set(presentations[(presentations['createdat_date'] >= cutoff_60d) & (presentations['createdat_date'] < cutoff_30d)]['user_id'].tolist())
    prev_active_members_count = len(prev_active_sessions | prev_active_presentations)

    # Last active date per user
    last_hosted = pd.to_datetime(sessions.groupby('hosted_by_id')['hosted_date'].max()).rename('last_hosted')
    last_hosted.index.name = 'id'
    last_created = pd.to_datetime(presentations.groupby('user_id')['createdat_date'].max()).rename('last_created')
    last_created.index.name = 'id'
    last_active_df = pd.concat([last_hosted, last_created], axis=1)
    last_active_df['last_active'] = last_active_df[['last_hosted', 'last_created']].max(axis=1)

    # Apply time filter
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

    # Previous period engagement rate
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
        prev_total_participants = prev_participants['participant_id'].nunique()
        prev_engagement_rate = prev_answers['participant_id'].nunique() / prev_total_participants if prev_total_participants > 0 else 0

    # Most active users (top 3)
    prez_counts = presentations.groupby('user_id').size().rename('presentations')
    session_counts = sessions.groupby('hosted_by_id').size().rename('sessions')
    user_activity = pd.concat([prez_counts, session_counts], axis=1).fillna(0)
    user_activity['total'] = user_activity['presentations'] + user_activity['sessions']
    most_active = user_activity.nlargest(3, 'total').reset_index().rename(columns={'index': 'user_id'})
    most_active = most_active.merge(users[['id', 'first_name', 'last_name']], left_on='user_id', right_on='id', how='left')

    # Member stats (top 100 by total activity)
    member_stats = users.copy()
    member_stats['name'] = member_stats['first_name'] + ' ' + member_stats['last_name']
    member_stats = member_stats.merge(prez_counts.reset_index().rename(columns={'user_id': 'id'}), on='id', how='left')
    member_stats = member_stats.merge(session_counts.reset_index().rename(columns={'hosted_by_id': 'id'}), on='id', how='left')
    member_stats = member_stats.merge(last_active_df[['last_active']].reset_index().rename(columns={'index': 'id'}), on='id', how='left')
    member_stats[['presentations', 'sessions']] = member_stats[['presentations', 'sessions']].fillna(0).astype(int)
    member_stats['total'] = member_stats['presentations'] + member_stats['sessions']

    valid_participant_keys = participants[['presentation_id', 'participant_id']].drop_duplicates()
    valid_answers = answers.merge(valid_participant_keys, on=['presentation_id', 'participant_id'])
    user_participants = participants.groupby('hosted_by_id')['participant_id'].nunique().rename('participants')
    user_engaged = valid_answers.groupby('hosted_by_id')['participant_id'].nunique().rename('engaged')
    user_engagement = pd.concat([user_participants, user_engaged], axis=1).fillna(0)
    user_engagement['engagement'] = (user_engagement['engaged'] / user_engagement['participants'] * 100).fillna(0).round(0).astype(int)

    member_stats = member_stats.merge(user_engagement.reset_index().rename(columns={'hosted_by_id': 'id'}), on='id', how='left')
    member_stats[['participants', 'engagement']] = member_stats[['participants', 'engagement']].fillna(0).astype(int)
    member_stats = member_stats.nlargest(100, 'total').sort_values('presentations', ascending=False)
    member_stats = member_stats[['name', 'email', 'last_active', 'presentations', 'sessions', 'participants', 'engagement']]

    # Events tables
    events = build_events_table(participants, answers, presentation_names, sessions, users)
    biggest_events = events.nlargest(20, 'total_responses')
    most_engaging_events = events.nlargest(20, 'submissions_per_participant')

    # Time series for charts
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
        'biggest_events': biggest_events,
        'most_engaging_events': most_engaging_events,
        'presentation_activity': presentation_activity,
        'engagement_performance': engagement_performance,
        'granularity': granularity,
    }


def format_period(period, granularity):
    current_year = datetime.now().year
    if granularity == 'D':
        date_str = period.strftime('%b %d')
        return date_str if period.year == current_year else f"{date_str} {str(period.year)}"
    elif granularity == 'W':
        date_str = period.start_time.strftime('%b %d')
        return date_str if period.year == current_year else f"{date_str} {str(period.year)}"
    else:
        month_str = period.strftime('%b')
        return month_str if period.year == current_year else f"{month_str} {str(period.year)}"


def render_events_table(events, title):
    st.markdown(f"<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>{title}</p>", unsafe_allow_html=True)
    display = events[['presentation_id', 'title', 'hosted_date', 'hosted_by_name', 'participant_count', 'total_responses', 'engagement_pct']].rename(columns={
        'presentation_id': 'Presentation ID',
        'title': 'Presentation Title',
        'hosted_date': 'Hosted At',
        'hosted_by_name': 'Hosted By',
        'participant_count': 'Participants',
        'total_responses': 'Responses',
        'engagement_pct': 'Engagement %',
    })
    st.dataframe(display, use_container_width=True, hide_index=True, column_config={
        'Presentation ID': st.column_config.Column(width='small'),
        'Presentation Title': st.column_config.Column(width='large'),
        'Hosted At': st.column_config.DateColumn(width='small', format='DD MMM YYYY'),
        'Hosted By': st.column_config.Column(width='medium'),
        'Participants': st.column_config.Column(width='small'),
        'Responses': st.column_config.Column(width='small'),
        'Engagement %': st.column_config.NumberColumn(width='small', format='%d%%'),
    })


def render_dashboard():
    st.set_page_config(layout="wide")
    st.title('Abu Dhabi University Analytics')
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

    with st.spinner('Loading data...'):
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
                st.markdown('**Most active (top 3)**')
                for _, row in data['most_active'].iterrows():
                    st.html(f"<div><b>{row['first_name']} {row['last_name']}</b> &nbsp; {int(row['presentations'])} prez, {int(row['sessions'])} sessions</div>")

    # Member statistics (top 100)
    st.markdown("<p style='font-size: 18px; font-weight: 600; margin-bottom: 0.5rem;'>Most active members</p>", unsafe_allow_html=True)
    member_stats_display = data['member_stats'].rename(columns={
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

    # 20 Biggest Events
    render_events_table(data['biggest_events'], 'Biggest Events (by number of responses)')

    # 20 Most Engaging Events
    render_events_table(data['most_engaging_events'], 'Most Engaging Events (no. responses / no. participants)')

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
