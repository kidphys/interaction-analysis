from redshift_api import execute
import pandas as pd
import json
import ast


def get_presentations_of_user(user_id: str):
    sql = f'SELECT "id", "userid", "name", "createdat" FROM aha_report_x.dim_presentations WHERE userid = {user_id};'
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['id', 'userid', 'name', 'createdat'])


def get_interactions_of_presentation(presentation_id: str):
    # One source of truth
    cols = [
        "Presentationid",
        "Slideid",
        "Slidetitle",
        "Slidetypenormalized",
        "Slideoptions",
        "Slideorder",
        "audience_name",
        "audienceid",
        "correct",
        "Vote",
        "poll_vote",
        "Title",
        "Createdat"
    ]
    cols_str = [f'"{col}"' for col in cols]
    sql = f'SELECT {", ".join(cols_str)} FROM aha_report_x.mart_presentation_interactions WHERE presentationid = {presentation_id};'
    rows = execute(sql)
    return pd.DataFrame(rows, columns=cols)


def get_points_of_presentation(presentation_id: str):
    # One source of truth
    cols = [
        "Slideid",
        "audienceid",
        "Earned_points",
        "Bonus_points"
    ]
    cols_str = [f'"{col}"' for col in cols]
    sql = f'SELECT {", ".join(cols_str)} FROM aha_report_x.fct_points WHERE presentationid = {presentation_id};'
    rows = execute(sql)
    return pd.DataFrame(rows, columns=cols)


def get_participant_count_per_day(user_id: str, days: int = 60):
    """
    Temp function, may be useful for busy users. For now we use weeks since there is too little data.
    """
    sql = f"""
    WITH params AS (
    SELECT CAST(CONVERT_TIMEZONE('UTC','Asia/Bangkok', GETDATE()) AS date) AS local_today
    ),
    nums AS (  -- 0..59 without unsupported functions
    SELECT ones.n + 10*tens.n AS n
    FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
            UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) ones
    CROSS JOIN (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                UNION ALL SELECT 5) tens
    ),
    days AS (
    SELECT DATEADD(day, -n, p.local_today) AS event_day
    FROM nums
    CROSS JOIN params p
    WHERE n BETWEEN 0 AND {days - 1}
    ),
    agg AS (
    SELECT
        CAST(CONVERT_TIMEZONE('UTC','Asia/Bangkok', "Createdat") AS date) AS event_day,
        COUNT(DISTINCT audienceid) AS unique_audience
    FROM aha_report_x.mart_presentation_interactions
    CROSS JOIN params p
    WHERE userid = {user_id}
        AND CAST(CONVERT_TIMEZONE('UTC','Asia/Bangkok', "Createdat") AS date)
            BETWEEN DATEADD(day, -{days - 1}, p.local_today) AND p.local_today
    GROUP BY 1
    )
    SELECT d.event_day,
        COALESCE(a.unique_audience, 0) AS unique_audience
    FROM days d
    LEFT JOIN agg a USING (event_day)
    ORDER BY d.event_day;
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['event_day', 'unique_audience'])



def get_participant_count_per_week_raw(user_id: int, weeks: int = 12):
    sql = f"""
    WITH params AS (
      SELECT CONVERT_TIMEZONE('UTC','Asia/Bangkok', GETDATE())::date AS local_today
    ),
    anchor AS (
      SELECT
        DATE_TRUNC('week', local_today)::date                                           AS week_start_today,
        DATEADD(week, CAST(-({weeks}-1) AS int), DATE_TRUNC('week', local_today))::date AS lower_bound,
        DATEADD(week, 1, DATE_TRUNC('week', local_today))::date                         AS next_week_start
      FROM params
    )
    SELECT
      DATE_TRUNC('week', CONVERT_TIMEZONE('UTC','Asia/Bangkok', "Createdat"))::date AS week_start,
      COUNT(DISTINCT audienceid) AS unique_audience
    FROM aha_report_x.mart_presentation_interactions, anchor a
    WHERE userid = {user_id}
      AND CONVERT_TIMEZONE('UTC','Asia/Bangkok', "Createdat")::date >= a.lower_bound
      AND CONVERT_TIMEZONE('UTC','Asia/Bangkok', "Createdat")::date <  a.next_week_start
    GROUP BY 1
    ORDER BY 1
    LIMIT 1000;
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['week_start', 'unique_audience'])

import datetime as dt

def fill_missing_weeks(df: pd.DataFrame, weeks: int = 12, tz: str = 'Asia/Bangkok'):
    # Ensure schema
    if df.empty:
        df = pd.DataFrame(columns=['week_start', 'unique_audience'])
    df = df.copy()
    df['week_start'] = pd.to_datetime(df['week_start']).dt.date  # -> python date

    # Monday-start of current local week as a python date
    now_local = pd.Timestamp.now(tz=tz)
    week_start_today = (now_local - pd.Timedelta(days=now_local.weekday())).date()

    # Build expected Monday starts (no extra .date() here)
    expected = [week_start_today - dt.timedelta(weeks=i) for i in range(weeks)]
    expected.sort()  # ascending

    spine = pd.DataFrame({'week_start': expected})
    out = spine.merge(df, on='week_start', how='left')
    out['unique_audience'] = out['unique_audience'].fillna(0).astype(int)
    return out


def get_participant_count_per_week_v2(user_id: int, weeks: int = 12):
    raw = get_participant_count_per_week_raw(user_id=user_id, weeks=weeks)
    filled = fill_missing_weeks(raw, weeks=weeks)  # adds zero rows for missing weeks
    return filled



def extract_quiz_value(slide_title, slide_options, vote):
    if vote is None or type(vote) == float or type(slide_options) != str:
        return None
    else:
        vote = ast.literal_eval(vote)
        if len(vote) == 0:
            return None
        data = json.loads(slide_options)
        for option in data:
            if option['id'] == vote[0]:
                return f'Answered: `{option["title"]}` for "{slide_title}"'


def extract_poll_value(slide_title, slide_options, poll_vote):
    if poll_vote is None or type(slide_options) != str:
        return None
    else:
        data = json.loads(slide_options)
        for option in data:
            if option['id'] == poll_vote:
                return f'Answered: `{option["title"]}` for "{slide_title}"'


def extract_short_answer(slide_title, short_answer):
    if short_answer is None or short_answer == 'nan' or type(short_answer) != str:
        return None
    else:
        return f'Answered: `{short_answer}` for "{slide_title}"'


def get_audience_segment(selected_slide, df, audience_id_field):
    slide_type = df[df['Slideid'] == selected_slide['Slideid']]['Slidetypenormalized'].iloc[0]
    if slide_type == 'Poll':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][[audience_id_field, 'Chosen Poll']]
        audience_df['Segment'] = audience_df['Chosen Poll'].fillna('No Category')
        return audience_df
    if slide_type == 'Open Ended':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][[audience_id_field, 'Chosen Short Answer']]
        audience_df['Segment'] = audience_df['Chosen Short Answer'].fillna('No Category')
        return audience_df
    if slide_type == 'Pick Answer':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][[audience_id_field, 'correct']]
        slide_title = df[df['Slideid'] == selected_slide['Slideid']]['Slidetitle'].iloc[0]
        audience_df['correct'] = audience_df['correct'].fillna('No Category')
        audience_df['correct'] = audience_df['correct'].apply(lambda x: f'Answered Correctly to `{slide_title}`' if x == 'correct' else f'Answered Incorrectly to `{slide_title}`')
        audience_df.rename(columns={'correct': 'Segment'}, inplace=True)
        return audience_df


def map_data_with_audience_category(selected_slide, df):
    audience_id_field = 'audienceid'
    audience_segment = get_audience_segment(selected_slide, df, audience_id_field)
    data = df.merge(audience_segment, on=audience_id_field, how='left')
    return data


def map_point_with_audience_segment(selected_slide, df, points_df):
    audience_id_field = 'audienceid'
    audience_segment = get_audience_segment(selected_slide, df, audience_id_field)
    return points_df.merge(audience_segment, on=audience_id_field, how='left')


def enrich_points_with_audience_segment(selected_slide, df, points_df):
    if selected_slide['Slideid'] != 'All':
        return map_point_with_audience_segment(selected_slide, df, points_df)
    else:
        data = points_df.copy()
        data['Segment'] = 'All'
        return data


def enrich_audience_with_category(selected_slide, df):
    if selected_slide['Slideid'] != 'All':
        return map_data_with_audience_category(selected_slide, df)
    else:
        data = df.copy()
        data['Segment'] = 'All'
        return data


def get_avg_point_per_question(user_id: int):
    sql = f"""
    SELECT
    dp.name as presentation_title,
    ds.title AS slide_title,
    AVG(f.earned_points) AS avg_point
        FROM aha_report_x.fct_points f
        JOIN aha_report_x.dim_presentations dp
            ON f.presentationid = dp.id
        JOIN aha_report_x.dim_slides ds
            ON f.slideid = ds.id
        WHERE dp.userid = {user_id}
        AND f.createdat >= dateadd(day, -60, getdate())
        GROUP BY ds.title, dp.name
        ORDER BY avg_point ASC
        LIMIT 1000;
    """
    rows = execute(sql)
    df = pd.DataFrame(rows, columns=['Presentation', 'Question', 'Avg Point'])
    df['Avg Point'] = df['Avg Point'].astype(float)
    return df


def get_wrong_often_questions(user_id: int):
    sql = f"""
    SELECT
    dp.name as presentation_title,
    ds.title AS slide_title,
    COUNT(DISTINCT f.audienceid) AS avg_point
        FROM aha_report_x.fct_points f
        JOIN aha_report_x.dim_presentations dp
            ON f.presentationid = dp.id
        JOIN aha_report_x.dim_slides ds
            ON f.slideid = ds.id
        WHERE dp.userid = {user_id}
        AND f.earned_points = 0
        AND f.createdat >= dateadd(day, -60, getdate())
        GROUP BY ds.title, dp.name
        ORDER BY avg_point DESC
        LIMIT 1000;
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Presentation', 'Question', 'No participant who got this wrong'])


def get_participant_stats(user_id: int):
    sql = f"""
    with answer_stats as (
    select audience_name, AVG(earned_points) as avg_point, COUNT(id) as answer_count from aha_report_x.mart_points
    where userid = {user_id}
    group by audience_name
    order by avg_point ASC
    )
    select * from answer_stats where answer_count > 10 LIMIT 1000
    """
    rows = execute(sql)
    df = pd.DataFrame(rows, columns=['Participant Name', 'Avg Point', 'Answer Count' ])
    df['Avg Point'] = df['Avg Point'].astype(float)
    df['Avg Point'] = df['Avg Point'].fillna(0)
    return df


def get_participant_correct_stats(user_id: int):
    sql = f"""
    with correct_stats as (
	select audience_name,
		SUM(CASE WHEN correct = 'correct' THEN 1 ELSE 0 END) AS correct_count,
	    SUM(CASE WHEN correct = 'incorrect' THEN 1 ELSE 0 END) AS incorrect_count,
	    COUNT(id) AS total_answers,
	    1.0 * SUM(CASE WHEN correct = 'correct' THEN 1 ELSE 0 END) / COUNT(*) AS correct_ratio
	from aha_report_x.mart_presentation_interactions
	where userid = {user_id} and correct IN ('correct', 'incorrect')
	group by audience_name
    )
    select * from correct_stats
    where total_answers > 10
    order by correct_ratio ASC
    LIMIT 1000
    """
    rows = execute(sql)
    df = pd.DataFrame(rows, columns=['Participant Name', 'Correct Answers', 'Incorrect Answers', 'Total Answers', 'Correct Ratio'])
    df['Correct Ratio'] = df['Correct Ratio'].astype(float).round(4)
    df['Correct Percentage'] = df['Correct Ratio'] * 100
    df['Correct Percentage'] = df['Correct Percentage'].round(2)
    return df