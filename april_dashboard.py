import streamlit as st
import altair as alt
from warehouse_v5_repo import get_question_engagement_stats, get_recurring_questions

st.set_page_config(layout="wide")

user_id = 2992027

params = st.query_params
version = params.get('version', 'v4')

recurring_question_df = get_recurring_questions(user_id)

st.subheader('Questions Stats Across Sessions')

slide_options = recurring_question_df.to_dict(orient='records')


selected_slide = st.selectbox(
    "Select Questions:",
    options=slide_options,
    format_func=lambda x: f"{x['SlideTitle']}",
    index=0 if slide_options else None,
    key="selected_slide"
)

def plot_chart(df, field, title):
    chart = alt.Chart(df).mark_line(
            point=True,  # Add points
            size=3       # Line thickness
        ).encode(
        x=alt.X('Presentation:N',
                sort=None,
                axis=alt.Axis(labelAngle=-60, labelLimit=300, labelOverlap=False),
                scale=alt.Scale(padding=0.5)
                ),
        y=f'{field}:Q',
    tooltip=['Presentation', field]
    ).properties(
        width=800,
        height=500,
        title=title,
        padding={'top': 30, 'bottom': 10, 'left': 10, 'right': 10}
    )
    st.altair_chart(chart, use_container_width=True)


if selected_slide:
    st.caption(f"Chosen slide: {selected_slide['SlideTitle']}")

    df = get_question_engagement_stats(selected_slide['SlideTitle'])

    plot_chart(df, 'Accuracy', 'Accuracy Across Session')
    plot_chart(df, 'Total Submission Count', 'Total Submission Across Session')
    plot_chart(df, 'Answer Time Seconds', 'Average Answered Time Across Session')
    # chart = alt.Chart(df).mark_line(
    #         point=True,  # Add points
    #         size=3       # Line thickness
    #     ).encode(
    #     x=alt.X('Presentation:N',
    #             sort=None,
    #             axis=alt.Axis(labelAngle=-45, labelLimit=300, labelOverlap=False),
    #             scale=alt.Scale(padding=0.5)
    #             ),
    #     y='Accuracy:Q',
    # tooltip=['Presentation', 'Accuracy']
    # ).properties(
    #     width=700,
    #     height=400,
    #     title='Accuracy Across Session'
    # )
    # st.altair_chart(chart, use_container_width=True)
