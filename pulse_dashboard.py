import streamlit as st
from user_map import user_map
from warehouse_repo import get_interactions_of_presentation, get_presentations_of_user
import altair as alt
import pandas as pd
import numpy as np

from warehouse_v5_repo import get_engagement_df_for_presentation, get_engagement_for_presentation, get_total_participants_joined


def enrich_interaction_data(df):
    unique_audience_data = df.copy()
    presentation_audience_count = unique_audience_data['audienceid'].nunique()

    unique_audience_data = unique_audience_data.groupby(['Slideid', 'Slidetitle', 'Slideorder',  'Slidetypenormalized'])['audienceid'].nunique().reset_index().rename(columns={'audienceid': 'Audience Count'})
    unique_audience_data['#'] = range(1, len(unique_audience_data) + 1)
    unique_audience_data['# Slidetitle'] = unique_audience_data.apply(lambda x: f"#{x['#']} - {x['Slidetitle']}", axis=1)
    audience_count = df['audienceid'].nunique()
    unique_audience_data = unique_audience_data.sort_values(by='Slideorder')

    unique_audience_data['Engagement Rate'] = unique_audience_data['Audience Count'] / audience_count
    unique_audience_data['Percent of engaged audience'] = unique_audience_data['Audience Count'] / presentation_audience_count * 100
    unique_audience_data = unique_audience_data.sort_values(by='Slideorder')
    return unique_audience_data

# Create ultra-simplified pulse with minimal points
def create_minimal_pulse(data, y_column):
    """Create minimal pulse with exactly 3 points per slide to prevent any clustering"""
    minimal_data = []

    for _, row in data.iterrows():
        slide_num = row['#']
        engagement = row[y_column]

        if engagement > 5:
            # Just 3 points: dip -> peak -> dip
            points = [
                (slide_num - 0.15, engagement * 0.1),  # Left dip
                (slide_num, engagement),               # Peak
                (slide_num + 0.15, engagement * 0.1)   # Right dip
            ]
        else:
            # Single flat point
            points = [(slide_num, engagement * 0.1)]

        for x, y in points:
            minimal_data.append({
                'x_pos': x,
                'y_pulse': y,
                'slide_num': slide_num,
                'original_engagement': engagement,
                'slide_title': row['Slidetitle']
            })

    return pd.DataFrame(minimal_data).sort_values('x_pos')


def create_pulse_chart(minimal_pulse_df):
    minimal_chart = alt.Chart(minimal_pulse_df).mark_line(
        size=3,
        color='#FF4081',
        strokeCap='round',
        interpolate='linear'
    ).encode(
        x=alt.X('x_pos:Q', title='Slide number'),
        y=alt.Y('y_pulse:Q', title='Engagement pulse'),
        tooltip=['slide_title:N', 'original_engagement:Q']
    ).properties(
        title='AhaPulse - Engagement Live Report',
        width=900,
        height=250
    )

    st.altair_chart(minimal_chart, use_container_width=True)


if __name__ == "__main__":
    st.set_page_config(layout="wide")
    col1, col2 = st.columns([3, 1])

    params = st.query_params
    user = params.get('user', 'cheryl')
    if user not in user_map:
        st.write('Not supported user')
    else:
        user_id = user_map.get(user)
        presentation_df = get_presentations_of_user(user_id)
        presentation_df = presentation_df.sort_values(by='createdat', ascending=False)

        with col2:
            presentations = presentation_df.to_dict(orient='records')
            default_idx = 1
            selected_presentation = st.selectbox('Select presentation:', list(presentations), format_func=lambda x: x['name'], index=default_idx)
            st.session_state.selected_presentation = selected_presentation


        if st.session_state.selected_presentation:
            presentation_id = st.session_state.selected_presentation['id']
        else:
            presentation_id = 7021758
        engagement_df = get_engagement_df_for_presentation(presentation_id)
        minimal_pulse_df = create_minimal_pulse(engagement_df, 'Percent of engaged audience')
        create_pulse_chart(minimal_pulse_df)





