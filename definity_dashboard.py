"""
The list:
    Number of activated users/number of licenses purchased (shows you whether people are actually using AhaSlides)
    Ranking of the most activate users (sorted by number of live presentations hosted)
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

def enrich_user_with_email(df):
    user_id_email_map = {user_id: email for user_id, email in zip(user_ids, emails)}
    if 'user_id' not in df.columns:
        return df
    df['email'] = df['user_id'].map(lambda x: user_id_email_map[x])
    return df

@st.cache_data(ttl='60m')
def get_number_of_activated_users():
    sql = f"""
   select COUNT(distinct user_id) from aha_report_v5.fact_answers2
where user_id in ({', '.join(map(str, user_ids))})
    """
    rows = execute(sql)
    return rows[0][0]


@st.cache_data(ttl='60m')
def st_get_users_stats():
    sql = f"""
   select user_id,
        COUNT(distinct presentation_id) as events,
        COUNT(distinct participant_id) as participants,
        COUNT(distinct id) as answers
         from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    group by user_id
    """
    rows, cols = execute_with_columns(sql)
    return pd.DataFrame(rows, columns=cols)


def get_ranking_of_most_activate_users():
    rank = st_get_users_stats()
    rank = enrich_user_with_email(rank)
    rank = rank.sort_values(by='events', ascending=False)
    return rank


@st.cache_data(ttl='60m')
def st_get_total_events_hosted():
    sql = f"""
    select COUNT(distinct presentation_id) from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    """
    rows = execute(sql)
    return rows[0][0]


@st.cache_data(ttl='60m')
def st_get_total_participants_engaged():
    sql = f"""
    select COUNT(distinct participant_id) from aha_report_v5.fact_answers2
    where user_id in ({', '.join(map(str, user_ids))})
    """
    rows = execute(sql)
    return rows[0][0]


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
    st.markdown("Here are some quick insights from all your sessions:")
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True, height=150):
            activated_users_count = get_number_of_activated_users()
            st.metric('Activeted users', activated_users_count)
    with col2:
        with st.container(border=True, height=150):
            total_events_hosted = st_get_total_events_hosted()
            st.metric('Total events', total_events_hosted)
    with col3:
        with st.container(border=True, height=150):
            participants_engaged = st_get_total_participants_engaged()
            st.metric('Total participants', participants_engaged)

    # Line chart of usage trend over weeks/months
    usage_trends = st_get_usage_trends_over_weeks_months()
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
    biggest_events.rename(columns={'title': 'Event Name', 'count': 'Participants', 'last_answered_at': 'Last Answered At'}, inplace=True)
    st.title('Biggest events')
    st.write(biggest_events.reset_index(drop=True)[['Event Name', 'Participants', 'Last Answered At']])

    # Bar chart of ranking of the most activate users
    most_activate_users = get_ranking_of_most_activate_users()
    most_activate_users.rename(columns={'email': 'Email', 'events': 'Events', 'participants': 'Participants', 'answers': 'Answers'}, inplace=True)
    st.title('Most activate users')
    st.write(most_activate_users.reset_index(drop=True)[['Email', 'Events', 'Participants', 'Answers']])

if __name__ == "__main__":
    main()