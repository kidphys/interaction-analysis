from re import I
from typing import List
from redshift_api import execute
import pandas as pd
import json
import ast

def get_wrong_often_questions_v2(user_id: int):
    sql = f"""
    SELECT
    dp.title AS presentation_title,
    ds.slide_title AS slide_title,
    COUNT(CASE WHEN fa.correct = true THEN fa.id END) AS correct_count,
    COUNT(CASE WHEN fa.correct != true THEN fa.id END) AS incorrect_count,
    COUNT(fa.id) AS total_answers
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_questions ds
        ON fa.slide_id = ds.id
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    WHERE fa.user_id = {user_id}
    AND fa.slide_type = 'Pick Answer'
    GROUP BY ds.slide_title, dp.title
    ORDER BY total_answers DESC;
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Presentation', 'Question', 'Correct Count', 'Incorrect Count', 'Total Answers'])


def get_total_participants_joined(presentation_id: str):
    sql = f"""
    SELECT COUNT(DISTINCT participant_id)
    FROM aha_report_v5.dim_participants dp
    WHERE master_presentation_id = {presentation_id}
    """
    rows = execute(sql)
    return rows[0][0]


def get_total_participants_submitted(presentation_id: str):
    sql = f"""
    SELECT COUNT(DISTINCT participant_id)
    FROM aha_report_v5.fact_answers fa
    WHERE master_presentation_id = {presentation_id}
    """
    rows = execute(sql)
    return rows[0][0]


def get_recent_presentations(user_id: int):
    """
    Return a list of presentation sorted by last answered createdat
    """
    sql = f"""
    SELECT fa.master_presentation_id, dp.title, MAX(fa.createdat) as last_answered_at
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.user_id = {user_id} AND dda.id IS NULL
    GROUP BY fa.master_presentation_id, dp.title
    ORDER BY MAX(fa.createdat) DESC
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Id', 'Title', 'Last Answered At'])


def get_average_response_time(presentation_id: str):
    """
    Return the average answer_time_seconds for all answers submitted to a presentation_id
    """
    sql = f"""
    SELECT AVG(answer_time_seconds)
    FROM aha_report_v5.fact_answers fa
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id} AND dda.id IS NULL
    """
    rows = execute(sql)
    return rows[0][0]


def get_most_engaging_slides(presentation_id: str):
    """
    Return the slide that have the most number of participants submitted answers
    If there are a tie, pick the most recent answered slide
    """
    sql = f"""
    SELECT fa.slide_id, ds.slide_title, COUNT(DISTINCT participant_id) AS total_participants
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_questions ds
        ON fa.slide_id = ds.id
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id} AND dda.id IS NULL
    GROUP BY fa.slide_id, ds.slide_title
    ORDER BY total_participants DESC, MAX(fa.createdat) DESC
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Slide Id', 'Title', 'Total Participants'])


def get_total_submissions(presentation_id: str):
    """
    Return the total of submissions for this presentation, along with the total number of participants
    """
    sql = f"""
    SELECT COUNT(fa.id), COUNT(DISTINCT participant_id) AS total_participants
    FROM aha_report_v5.fact_answers fa
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id} AND dda.id IS NULL
    """
    rows = execute(sql)
    df = pd.DataFrame(rows, columns=['Total Submissions', 'Total Participants'])
    df['Submission Ratio'] = df['Total Submissions'] / df['Total Participants']
    return df


def get_all_answers_full(presentation_id):
    """
    Return all the answers from a presentation, with dim presentation / slide
    """
    sql = f"""
    SELECT fa.id, fa.slide_id, fa.participant_id, fa.createdat, fa.correct, fa.answer_time_seconds, fa.submitted_answer_text,
    dp.title as presentation_title,
    dq.slide_title,
    dq.slide_order
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    JOIN aha_report_v5.dim_questions dq
        ON fa.slide_id = dq.id
    LEFT JOIN aha_report_v5.dim_deleted_answers dda
        ON fa.id = dda.id
    WHERE fa.master_presentation_id = {presentation_id}
    AND dda.id IS NULL
    """
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['Id', 'Slide Id', 'Participant Id', 'Created At', 'Correct', 'Answer Time Seconds', 'Answer Text', 'Presentation Title', 'Slide Title', 'Slide Order'])

class PresentationData:

    def __init__(self, presentation_id: str):
        self.presentation_id = presentation_id
        self.df = get_all_answers_full(presentation_id)
        self.total_participants = get_total_participants_joined(presentation_id)

    def get_total_submissions(self):
        return self.df['Id'].nunique()

    def get_total_participants_submitted(self):
        return self.df['Participant Id'].nunique()

    def get_engagement_rate(self):
        return self.get_total_participants_submitted() / self.total_participants * 100

    def get_slides_engagement_stats(self):
        slide_df = self.df.groupby(['Slide Id', 'Slide Title', 'Slide Order']).agg({
            'Participant Id': 'nunique',
            'Answer Time Seconds': 'mean'
        }).reset_index()
        slide_df['Engagement Rate'] = slide_df['Participant Id'] / self.total_participants * 100
        # Sort by slide order to maintain proper sequence
        slide_df = slide_df.sort_values('Slide Order').reset_index(drop=True)
        return slide_df

    def get_most_engaging_slide(self):
        slide_df = self.get_slides_engagement_stats()
        slide = slide_df[slide_df['Engagement Rate'] == slide_df['Engagement Rate'].max()]
        return slide.iloc[0].to_dict()

    def get_slides_need_attention_count(self, threshold=60):
        slide_df = self.get_slides_engagement_stats()
        return len(slide_df[slide_df['Engagement Rate'] < threshold])

    def get_total_slides_count(self):
        slide_df = self.get_slides_engagement_stats()
        return len(slide_df)

    def get_average_response_time(self):
        return self.df['Answer Time Seconds'].mean()


# def get_presentations_stats(user_id: int):
#     sql = f"""
#     SELECT
#     dp.title AS presentation_title,
#     COUNT(DISTINCT fa.slide_id) AS total_slides,
#     COUNT(DISTINCT fa.user_id) AS total_participants,
#     COUNT(DISTINCT fa.id) AS total_answers
#     FROM aha_report_v5.fact_answers fa
#     JOIN aha_report_v5.dim_presentations dp
#         ON fa.master_presentation_id = dp.id
#     WHERE fa.user_id = {user_id}
#     GROUP BY dp.title;
#     """