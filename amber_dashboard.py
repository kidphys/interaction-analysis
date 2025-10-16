import streamlit as st
from warehouse_v5_repo import get_reactions_data_for_presentation, get_recent_presentations, get_recent_presentations_by_reaction, get_recent_presentations_fast, get_slides



st.set_page_config(layout="wide")
user_id = 3802280


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

    # Default selection (first presentation)
    default_presentation = presentation_options[0] if presentation_options else None

    selected_presentation = st.selectbox(
        "Select Presentation:",
        options=presentation_options,
        format_func=lambda x: f"{x['title'][:50]}{'...' if len(x['title']) > 50 else ''}",
        index=0 if presentation_options else None,
        key="selected_presentation"
    )

    if selected_presentation:
        st.caption(f"Last activity: {selected_presentation['last_answered']}")

# Store selected presentation ID for use throughout the dashboard
presentation_id = selected_presentation['id'] if selected_presentation else None


with col_title:
    reactions = get_reactions_data_for_presentation(presentation_id)
    slides = get_slides(presentation_id)
    df = reactions.merge(slides, on='Slide Id')
    df = df[df['Deleted'] == False]
    df = df.drop('Deleted', axis=1)
    st.write(df)
