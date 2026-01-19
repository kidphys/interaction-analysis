from curses import window
from redshift_api import execute, execute_with_columns
import pandas as pd

from session_insight.tasks import MART_SQL


def save_max_participant_joined():
    window_minute = 3
    sql = f"""
    -- Query to find max unique participants per presentation and the time window when it occurred
WITH time_windowed_data AS (
    SELECT
        presentation_id,
        participant_id,
        -- Create {window_minute}-minute time windows
        DATE_TRUNC('hour', createdat) +
        INTERVAL '{window_minute} minutes' * FLOOR(EXTRACT(minutes FROM createdat) / {window_minute}) as time_window_start
    FROM aha_report_v5.dim_participants
    WHERE createdat IS NOT NULL
      AND participant_id IS NOT NULL
      AND presentation_id IS NOT null
      AND createdat >= '2025-06-01 00:00:00'::timestamp AT TIME ZONE 'UTC+7'
),
participants_per_window AS (
    SELECT
        presentation_id,
        time_window_start,
        COUNT(DISTINCT participant_id) as unique_participants_in_window
    FROM time_windowed_data
    GROUP BY
        presentation_id,
        time_window_start
),
max_per_presentation AS (
    SELECT
        presentation_id,
        MAX(unique_participants_in_window) as max_unique_participants_in_{window_minute}min_window
    FROM participants_per_window
    GROUP BY presentation_id
)
SELECT
    ppw.presentation_id,
    ppw.time_window_start,
    ppw.unique_participants_in_window as max_unique_participants_in_{window_minute}min_window
FROM participants_per_window ppw
INNER JOIN max_per_presentation mpp
    ON ppw.presentation_id = mpp.presentation_id
    AND ppw.unique_participants_in_window = mpp.max_unique_participants_in_{window_minute}min_window
ORDER BY max_unique_participants_in_{window_minute}min_window DESC
"""
    rows = execute(sql)
    df = pd.DataFrame(columns=['presentation_id', 'time_window', 'participant_count'], data=rows)
    df.to_parquet('max_participant_count_events_per_3_minutes.parquet')


def save_all_events():
    sql = """
    SELECT
    MIN(createdat) as start_time,
    COUNT(createdat) as answer_count,
    COUNT(DISTINCT participant_id) as participant_count,
    true as is_events,
    user_id as presenter_id,
    presentation_id
FROM aha_report_v5.fact_answers2
WHERE createdat >= '2025-10-01 00:00:00'::timestamp AT TIME ZONE 'UTC+7'
  AND createdat < '2025-12-02 00:00:00'::timestamp AT TIME ZONE 'UTC+7'
GROUP BY is_events, presenter_id, presentation_id
"""
    rows = execute(sql)
    df = pd.DataFrame(columns=['start_time', 'answer_count', 'participant_count', 'is_events', 'presenter_id', 'presentation_id'], data=rows)
    df.to_parquet('hosted_events.parquet')


def save_answers_for_cheryl():
    sql = """
    SELECT * FROM aha_report_v5.fact_answers2
    WHERE user_id = 1918789
    """
    rows, cols = execute_with_columns(sql)
    df = pd.DataFrame(columns=cols, data=rows)
    df.to_csv('chery_answers.csv')


def save_participant_reaction_data():
    sql = """
    WITH participant_count_table AS (
    SELECT
        dp.presentation_id,
        COUNT(DISTINCT participant_id) AS participant_count
    FROM aha_report_v5.dim_participants dp
    GROUP BY dp.presentation_id
),
selected_presentation AS (
    SELECT presentation_id, participant_count
    FROM participant_count_table
    WHERE participant_count > 20 AND participant_count < 40
)
SELECT
    fa.presentation_id,
    dq.slide_type,
    fa.reaction_type,
    COUNT(fa.participant_id) AS reaction_count,
    COUNT(DISTINCT fa.participant_id) AS participant_reacted,
    sp.participant_count as total_participant,
    (COUNT(DISTINCT fa.participant_id)::float / sp.participant_count) * 100 as reaction_percentage,
    MAX(fa.updatedat) as last_reaction_time
FROM aha_report_v5.fact_reactions3 fa
JOIN selected_presentation sp
    ON fa.presentation_id = sp.presentation_id
JOIN aha_report_v5.dim_questions dq
    ON fa.slide_id = dq.slide_id
    AND fa.presentation_id = dq.presentation_id
WHERE
    fa.deleted = false
GROUP BY
    fa.presentation_id,
    dq.slide_type,
    fa.reaction_type,
    sp.participant_count;
    """
    rows, cols = execute_with_columns(sql)
    df = pd.DataFrame(columns=cols, data=rows)
    df.to_csv('reaction_stats.csv')


def save_participant_answers_data():
    sql = """
    WITH participant_count_table AS (
    SELECT
        dp.presentation_id,
        COUNT(DISTINCT participant_id) AS participant_count
    FROM aha_report_v5.dim_participants dp
    GROUP BY dp.presentation_id
),
selected_presentation AS (
    SELECT presentation_id, participant_count
    FROM participant_count_table
    WHERE participant_count > 20 AND participant_count < 40
)
SELECT
    fa.presentation_id,
    dq.slide_type,
    COUNT(fa.participant_id) AS answer_count,
    COUNT(DISTINCT fa.participant_id) AS participant_answered,
    sp.participant_count as total_participant,
    (COUNT(DISTINCT fa.participant_id)::float / sp.participant_count) * 100 as answer_percentage,
    MAX(fa.updatedat) as last_answer_time
FROM aha_report_v5.fact_answers2 fa
JOIN selected_presentation sp
    ON fa.presentation_id = sp.presentation_id
JOIN aha_report_v5.dim_questions dq
    ON fa.slide_id = dq.slide_id
    AND fa.presentation_id = dq.presentation_id
WHERE
    fa.deleted = false
GROUP BY
    fa.presentation_id,
    dq.slide_type,
    sp.participant_count;
    """
    rows, cols = execute_with_columns(sql)
    df = pd.DataFrame(columns=cols, data=rows)
    df.to_csv('answer_stats.csv')


def save_participant_answers_no_timeout_data():
    sql = """
    WITH participant_count_table AS (
    SELECT
        dp.presentation_id,
        COUNT(DISTINCT participant_id) AS participant_count
    FROM aha_report_v5.dim_participants dp
    GROUP BY dp.presentation_id
),
selected_presentation AS (
    SELECT presentation_id, participant_count
    FROM participant_count_table
    WHERE participant_count > 20 AND participant_count < 40
)
SELECT
    fa.presentation_id,
    dq.slide_type,
    dq.slide_title,
    dq.slide_subheading,
    dq.slide_description,
    dq.slide_order,
    COUNT(fa.participant_id) AS answer_count,
    COUNT(DISTINCT fa.participant_id) AS participant_answered,
    sp.participant_count as total_participant,
    (COUNT(DISTINCT fa.participant_id)::float / sp.participant_count) * 100 as answer_percentage,
    MAX(fa.updatedat) as last_answer_time
FROM aha_report_v5.fact_answers2 fa
JOIN selected_presentation sp
    ON fa.presentation_id = sp.presentation_id
JOIN aha_report_v5.dim_questions dq
    ON fa.slide_id = dq.slide_id
    AND fa.presentation_id = dq.presentation_id
WHERE
    fa.deleted = false
GROUP BY
    fa.presentation_id,
    dq.slide_type,
    dq.slide_title,
    dq.slide_subheading,
    dq.slide_description,
    dq.slide_order,
    sp.participant_count;
    """
    rows, cols = execute_with_columns(sql)
    df = pd.DataFrame(columns=cols, data=rows)
    df.to_csv('answer_stats_no_timeout_v2.csv')


def save_participant_answers_for_users(user_ids: list[int]):
    sql = f"""
    WITH participant_count_table AS (
    SELECT
        dp.presentation_id,
        COUNT(DISTINCT participant_id) AS participant_count
    FROM aha_report_v5.dim_participants dp
    WHERE dp.user_id IN ({', '.join(map(str, user_ids))})
    GROUP BY dp.presentation_id
),
selected_presentation AS (
    SELECT user_id, presentation_id, title as presentation_title, participant_count
    FROM participant_count_table
    JOIN aha_report_v5.dim_presentations dp
        ON dp.id = participant_count_table.presentation_id
    WHERE participant_count > 20 AND participant_count < 40
)
SELECT
    fa.presentation_id,
    sp.user_id,
    sp.presentation_title,
    dq.slide_type,
    dq.slide_title,
    dq.slide_subheading,
    dq.slide_description,
    dq.slide_order,
    COUNT(fa.participant_id) AS answer_count,
    COUNT(DISTINCT fa.participant_id) AS participant_answered,
    sp.participant_count as total_participant,
    (COUNT(DISTINCT fa.participant_id)::float / sp.participant_count) * 100 as answer_percentage,
    MAX(fa.updatedat) as last_answer_time
FROM aha_report_v5.fact_answers2 fa
JOIN selected_presentation sp
    ON fa.presentation_id = sp.presentation_id
JOIN aha_report_v5.dim_questions dq
    ON fa.slide_id = dq.slide_id
    AND fa.presentation_id = dq.presentation_id
WHERE
    fa.deleted = false
GROUP BY
    fa.presentation_id,
    sp.user_id,
    dq.slide_type,
    dq.slide_title,
    dq.slide_subheading,
    dq.slide_description,
    dq.slide_order,
    sp.presentation_title,
    sp.participant_count;
    """
    rows, cols = execute_with_columns(sql)
    df = pd.DataFrame(columns=cols, data=rows)
    df.to_csv('answer_stats_user_ids.csv')


def save_answers_for_presentation(presentation_id):
    sql = MART_SQL.format(presentation_id=presentation_id)
    rows, cols = execute_with_columns(sql)
    df = pd.DataFrame(columns=cols, data=rows)
    return df
    # df.to_csv(f'answers_for_presentation_{presentation_id}.csv')


if __name__ == "__main__":
    # save_max_participant_joined()
    # save_answers_for_cheryl()
    # save_participant_reaction_data()
    # save_participant_answers_data()
    # save_participant_answers_no_timeout_data()
    # save_participant_answers_for_users([1472007, 1918789, 126])
    save_answers_for_presentation("7880449")