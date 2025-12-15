"""
The list:
    Number of active users/number of licenses purchased (shows you whether people are actually using AhaSlides)
    Ranking of the most active users (sorted by number of live presentations hosted)
    Total events hosted
    Total participants engaged
    Usage trends over weeks/months (number of events, participants, responses submitted...)
    Ranking of the the biggest events (sorted by number of participants)
Questions:
    Will there be filters to further breakdown the data? For example, #4 below (Total participants engaged), can we then filter this to see the number of participants per presentation, over a specified time period? Maybe this is part of #5 and #6, but I just want to clarify what will be possible.
    Will there be an export option to Excel so that we can manipulate and analyze the data ourselves, outside of AHA?
"""
import streamlit as st
import pandas as pd
import altair as alt

from redshift_api import execute, execute_with_columns

# users:
user_ids = [ 3518340, 3531510, 3571556, 3518110, 3528332, 3518177, 3528682, 3517550, 3588998, 3528766, 3648705, 3583921, 3581330, 3744214, 3687594, 3609258, 3609303, 3518008, 3957820, 3963064, 3589123, 3581584, 3576806, 3823694, 3744305, 3553843, 3518220, 3517501, 3553356, 3719355, 3517712, 3528990, 3650855 ]
emails = ['nwb@economical.com', 'etc@economical.com', 'kbc@economical.com', 'y6w@economical.com', 'jdd@economical.com', 'bgm@economical.com', 'rqk@economical.com', 'hdl@economical.com', 'neh@economical.com', 'djb@economical.com', 'eni@economical.com', 'izm@economical.com', 'mea@economical.com', 'lrt@economical.com', 'teh@economical.com', 'kws@economical.com', 'jzs@economical.com', 'nbl@economical.com', 'mnz@economical.com', 's9r@economical.com', 'cis@economical.com', 'rtu@economical.com', 'nmt@economical.com', 'ewi@economical.com', 'udm@economical.com', 'dlb@economical.com', 'mdr@economical.com', 'odq@economical.com', 'cqy@economical.com', 'gbh@economical.com', 'ckk@economical.com', 'mpt@economical.com', 'learning@definity.com']


@st.cache_data(ttl='60m')
def st_get_all_answers():
    sql = f"""
    select * from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    """
    rows, cols = execute_with_columns(sql)
    return pd.DataFrame(rows, columns=cols)


def enrich_user_with_email(df):
    user_id_email_map = {user_id: email for user_id, email in zip(user_ids, emails)}
    if 'user_id' not in df.columns:
        return df
    df['email'] = df['user_id'].map(lambda x: user_id_email_map[x])
    return df


@st.cache_data(ttl='60m')
def st_get_number_of_active_users():
    sql = f"""
   select COUNT(distinct user_id) from aha_report_v5.fact_answers2
where user_id in ({', '.join(map(str, user_ids))})
    """
    rows = execute(sql)
    return rows[0][0]


def get_number_of_active_users(start_date='2025-01-01', end_date='2025-12-30'):
    df = st_get_all_answers()
    df = df[(df['createdat'] >= start_date) & (df['createdat'] <= end_date)]
    return df['user_id'].nunique()



@st.cache_data(ttl='60m')
def st_get_users_stats(start_date='2025-01-01', end_date='2025-12-30'):
    sql = f"""
   select user_id,
        COUNT(distinct presentation_id) as events,
        COUNT(distinct participant_id) as participants,
        COUNT(distinct id) as answers
         from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    and createdat >= '{start_date}'
    and createdat <= '{end_date}'
    group by user_id
    """
    rows, cols = execute_with_columns(sql)
    return pd.DataFrame(rows, columns=cols)


def get_users_stats(start_date='2025-01-01', end_date='2025-12-30'):
    df = st_get_all_answers()
    df = df[(df['createdat'] >= start_date) & (df['createdat'] <= end_date)]
    df = df.groupby('user_id').agg({
        'presentation_id': 'nunique',
        'participant_id': 'nunique',
        'id': 'nunique'
    }).reset_index()
    df.rename(columns={'presentation_id': 'events', 'participant_id': 'participants', 'id': 'answers'}, inplace=True)
    return df


def get_ranking_of_most_active_users(start_date='2025-01-01', end_date='2025-12-30'):
    rank = get_users_stats(start_date=start_date, end_date=end_date)
    rank = enrich_user_with_email(rank)
    rank = rank.sort_values(by='events', ascending=False)
    return rank


def get_total_responses(start_date='2025-01-01', end_date='2025-12-30'):
    df = st_get_all_answers()
    df = df[(df['createdat'] >= start_date) & (df['createdat'] <= end_date)]
    return df['id'].nunique()


@st.cache_data(ttl='60m')
def st_get_total_events_hosted():
    sql = f"""
    select COUNT(distinct presentation_id) from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    """
    rows = execute(sql)
    return rows[0][0]


def get_total_events_hosted(start_date='2025-01-01', end_date='2025-12-30'):
    df = st_get_all_answers()
    df = df[(df['createdat'] >= start_date) & (df['createdat'] <= end_date)]
    return df['presentation_id'].nunique()


@st.cache_data(ttl='60m')
def st_get_total_participants_engaged():
    sql = f"""
    select COUNT(distinct participant_id) from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    """
    rows = execute(sql)
    return rows[0][0]


def get_total_participants_engaged(start_date='2025-01-01', end_date='2025-12-30'):
    df = st_get_all_answers()
    df = df[(df['createdat'] >= start_date) & (df['createdat'] <= end_date)]
    return df['participant_id'].nunique()


@st.cache_data(ttl='60m')
def st_get_usage_trends_over_weeks_months():
    sql = f"""
    select
        date_trunc('week', createdat) as week,
        COUNT(distinct presentation_id) as count,
        COUNT(distinct participant_id) as participants,
        COUNT(distinct id) as answers
    from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    group by date_trunc('week', createdat)
    """
    rows, cols= execute_with_columns(sql)
    df = pd.DataFrame(rows, columns=cols)
    return df



@st.cache_data(ttl='60m')
def st_get_ranking_of_the_biggest_events():
    sql = f"""
    select
        fa.presentation_id,
        dp.title,
        COUNT(distinct participant_id) as count,
        max(fa.createdat) as last_answered_at
         from aha_report_v5.fact_answers2 fa
    join aha_report_v5.dim_presentations dp
    on fa.presentation_id = dp.id
    where dp.user_id in ({', '.join(map(str, user_ids))})
    group by fa.presentation_id, dp.title
    """
    rows, cols= execute_with_columns(sql)
    df = pd.DataFrame(rows, columns=cols)
    return df.sort_values(by='count', ascending=False)


def main():
    # add date range filter
    date_range = st.date_input('Select date range', value=(pd.to_datetime('2025-01-01'), pd.to_datetime('2025-12-31')))

    if len(date_range) < 2 or date_range[0] is None or date_range[1] is None:
        st.write('Please select a date range')
        return

    st.session_state.start_date = pd.to_datetime(date_range[0])
    st.session_state.end_date = pd.to_datetime(date_range[1])

    st.markdown("Here are some quick insights from all your sessions")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with st.container(border=True, height=150):
            active_users_count = get_number_of_active_users(start_date=st.session_state.start_date, end_date=st.session_state.end_date)
            st.metric('Activeted users', active_users_count)
    with col2:
        with st.container(border=True, height=150):
            total_events_hosted = get_total_events_hosted(start_date=st.session_state.start_date, end_date=st.session_state.end_date)
            st.metric('Total events', total_events_hosted)
    with col3:
        with st.container(border=True, height=150):
            participants_engaged = get_total_participants_engaged(start_date=st.session_state.start_date, end_date=st.session_state.end_date)
            st.metric('Total participants', participants_engaged)
    with col4:
        with st.container(border=True, height=150):
            total_responses = get_total_responses(start_date=st.session_state.start_date, end_date=st.session_state.end_date)
            st.metric('Total responses', total_responses)


    # Line chart of usage trend over weeks/months
    usage_trends = st_get_usage_trends_over_weeks_months()
    # filter by date range
    usage_trends = usage_trends[(usage_trends['week'] >= st.session_state.start_date) & (usage_trends['week'] <= st.session_state.end_date)]
    if usage_trends.empty:
        st.write('No data available for the selected date range')
        return
    usage_trends.rename(columns={'week': 'Week', 'count': 'Events', 'participants': 'Participants', 'answers': 'Answers'}, inplace=True)
    st.title('Usage trends over weeks/months')
    # st.line_chart(usage_trends, x='Week', y=['Participants', 'Answers'])
    df_melt = usage_trends.melt("Week", var_name="Metric", value_name="Count")

    chart = (
        alt.Chart(df_melt)
        .mark_line(point=True)
        .encode(
            x="Week:T",
            y=alt.Y("Count:Q", title="Count"),
            color=alt.Color("Metric:N", title="Metric"),
            tooltip=[
                alt.Tooltip("Week:T", title="Week"),
                alt.Tooltip("Metric:N", title="Type"),
                alt.Tooltip("Count:Q", title="Value"),
            ],
        )
        .properties(height=400)
    )
    st.write(chart)

    # Bar chart of ranking of the biggest events
    biggest_events = st_get_ranking_of_the_biggest_events()
    biggest_events = biggest_events[(biggest_events['last_answered_at'] >= st.session_state.start_date) & (biggest_events['last_answered_at'] <= st.session_state.end_date)]
    if biggest_events.empty:
        st.write('No data available for the selected date range')
        return
    biggest_events.rename(columns={'title': 'Event Name', 'count': 'Participants', 'last_answered_at': 'Last Answered At'}, inplace=True)
    st.title('Biggest events')
    st.write(biggest_events.reset_index(drop=True)[['Event Name', 'Participants', 'Last Answered At']])

    # Bar chart of ranking of the most active users
    most_active_users = get_ranking_of_most_active_users(start_date=st.session_state.start_date, end_date=st.session_state.end_date)
    most_active_users.rename(columns={'email': 'Email', 'events': 'Events', 'participants': 'Participants', 'answers': 'Answers'}, inplace=True)
    st.title('Most active users')
    st.write(most_active_users.reset_index(drop=True)[['Email', 'Events', 'Participants', 'Answers']])


if __name__ == "__main__":
    st.logo('https://ahaslides.com/wp-content/uploads/2025/05/logo-full.png')
    st.markdown("""
    <style>
        div[class="stAppDeployButton"] {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)
    st.set_page_config(
        page_title="Definity dashboard",
        page_icon="🚀",
        menu_items={
            'Get Help': 'https://www.google.com',
            'Report a bug': None,
            'About': None
        }
    )
    main()