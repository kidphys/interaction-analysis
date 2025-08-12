import json
from select import poll
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt


df = pd.read_csv('duke_presentation_interactions.csv')
# df.groupby('Presentationid').size().sort_values(ascending=False)
cols = ['ID', 'Presentationid', 'Interaction Source', 'Numberofreactions', 'Reactiontype',
       'Slideid', 'Audienceid', 'Createdat', 'Updatedat', 'Slideoptions', 'Slidetitle', 'Slide Description', 'Title', 'Slideorder', 'Slidetypenormalized', 'Poll Vote', 'Presentation Name', 'Audience Name']
df = df[df['Presentationid'].isin([7021758, 6925119])][cols].sort_values(by='Slideorder').copy()


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


selected_poll_answers = st.selectbox('Filter participant who:', poll_answers)

st.session_state.selected_poll_answers = selected_poll_answers

audience_id_field = 'Audience Name'
audience_ids = df[audience_id_field].unique()
if st.session_state.selected_poll_answers != 'All':
    audience_df = df[df['Chosen Poll'] == st.session_state.selected_poll_answers]
    audience_ids = audience_df[audience_id_field].unique()

if st.session_state.selected_short_answer != 'All':
    audience_df = df[df['Chosen Short Answer'] == st.session_state.selected_short_answer]
    audience_ids = audience_df[audience_id_field].unique()

filtered_df = df[df[audience_id_field].isin(audience_ids)].copy()

full = df.groupby(['Slideid', 'Slideorder', 'Slidetitle', 'Slidetypenormalized'])['Createdat'].size().reset_index().sort_values(by='Slideorder')
data = filtered_df.groupby(['Slideid', 'Slideorder', 'Slidetitle', 'Slidetypenormalized', 'Presentationid'])['Createdat'].size().reset_index().sort_values(by='Slideorder')
data.rename(columns={'Createdat': 'Interaction Count'}, inplace=True)


slide_type_options = full['Slidetypenormalized'].unique()
slide_type_options = ['All'] + list(slide_type_options)
selected_slide_type = st.selectbox('Filter by slide type', slide_type_options)
# Save the selected value in session state
st.session_state.selected_slide_type = selected_slide_type

# Filter the dataframe based on the selected slide type
if st.session_state.selected_slide_type != 'All':
    data = data[data['Slidetypenormalized'] == st.session_state.selected_slide_type]

# Create a line chart using Altair
chart = alt.Chart(data[data['Presentationid'] == 7021758]).mark_bar().encode(
    x=alt.X('Slidetitle:N', title='Slide Title',
            axis=alt.Axis(labelAngle=-45), sort=['Slideorder']  # Rotate x-axis labels to make them easier to read
    ),
    y='Interaction Count:Q',  # count of interactions as the y-axis
    tooltip=['Slidetitle:N', 'Interaction Count:Q']  # Show full slide title, interaction count, and slide order on hover
).properties(
    title=df[df['Presentationid'] == 7021758]['Presentation Name'].iloc[0]
)

chart2 = alt.Chart(data[data['Presentationid'] == 6925119]).mark_bar().encode(
    x=alt.X('Slidetitle:N', title='Slide Title',
            axis=alt.Axis(labelAngle=-45), sort=['Slideorder']  # Rotate x-axis labels to make them easier to read
    ),
    y='Interaction Count:Q',  # count of interactions as the y-axis
    tooltip=['Slidetitle:N', 'Interaction Count:Q']  # Show full slide title, interaction count, and slide order on hover
).properties(
    title=df[df['Presentationid'] == 6925119]['Presentation Name'].iloc[0]
)
# Display the chart in Streamlit
st.altair_chart(chart, use_container_width=True)
st.altair_chart(chart2, use_container_width=True)


# df