from emotional_wheel_dashboard import create_emotional_wheel, create_emotional_wheel_autoplay, get_all_slide_reactions, load_reaction_data
from emotional_wheel_dashboard import emotion_map
from fast_wheel_dashboard import create_progressive_ring_wheel
from pulse_dashboard import create_minimal_pulse, create_pulse_chart, enrich_interaction_data
import streamlit as st
from warehouse_repo import get_interactions_of_presentation, get_presentations_of_user
from warehouse_v5_repo import get_all_answers_full


def make_legacy_compatible(answer_df):
    # convert data to make it compatible with output of this line
    # df = get_interactions_of_presentation(presentation_id)
    answer_df['audienceid'] = answer_df['Participant Id']
    answer_df['Slideid'] = answer_df['Slide Id']
    answer_df['Slidetitle'] = answer_df['Slide Title']
    answer_df['Slideorder'] = answer_df['Slide Order']
    answer_df['Slidetypenormalized'] = answer_df['Slide Type']
    return answer_df

if __name__ == "__main__":
    # Add this to your Streamlit app
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono&display=swap');
    </style>
    """, unsafe_allow_html=True)

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

    presentation_id = 6801653

    df = get_all_answers_full(presentation_id)
    df = make_legacy_compatible(df)


    # if len(df) > 0:
    #     reaction_df = enrich_interaction_data(df)
    #     minimal_pulse_df = create_minimal_pulse(reaction_df, 'Percent of engaged audience')
    #     create_pulse_chart(minimal_pulse_df)
    # else:
    #     st.error('No participant response to display.')

    df = load_reaction_data(presentation_id)

    all_reactions_df = get_all_slide_reactions(df, emotion_map)

    with col1:
        if len(all_reactions_df) > 0:
            create_progressive_ring_wheel(all_reactions_df)
        else:
            st.error("No reaction to display.")