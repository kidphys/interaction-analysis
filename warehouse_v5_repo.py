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