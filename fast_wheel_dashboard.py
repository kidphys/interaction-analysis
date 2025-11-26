from emotional_wheel_dashboard import emotion_map, get_all_slide_reactions
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from user_map import user_map
from warehouse_repo import get_presentations_of_user
from warehouse_v5_repo import get_reactions_data_for_presentation, get_slides


def create_progressive_ring_wheel(ring_df):
    """
    Alternative approach: Build rings progressively without complex frame management
    """
    chart_placeholder = st.empty()
    progress_bar = st.progress(0)

    slides = sorted(ring_df['slide_order'].unique())

    max_count = ring_df['submission_count'].max()

    # Build progressively
    for frame_idx, current_slide in enumerate(slides):
        # Create figure with all slides up to current
        fig = go.Figure()

        visible_slides = slides[:frame_idx + 1]

        for slide_num in visible_slides:
            slide_data = ring_df[ring_df['slide_order'] == slide_num]
            slide_title = slide_data['slide_title'].iloc[0]

            for _, row in slide_data.iterrows():
                if row['submission_count'] > 0:
                    intensity = 0.3 + (row['submission_count'] / max_count) * 0.7
                    angular_width = 72

                    fig.add_trace(go.Barpolar(
                        # r=[row['submission_count']],
                        r=[1.1],
                        theta=[row['emotion_angle']],
                        width=[angular_width],
                        base=[slide_num - 0.5],
                        marker=dict(
                            color=row['emotion_color'],
                            opacity=intensity,
                            line=dict(color='white', width=1)
                        ),
                        showlegend=False,
                        hovertemplate=(
                            f"<b>Slide {slide_num} - {slide_title} </b><br>" +
                            f"Emotion: {row['emotion_emoji']} {row['emotion_name']}<br>" +
                            f"Reactions: {row['submission_count']}<br>" +
                            f"Participants: {row['participant_count']}<br>" +
                            "<extra></extra>"
                        )
                    ))

        # Update layout
        fig.update_layout(
            title=f"🎭 Emotion Rings",
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, len(slides) + max_count],
                    showticklabels=True,
                    gridcolor='lightgray'
                ),
                angularaxis=dict(
                    visible=True,
                    direction='clockwise',
                    tickmode='array',
                    tickvals=[i * angular_width for i in range(5)],
                    ticktext=['❤️ Love/Connection', '👍 Positive/Approval', '😆 Joy/Amusement', '😮 Awe/Surprise', '😢 Sad/Reflection']
                )
            ),            # Proper margins for text visibility
            margin=dict(
                l=120,    # Left margin
                r=120,    # Right margin
                t=120,    # Top margin
                b=120,    # Bottom margin
                pad=10            # Padding
            ),
            width=900,
            height=900
        )

        # Update chart
        chart_placeholder.plotly_chart(fig, use_container_width=False, key=f"ring_{frame_idx}")

        # Small delay for animation effect
        if frame_idx < len(slides) - 1:
            import time
            delay = 0.4 / (frame_idx + 1) # getting faster
            time.sleep(delay)

    progress_bar.empty()
    st.success("✨ Ring building complete!")
    return fig

@st.cache_data
def load_reaction_data(presentation_id):
    """Load and process the reaction data"""
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

    return df


def main():
    st.set_page_config(layout="wide")
    col1, col2 = st.columns([3, 1])

    params = st.query_params
    user = params.get('user', 'cheryl')
    if user not in user_map:
        st.write('Not supported user')
        return
    user_id = user_map.get(user)
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

    try:
        df = load_reaction_data(presentation_id)
        all_reactions_df = get_all_slide_reactions(df, emotion_map)

        if len(all_reactions_df) > 0:
            create_progressive_ring_wheel(all_reactions_df)
        else:
            st.write('No reaction data')
    except Exception as e:
        st.error(f"Error loading your data: {e}")


if __name__ == "__main__":
    main()