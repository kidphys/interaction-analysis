import streamlit as st
import altair as alt
from streamlist_interaction import create_stacked_category_bar_chart, enrich_audience_with_category, map_data_with_audience_category
from warehouse_repo import get_wrong_often_questions_v2
from warehouse_v5_repo import get_wrong_often_questions_v2 as v5_get_wrong_often_questions_v2

st.set_page_config(layout="wide")

user_id = 3146502

params = st.query_params
version = params.get('version', 'v4')

st.subheader('Commonly Wrong Questions In The Last 3 Months')

if version == 'v4':
    wrong_question_df = get_wrong_often_questions_v2(user_id)
if version == 'v5':
    wrong_question_df = v5_get_wrong_often_questions_v2(user_id)

wrong_question_df['Correct Percentage'] = wrong_question_df['Correct Count'] / wrong_question_df['Total Answers'] * 100
wrong_question_df['Correct Percentage'] = wrong_question_df['Correct Percentage'].round(2)
wrong_question_df.sort_values(by='Correct Percentage', inplace=True)
st.write(wrong_question_df)

# Altair histogram of Correct Percentage
hist = (
    alt.Chart(wrong_question_df)
    .mark_bar()
    .encode(
        alt.X("Correct Percentage", bin=alt.Bin(maxbins=20), title="Correct Percentage (%)"),
        alt.Y("count()", title="Number of Questions"),
    )
    .properties(title="Distribution of Correct Percentage")
)

st.altair_chart(hist, use_container_width=True)