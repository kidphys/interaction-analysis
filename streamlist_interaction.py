import json
from select import poll
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt


df = pd.read_csv('duke_presentation_interactions.csv')
# df.groupby('Presentationid').size().sort_values(ascending=False)
df = df[df['Presentationid'].isin([7021758, 6925119])].sort_values(by='Slideorder').copy()


def extract_poll_value(slide_title, slide_options, poll_vote):
    if poll_vote is None or type(slide_options) != str:
        return None
    else:
        data = json.loads(slide_options)
        for option in data:
            if option['id'] == poll_vote:
                return f'Answered: `{option["title"]}` for "{slide_title}"'


df['Chosen Poll'] = df.apply(lambda x: extract_poll_value(x['Slidetitle'], x['Slideoptions'], x['Poll Vote']), axis=1)
poll_answers = df[df['Chosen Poll'].notna()]['Chosen Poll'].unique()
poll_answers = ['All'] + list(poll_answers)


if 'selected_poll_answers' not in st.session_state:
    st.session_state.selected_poll_answers = 'All'
if 'selected_slide_type' not in st.session_state:
    st.session_state.selected_slide_type = 'All'
if 'selected_short_answer' not in st.session_state:
    st.session_state.selected_short_answer = 'All'


def extract_short_answer(slide_title, short_answer):
    if short_answer is None or short_answer == 'nan' or type(short_answer) != str:
        return None
    else:
        return f'Answered: `{short_answer}` for "{slide_title}"'

df['Chosen Short Answer'] = df.apply(lambda x: extract_short_answer(x['Slidetitle'], x['Title']), axis=1)
chosen_answers = df['Chosen Short Answer'].dropna().unique()

# selected_short_answer = st.selectbox('Filter participant who:', ['All'] + list(chosen_answers))
# st.session_state.selected_short_answer = selected_short_answer


poll_slide_titles = df[df['Slidetypenormalized'] == 'Poll']['Slidetitle'].unique()
quiz_slide_titles = df[df['Slidetypenormalized'] == 'Pick Answer']['Slidetitle'].unique()
selected_slide = st.selectbox('Break down by answer for question:', ['All'] + list(quiz_slide_titles) + list(poll_slide_titles))
st.session_state.selected_slide = selected_slide

def create_category_bar_chart(data, presentation_id):
    return alt.Chart(data[data['Presentationid'] == presentation_id]).mark_bar().encode(
        x=alt.X('Slidetitle:N', title='Slide Title',
                axis=alt.Axis(labelAngle=-45), sort=['Slideorder']  # Rotate x-axis labels to make them easier to read
        ),
        y='Interaction Count:Q',  # count of interactions as the y-axis
        xOffset='Category:N',
        color='Category:N',
        tooltip=['Category:N', 'Interaction Count:Q', 'Slidetitle:N']  # Show full slide title, interaction count, and slide order on hover
    ).properties(
        title=df[df['Presentationid'] == presentation_id]['Presentation Name'].iloc[0]
    )


if selected_slide != 'All':
    slide_type = df[df['Slidetitle'] == selected_slide]['Slidetypenormalized'].iloc[0]
    if slide_type == 'Poll':
        audience_df = df[df['Slidetitle'] == selected_slide][['Audience Name', 'Chosen Poll']]
        data = df.merge(audience_df, on='Audience Name', how='left')
        data.rename(columns={'Chosen Poll_y': 'Category'}, inplace=True)
        data = data.groupby(['Presentationid', 'Slidetitle', 'Slideorder', 'Category']).size().reset_index().rename(columns={0: 'Interaction Count'})
        data = data.sort_values(by='Slideorder')
        data['Category'] = data['Category'].fillna('No Category')
    if slide_type == 'Pick Answer':
        audience_df = df[df['Slidetitle'] == selected_slide][['Audience Name', 'Correct']]
        slide_title = df[df['Slidetitle'] == selected_slide]['Slidetitle'].iloc[0]
        audience_df['Correct'] = audience_df['Correct'].fillna('No Category')
        audience_df['Correct'] = audience_df['Correct'].apply(lambda x: f'Answered Correctly to `{slide_title}`' if x == 'correct' else f'Answered Incorrectly to `{slide_title}`')
        data = df.merge(audience_df, on='Audience Name', how='left')
        data.rename(columns={'Correct_y': 'Category'}, inplace=True)
        data = data.groupby(['Presentationid', 'Slidetitle', 'Slideorder', 'Category']).size().reset_index().rename(columns={0: 'Interaction Count'})
        data = data.sort_values(by='Slideorder')
        data['Category'] = data['Category'].fillna('No Category')
else:
    data = df.copy()
    data = data.groupby(['Presentationid', 'Slidetitle', 'Slideorder']).size().reset_index().rename(columns={0: 'Interaction Count'})
    data = data.sort_values(by='Slideorder')
    data['Category'] = 'All'
    # chart1 = create_all_interaction_bar_chart(data, 6925119)
    # chart2 = create_all_interaction_bar_chart(data, 7021758)

chart1 = create_category_bar_chart(data, 6925119)
chart2 = create_category_bar_chart(data, 7021758)



st.altair_chart(chart1, use_container_width=True)
st.altair_chart(chart2, use_container_width=True)
# data = data[data['Presentationid'] == 7021758]
# df