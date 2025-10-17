import streamlit as st
from data_commentor_agent import ChartData, get_comment
from warehouse_v5_repo import get_reactions_data_for_presentation, get_recent_presentations, get_recent_presentations_by_reaction, get_recent_presentations_fast, get_slides
import altair as alt



def build_reaction_dashboard(user_id):
    recent_presentations = get_recent_presentations(user_id)

    # Dashboard header with presentation selector
    col_title, col_selector = st.columns([2, 1])

    with col_selector:
        st.markdown("")  # Add spacing to align with title

        # Create options for selectbox
        presentation_options = []
        for _, row in recent_presentations.iterrows():
            presentation_options.append({
                'id': row['Id'],
                'title': row['Title'],
                'last_answered': row['Last Answered At']
            })


        selected_presentation_reaction = st.selectbox(
            "Select Presentation:",
            options=presentation_options,
            format_func=lambda x: f"{x['title'][:50]}{'...' if len(x['title']) > 50 else ''}",
            index=0 if presentation_options else None,
            key="selected_presentation_reaction"
        )

        if selected_presentation_reaction:
            st.caption(f"Last activity: {selected_presentation_reaction['last_answered']}")

    # Store selected presentation ID for use throughout the dashboard
    presentation_id = selected_presentation_reaction['id'] if selected_presentation_reaction else None

    reactions = get_reactions_data_for_presentation(presentation_id)
    slides = get_slides(presentation_id)
    df = reactions.merge(slides, on='Slide Id')
    df = df[df['Deleted'] == False]
    df = df.drop('Deleted', axis=1)

    reaction_to_emoji = {
        'heart': '❤️',
        'like': '👍',
        'sad': '😢',
        'wow': '😮',
        'question': '🧐',
        'laugh': '😆'
    }

    df['Reaction'] = df['Reaction Type'].map(lambda x: reaction_to_emoji.get(x, '👀'))
    df = df.rename(columns={'Submission Count': 'Reaction Count'})
    df = df.sort_values(by='Slide Order')
    df['Slide Idx'] = df['Slide Order'].rank(method='dense').astype(int)
    df = df.drop('Reaction Type', axis=1)
    tf = df.groupby(['Slide Idx', 'Slide Order', 'Slide Title', 'Reaction']).agg({'Reaction Count': 'sum', 'Participant Id': 'nunique'})
    tf = tf.rename(columns={'Participant Id': 'Participant Count'})
    tf = tf.reset_index()



    with col_title:

        st.subheader('Reactions during your session')
        chart = alt.Chart(tf).mark_line(
                point=True,  # Add points
                size=3       # Line thickness
            ).encode(
            x=alt.X('Slide Idx:N',
                    sort=None,
                    axis=alt.Axis(labels=False,           # Hide the labels
                    title='Slides', labelAngle=-60, labelLimit=300, labelOverlap=False),
                    scale=alt.Scale(padding=0.5)
                    ),
            y=f'Reaction Count:Q',
            color='Reaction',
        tooltip=['Slide Title', 'Reaction', 'Reaction Count', 'Participant Count']
        ).properties(
            width=800,
        )
        st.altair_chart(chart, use_container_width=True)


    data_col, ai_col = st.columns([2, 1])

    with data_col:
        st.subheader('Slides Stats')
        simple_tf = tf[[col for col in tf.columns if col not in ['Slide Order']]]
        st.dataframe(simple_tf, hide_index=True)
        simple_df =df[['Slide Idx', 'Slide Title', 'Slide Type', 'Participant Name', 'Participant Email', 'Reaction', 'Reaction Count']]
        st.subheader('Raw Data')
        st.dataframe(simple_df, hide_index=True)

    with ai_col:
        if st.button('Analyze with AI...'):
            with st.spinner('Thinking about your data...'):
                slide_reaction_data = ChartData(description='Slide Reaction stats', data=simple_tf.to_dict(orient='records'))
                reaction_raw_data = ChartData(description='Reaction Raw Data', data=simple_df.to_dict(orient='records'))
                comment = get_comment([slide_reaction_data, reaction_raw_data])
                st.write(comment)

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    user_id = 3802280


    build_reaction_dashboard(user_id)