from emotional_wheel_dashboard import create_emotional_wheel, get_all_slide_reactions, load_reaction_data
from emotional_wheel_dashboard import emotion_map
from pulse_dashboard import create_minimal_pulse, create_pulse_chart, enrich_interaction_data
import streamlit as st
from warehouse_repo import get_interactions_of_presentation, get_presentations_of_user


if __name__ == "__main__":

    st.set_page_config(layout="wide")
    col1, col2 = st.columns([3, 1])

    params = st.query_params
    user_id = params.get('user_id', 1918789)
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

    df = get_interactions_of_presentation(presentation_id)

    if len(df) > 0:
        reaction_df = enrich_interaction_data(df)
        minimal_pulse_df = create_minimal_pulse(reaction_df, 'Percent of engaged audience')
        create_pulse_chart(minimal_pulse_df)
    else:
        st.error('No participant response to display.')

    df = load_reaction_data(presentation_id)
    all_reactions_df = get_all_slide_reactions(df, emotion_map)
    #Create the chart
    if len(all_reactions_df) > 0:
        create_emotional_wheel(all_reactions_df)
    else:
        st.error("No reaction to display.")