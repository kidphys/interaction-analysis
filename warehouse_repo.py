from redshift_api import execute
import pandas as pd
import json
import ast


def get_presentations_of_user(user_id: str):
    sql = f'SELECT "id", "userid", "name" FROM aha_report_x.dim_presentations WHERE userid = {user_id};'
    rows = execute(sql)
    return pd.DataFrame(rows, columns=['id', 'userid', 'name'])


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
        audience_df['Segement'] = audience_df['Chosen Poll'].fillna('No Category')
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
