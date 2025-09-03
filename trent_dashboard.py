import streamlit as st
import altair as alt
from streamlist_interaction import create_stacked_category_bar_chart, enrich_audience_with_category, map_data_with_audience_category
from warehouse_repo import get_interactions_of_presentation, get_polls_of_presentation

st.set_page_config(layout="wide")

params = st.query_params
presentation_id = params.get('presentation_id', 7182146)
df = get_polls_of_presentation(presentation_id)

slide_ids = df['Slideid'].unique()
slides = [{
    'Slideid': slide_id,
    'Slidetitle': df[df['Slideid'] == slide_id].iloc[0]['Slidetitle']
} for slide_id in slide_ids]

col1, col2 = st.columns([10, 2])

with col2:
    selected_first_slide = st.selectbox('Poll Result For Slide',
                                  options=slides,
                                  format_func=lambda x: f"{x['Slidetitle']}")
    st.session_state.selected_first_slide = selected_first_slide

    filtered_slides = [slide for slide in slides if slide['Slideid'] != selected_first_slide['Slideid']]
    selected_second_slide = st.selectbox('Break Down By Answers From Slide',
                                  options=filtered_slides,
                                  format_func=lambda x: f"{x['Slidetitle']}")
    st.session_state.selected_second_slide = selected_second_slide

with col1:
    selected_first_slide = st.session_state.selected_first_slide
    selected_second_slide = st.session_state.selected_second_slide
    unique_audience_data = map_data_with_audience_category(selected_second_slide, df)
    unique_audience_data.rename(columns={'Chosen Poll_x': 'Chosen Poll'}, inplace=True)
    unique_audience_data = unique_audience_data[unique_audience_data['Slideid'] == selected_first_slide['Slideid']]
    unique_audience_data = unique_audience_data.groupby(['Presentationid', 'Slideid', 'Slidetitle', 'Slideorder', 'Chosen Poll', 'Category'])['audienceid'].nunique().reset_index().rename(columns={'Audienceid': 'Audience Count'})

    y_field = 'audienceid'
    chart = alt.Chart(unique_audience_data).mark_bar().encode(
        x=alt.X('Chosen Poll:N', title='Chosen Answer',
                axis=alt.Axis(labelAngle=-45)
        ),
        y=f'{y_field}:Q',  # count of interactions as the y-axis
        xOffset='Chosen Poll:N',
        color='Category:N',
        tooltip=['Category:N', f'{y_field}:Q', 'Slidetitle:N', 'Chosen Poll:N']  # Show full slide title, interaction count, and slide order on hover
    ).properties(
        title=selected_first_slide['Slidetitle']
    )
    st.altair_chart(chart, use_container_width=True)