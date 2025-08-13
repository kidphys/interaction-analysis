import json
from select import poll
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

df = pd.read_csv('duke_presentation_interactions.csv')
# df.groupby('Presentationid').size().sort_values(ascending=False)
# df = df[df['Presentationid'].isin([7021758, 6925119])].sort_values(by='Slideorder').copy()
df = df.sort_values(by='Slideorder').copy()


st.set_page_config(layout="wide")
# Create a container
top_container = st.container()
col1, col2 = top_container.columns([3, 1])

with col2:
    presentation_titles = df['Presentation Name'].unique()
    default_idx = presentation_titles.tolist().index('Impact Meeting 02/06/2023 - final final')
    selected_presentation = st.selectbox('Select presentation:', list(presentation_titles), index=default_idx)
    st.session_state.selected_presentation = selected_presentation

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

if st.session_state.selected_presentation:
    presentation_id = df[df['Presentation Name'] == st.session_state.selected_presentation]['Presentationid'].iloc[0]
else:
    presentation_id = 7021758

df = df[df['Presentationid'] == presentation_id]
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


def create_category_bar_chart(data, presentation_id, y_field='Interaction Count'):
    return alt.Chart(data[data['Presentationid'] == presentation_id]).mark_bar().encode(
        x=alt.X('Slidetitle:N', title='Slide Title',
                axis=alt.Axis(labelAngle=-45), sort=['Slideorder']  # Rotate x-axis labels to make them easier to read
        ),
        y=f'{y_field}:Q',  # count of interactions as the y-axis
        xOffset='Category:N',
        color='Category:N',
        tooltip=['Category:N', f'{y_field}:Q', 'Slidetitle:N']  # Show full slide title, interaction count, and slide order on hover
    ).properties(
        title=df[df['Presentationid'] == presentation_id]['Presentation Name'].iloc[0]
    )


def map_data_with_audience_category(selected_slide, df):
    slide_type = df[df['Slideid'] == selected_slide['Slideid']]['Slidetypenormalized'].iloc[0]
    if slide_type == 'Poll':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][['Audience Name', 'Chosen Poll']]
        audience_df['Chosen Poll'] = audience_df['Chosen Poll'].fillna('No Category')
        data = df.merge(audience_df, on='Audience Name', how='left')
        data.rename(columns={'Chosen Poll_y': 'Category'}, inplace=True)
        return data
    if slide_type == 'Pick Answer':
        audience_df = df[df['Slideid'] == selected_slide['Slideid']][['Audience Name', 'Correct']]
        slide_title = df[df['Slideid'] == selected_slide['Slideid']]['Slidetitle'].iloc[0]
        audience_df['Correct'] = audience_df['Correct'].fillna('No Category')
        audience_df['Correct'] = audience_df['Correct'].apply(lambda x: f'Answered Correctly to `{slide_title}`' if x == 'correct' else f'Answered Incorrectly to `{slide_title}`')
        data = df.merge(audience_df, on='Audience Name', how='left')
        data.rename(columns={'Correct_y': 'Category'}, inplace=True)
        return data


def enrich_audience_with_category(selected_slide, df):
    if selected_slide['Slideid'] != 'All':
        return map_data_with_audience_category(selected_slide, df)
    else:
        data = df.copy()
        data['Category'] = 'All'
        return data

interaction_count_data = enrich_audience_with_category(selected_slide, df)
interaction_count_data = interaction_count_data.groupby(['Presentationid', 'Slideid', 'Slidetitle', 'Slideorder', 'Category']).size().reset_index().rename(columns={0: 'Interaction Count'})
interaction_count_data = interaction_count_data.sort_values(by='Slideorder')


def get_chosen_presentation_id(df):
    if st.session_state.selected_presentation:
        return df[df['Presentation Name'] == st.session_state.selected_presentation]['Presentationid'].iloc[0]
    else:
        return 6925119


with col1:
    chart1 = create_category_bar_chart(interaction_count_data, get_chosen_presentation_id(df))
    st.altair_chart(chart1, use_container_width=True)

unique_audience_data = enrich_audience_with_category(selected_slide, df)
presentation_audience_count = unique_audience_data.groupby('Presentationid')['Audienceid'].nunique().reset_index()['Audienceid'].iloc[0]


with col1:
    is_audience_account_in_percentage = st.toggle('Percentage of audience', value=True)
    st.session_state.is_audience_account_in_percentage = is_audience_account_in_percentage

unique_audience_data = unique_audience_data.groupby(['Presentationid', 'Slideid', 'Slidetitle', 'Slideorder', 'Category'])['Audienceid'].nunique().reset_index().rename(columns={'Audienceid': 'Audience Count'})
unique_audience_data = unique_audience_data.sort_values(by='Slideorder')

y_field = 'Audience Count'
if st.session_state.is_audience_account_in_percentage:
    unique_audience_data['Percent of engaged audience'] = unique_audience_data['Audience Count'] / presentation_audience_count * 100
    y_field = 'Percent of engaged audience'

chart2 = create_category_bar_chart(unique_audience_data, get_chosen_presentation_id(df), y_field=y_field)

with col1:
    st.altair_chart(chart2, use_container_width=True)


bottom_container = st.container()
col1, col2 = bottom_container.columns([3, 1])


with col2:
    slides_to_select = all_slide_titles[1:].copy()
    first_selected_slide = st.selectbox('Select 1st slide', options=slides_to_select, format_func=lambda x: f"#{x['Index']} - {x['Slidetypenormalized']} - {x['Slidetitle']}", key="select_first_slide")
    st.session_state.first_selected_slide = first_selected_slide
    second_slides_candidates = [s for s in slides_to_select if s['Index'] > first_selected_slide['Index']]
    second_selected_slide = st.selectbox('Select 2nd slide', options=second_slides_candidates, format_func=lambda x: f"#{x['Index']} - {x['Slidetypenormalized']} - {x['Slidetitle']}")
    st.session_state.second_selected_slide = second_selected_slide


with col1:
    first_funnel_data = enrich_audience_with_category(st.session_state.selected_slide, df)
    first_funnel_data = first_funnel_data[first_funnel_data['Slideid'] == st.session_state.first_selected_slide['Slideid']]
    first_funnel_df = first_funnel_data.groupby(['Category', 'Slideorder'])['Audienceid'].agg(lambda x: set(x)).reset_index()
    second_funnel_data = enrich_audience_with_category(st.session_state.selected_slide, df)
    second_funnel_data = second_funnel_data[second_funnel_data['Slideid'] == st.session_state.second_selected_slide['Slideid']]
    second_funnel_df = second_funnel_data.groupby(['Category', 'Slideorder'])['Audienceid'].agg(lambda x: set(x)).reset_index()
    funnel_df = pd.merge(first_funnel_df, second_funnel_df, on='Category', how='outer')
    funnel_df = funnel_df.fillna('')
    funnel_df['Audienceid_x'] = funnel_df['Audienceid_x'].apply(lambda x: x if x is not '' else set())
    funnel_df['Audienceid_y'] = funnel_df['Audienceid_y'].apply(lambda x: x if x is not '' else set())
    funnel_df['Second Step Audiences'] = funnel_df.apply(lambda x: (x['Audienceid_x'] & x['Audienceid_y']), axis=1)
    first_step = f"#{st.session_state.first_selected_slide['Index']} - {st.session_state.first_selected_slide['Slidetitle']}"
    second_step = f"#{st.session_state.second_selected_slide['Index']} - {st.session_state.second_selected_slide['Slidetitle']}"
    funnel_df[first_step] = funnel_df['Audienceid_x'].apply(lambda x: len(x))
    funnel_df[second_step] = funnel_df['Second Step Audiences'].apply(lambda x: len(x))
    funnel_df['Percent converted to 2nd step'] = funnel_df[f"#{st.session_state.second_selected_slide['Index']} - {st.session_state.second_selected_slide['Slidetitle']}"] / funnel_df[f"#{st.session_state.first_selected_slide['Index']} - {st.session_state.first_selected_slide['Slidetitle']}"] * 100
    # Clean up and reshape
    plot_df = funnel_df.copy()
    plot_df = plot_df.fillna(0)  # in case some categories are missing a step
    long_df = plot_df.melt(
        id_vars=['Category', 'Percent converted to 2nd step', 'Slideorder_x', 'Slideorder_y'] ,
        value_vars=[first_step, second_step],
        var_name='Step',
        value_name='Audience Count'
    )
    long_df['Percent'] = long_df.apply(
            lambda row: f"{row['Percent converted to 2nd step']:,.2f}%" if row['Step'] == second_step else "100%",
            axis=1
        )
    # long_df = long_df.sort_values(by='Slideorder')
    long_df['Slideorder'] = long_df.apply(lambda x: x['Slideorder_x'] if x['Step'] == first_step else x['Slideorder_y'], axis=1)

    # Bars
    chart3 = alt.Chart(long_df).mark_bar().encode(
        x=alt.X('Step:N', title='Step', axis=alt.Axis(labelAngle=-45), sort=['Slideorder']),
        y=alt.Y('Audience Count:Q', title='Audience Count'),
        xOffset='Category:N',
        color='Category:N',
        tooltip=['Audience Count:Q', 'Percent:N', 'Category:N'],
        text='Percent:N'
    ).properties(title='Conversion funnel from 1st to 2nd slide')

    st.altair_chart(chart3, use_container_width=True)