import ast
import json
from select import poll
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

from warehouse_repo import enrich_audience_with_category, extract_poll_value, extract_quiz_value, extract_short_answer
from warehouse_repo import get_interactions_of_presentation, get_presentations_of_user

kiotviet_user_id = 259137
presentation_df = get_presentations_of_user(kiotviet_user_id)

st.set_page_config(layout="wide")
# Create a container
top_container = st.container()
col1, col2 = top_container.columns([3, 1])

with col2:
    presentations = presentation_df.to_dict(orient='records')
    default_idx = 28
    selected_presentation = st.selectbox('Select presentation:', list(presentations), format_func=lambda x: x['name'], index=default_idx)
    st.session_state.selected_presentation = selected_presentation

if st.session_state.selected_presentation:
    presentation_id = st.session_state.selected_presentation['id']
else:
    presentation_id = 7021758

df = get_interactions_of_presentation(presentation_id)

t = df[['Slideorder', 'Slidetitle']].value_counts().reset_index().sort_values(by='Slideorder')
t['#'] = range(1, len(t) + 1)
df = df.merge(t[['#', 'Slideorder', 'Slidetitle']], on=['Slideorder', 'Slidetitle'], how='left').sort_values(by='Slideorder')
df['#'] = df['#'].fillna(0).astype(int)
df['# Slidetitle'] = df.apply(lambda x: f"#{x['#']} - {x['Slidetitle']}", axis=1)

df['Chosen Pick Answer'] = df.apply(lambda x: extract_quiz_value(x['Slidetitle'], x['Slideoptions'], x['Vote']), axis=1)
df['Chosen Poll'] = df.apply(lambda x: extract_poll_value(x['Slidetitle'], x['Slideoptions'], x['poll_vote']), axis=1)
poll_answers = df[df['Chosen Poll'].notna()]['Chosen Poll'].unique()
poll_answers = ['All'] + list(poll_answers)


if 'selected_poll_answers' not in st.session_state:
    st.session_state.selected_poll_answers = 'All'
if 'selected_slide_type' not in st.session_state:
    st.session_state.selected_slide_type = 'All'
if 'selected_short_answer' not in st.session_state:
    st.session_state.selected_short_answer = 'All'

df['Chosen Short Answer'] = df.apply(lambda x: extract_short_answer(x['Slidetitle'], x['Title']), axis=1)
chosen_answers = df['Chosen Short Answer'].dropna().unique()

df['Answer Text'] = df[['Chosen Pick Answer', 'Chosen Poll', 'Chosen Short Answer']].bfill(axis=1).iloc[:, 0]

df['Slidetitle'] = df['Slidetitle'].astype(str)
df['Slidetitle'] = df.apply(lambda x: x['Slidetitle'] if x['Slidetitle'] != 'nan' else '(empty)', axis=1)

all_slides_df = df.groupby(['Slideid', 'Slidetitle', 'Slidetypenormalized', 'Slideorder']).size().reset_index().sort_values(by='Slideorder')[['Slideid', 'Slidetitle', 'Slidetypenormalized']]
all_slides_df['Index'] = range(1, len(all_slides_df) + 1)
all_slide_titles = all_slides_df.to_dict('records')
poll_slide_titles = all_slides_df[all_slides_df['Slidetypenormalized'] == 'Poll'][['Slideid', 'Slidetitle', 'Slidetypenormalized']].to_dict('records')
quiz_slide_titles = all_slides_df[all_slides_df['Slidetypenormalized'] == 'Pick Answer'][['Slideid', 'Slidetitle', 'Slidetypenormalized']].to_dict('records')
all_slide_titles = [{'Slideid': 'All', 'Slidetitle': 'All', 'Slidetypenormalized': '', 'Index': 0}] + all_slide_titles

with col2:
    question_slides = [{'Slideid': 'All', 'Slidetitle': 'All', 'Slidetypenormalized': ''}] + list(quiz_slide_titles) + list(poll_slide_titles)
    selected_slide = st.selectbox('Break down by answer for question:',
                                  options=question_slides,
                                  format_func=lambda x: f"{x['Slidetypenormalized']} - {x['Slidetitle']}")
    st.session_state.selected_slide = selected_slide


def create_category_bar_chart(data, y_field='Interaction Count', title='Empty'):
    return alt.Chart(data).mark_bar(size=12).encode(
        x=alt.X('Slidetitle:N', title='Slide Title',
                axis=alt.Axis(labelAngle=-45), sort=['Slideorder']  # Rotate x-axis labels to make them easier to read
        ),
        y=f'{y_field}:Q',  # count of interactions as the y-axis
        xOffset='Segment:N',
        color='Segment:N',
        tooltip=['Segment:N', f'{y_field}:Q', 'Slidetitle:N']  # Show full slide title, interaction count, and slide order on hover
    ).properties(
        title=title
    )

def create_stacked_category_bar_chart(data, y_field='Interaction Count', title='Empty'):
    orders = sorted(data['Answer Text'].dropna().unique().tolist())
    return alt.Chart(data).mark_bar(size=10,
                                    stroke='white',        # outline color (use '#0E1117' if your bg is dark and you want gaps)
                                    strokeWidth=2,
                                    strokeOpacity=1,
                                    fillOpacity=0.7).encode(
        x=alt.X('Slidetitle:N', title='Slide Title',
                axis=alt.Axis(ticks=True, tickBand='center', labelAngle=-45), sort=['Slideorder'],  # Rotate x-axis labels to make them easier to read
        ),
        y=f'{y_field}:Q',  # count of interactions as the y-axis
        xOffset='Segment:N',
        color=alt.Color('Answer Text:N', legend=None),
        tooltip=['Segment:N', f'{y_field}:Q', 'Slidetitle:N', 'Answer Text:N'],  # Show full slide title, interaction count, and slide order on hover
        stroke=alt.Stroke('Segment:N',     # outline color varies by offset
                          sort=orders,
                          scale=alt.Scale(scheme='category10'))
    ).properties(
        height=380, width=2200, title=title
    ).interact


def create_segment_line_chart(data, y_field='Interaction Count', title='Empty'):
    return alt.Chart(data).mark_line(
            size=2,
            point=alt.OverlayMarkDef(filled=True, size=80)
            ).encode(
        x=alt.X('# Slidetitle:N', title='Slide Title',
                sort=alt.EncodingSortField(field='Slideorder', op='min', order='ascending'),
                axis=alt.Axis(ticks=True, tickBand='center', labelAngle=-45),   # Rotate x-axis labels to make them easier to read
        ),
        y=f'{y_field}:Q',  # count of interactions as the y-axis
        color='Segment:N',
        tooltip=['Segment:N', alt.Tooltip(f'{y_field}:Q', format='.2%'), 'Slidetitle:N']  # Show full slide title, interaction count, and slide order on hover
    ).properties(
        title=title
    )


def get_active_presentation_title():
    presentation_id = st.session_state.selected_presentation['id']
    return presentation_df[presentation_df['id'] == presentation_id]['name'].iloc[0]


interaction_count_data = enrich_audience_with_category(selected_slide, df)
interaction_count_data = interaction_count_data.groupby(['Slideid', 'Slidetitle', '# Slidetitle', 'Slideorder', 'Segment']).size().reset_index().rename(columns={0: 'Interaction Count'})
interaction_count_data = interaction_count_data.sort_values(by='Slideorder')


st.write(interaction_count_data)
with col1:
    chart1 = create_segment_line_chart(interaction_count_data, y_field='Interaction Count', title=get_active_presentation_title())
    # chart1 = create_category_bar_chart(interaction_count_data, title=get_active_presentation_title())
    st.altair_chart(chart1, use_container_width=True)

unique_audience_data = enrich_audience_with_category(selected_slide, df)
presentation_audience_count = unique_audience_data['audienceid'].nunique()


unique_audience_per_segment = unique_audience_data.groupby(['Segment'])['audienceid'].nunique().reset_index().rename(columns={'audienceid': 'Segment Audience Count'})

unique_audience_data = unique_audience_data.groupby(['Slideid', 'Slidetitle', '# Slidetitle', 'Slideorder', 'Segment'])['audienceid'].nunique().reset_index().rename(columns={'audienceid': 'Audience Count'})
unique_audience_data = unique_audience_data.sort_values(by='Slideorder')

unique_audience_data = unique_audience_data.merge(unique_audience_per_segment, on='Segment', how='left')
unique_audience_data['Engagement Rate'] = unique_audience_data['Audience Count'] / unique_audience_data['Segment Audience Count']
st.write(unique_audience_data)

unique_audience_data['Percent of engaged audience'] = unique_audience_data['Audience Count'] / presentation_audience_count * 100
y_field = 'Percent of engaged audience'

chart2 = create_segment_line_chart(unique_audience_data, y_field='Engagement Rate', title=get_active_presentation_title())

with col1:
    st.altair_chart(chart2, use_container_width=True)

st.write(unique_audience_data[['# Slidetitle', 'Engagement Rate', 'Segment', 'Audience Count', 'Segment Audience Count']])