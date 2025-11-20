import streamlit as st
from warehouse_repo import get_presentations_of_user
from warehouse_v5_repo import get_reactions_data_for_presentation, get_slides
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# Load the actual data
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


# ===== REACTION MAPPING (Option 2: Psychological Valence Model) =====

emotion_map = {
    'heart': {'name': 'Love/Connection', 'color': '#FF1493', 'angle': 0, 'emoji': '❤️'},
    'like': {'name': 'Positive/Approval', 'color': '#32CD32', 'angle': 60, 'emoji': '👍'},
    'laugh': {'name': 'Joy/Amusement', 'color': '#FFD700', 'angle': 120, 'emoji': '😆'},
    'wow': {'name': 'Awe/Surprise', 'color': '#FF8C00', 'angle': 180, 'emoji': '😮'},
    'sad': {'name': 'Reflection/Sadness', 'color': '#4169E1', 'angle': 240, 'emoji': '😢'},
    'question': {'name': 'Curiosity/Thinking', 'color': '#9370DB', 'angle': 300, 'emoji': '🧐'}
}

# ===== PROCESS ALL REACTIONS PER SLIDE =====

def get_all_slide_reactions(df, emotion_map):
    """Get all reaction types and counts for each slide"""
    slide_reactions = []

    for slide_order in sorted(df['Slide Order'].unique()):
        slide_df = df[df['Slide Order'] == slide_order]

        # Get slide info
        slide_title = slide_df['Slide Title'].iloc[0] if len(slide_df) > 0 else f"Slide {slide_order}"
        slide_type = slide_df['Slide Type'].iloc[0] if len(slide_df) > 0 else "Unknown"

        # Get all reaction counts for this slide
        reaction_summary = slide_df.groupby('Reaction Type').agg({
            'Submission Count': 'sum',
            'Participant Id': 'nunique'
        }).reset_index()

        # Add each reaction type as separate entry
        for _, reaction in reaction_summary.iterrows():
            reaction_type = reaction['Reaction Type']
            submission_count = reaction['Submission Count']
            participant_count = reaction['Participant Id']

            if reaction_type in emotion_map:
                emotion_config = emotion_map[reaction_type]

                slide_reactions.append({
                    'slide_order': int(slide_order),
                    'slide_title': slide_title,
                    'slide_type': slide_type,
                    'reaction_type': reaction_type,
                    'submission_count': int(submission_count),
                    'participant_count': int(participant_count),
                    'emotion_name': emotion_config['name'],
                    'emotion_color': emotion_config['color'],
                    'emotion_angle': emotion_config['angle'],
                    'emotion_emoji': emotion_config['emoji']
                })

    return pd.DataFrame(slide_reactions)


# ===== CREATE COLORED SEGMENT EMOTION WHEEL =====

def create_colored_segment_wheel(reactions_df):
    """Create emotion wheel with colored segments like the reference image"""
    fig = go.Figure()

    # Define emotion types and their angular positions
    emotions = ['heart', 'like', 'laugh', 'wow', 'sad', 'question']
    emotion_angles = {
        'heart': 0, 'like': 60, 'laugh': 120,
        'wow': 180, 'sad': 240, 'question': 300
    }
    angular_width = 60  # degrees per emotion segment

    # Get all slide numbers to determine ring structure
    slide_numbers = sorted(reactions_df['slide_order'].unique())
    max_slide = max(slide_numbers) if slide_numbers else 1

    # Calculate max submissions for opacity scaling
    max_submissions = reactions_df['submission_count'].max() if len(reactions_df) > 0 else 1

    # Track slide labels added
    labeled_slides = set()

    # Process each slide as a concentric ring
    for slide_num in slide_numbers:
        slide_data = reactions_df[reactions_df['slide_order'] == slide_num]

        # Get slide information
        slide_title = slide_data['slide_title'].iloc[0] if len(slide_data) > 0 else f"Slide {slide_num}"
        # Get slide information - cleaned for JSON safety
        raw_slide_title = slide_data['slide_title'].iloc[0] if len(slide_data) > 0 else f"Slide {slide_num}"
        slide_title = clean_text_for_json(raw_slide_title)

        # Create segments for each emotion type in this slide
        for emotion_type in emotions:
            emotion_data = slide_data[slide_data['reaction_type'] == emotion_type]
            if len(emotion_data) > 0:
                submission_count = emotion_data['submission_count'].iloc[0]
                emotion_color = emotion_data['emotion_color'].iloc[0]
                emotion_name = emotion_data['emotion_name'].iloc[0]
                emotion_emoji = emotion_data['emotion_emoji'].iloc[0]
                participant_count = emotion_data['participant_count'].iloc[0]

                # Calculate opacity based on submission count (stronger reactions = more opaque)
                opacity = 0.3 + (submission_count / max_submissions) * 0.7

            else:
                # Default values for missing emotions
                emotion_config = emotion_map.get(emotion_type, {})
                submission_count = 0
                emotion_color = emotion_config.get('color', 'lightgray')
                emotion_name = emotion_config.get('name', emotion_type)
                emotion_emoji = emotion_config.get('emoji', '❓')
                participant_count = 0
                opacity = 0.1  # Very light for no reactions

            # Create the ring segment using Barpolar
            fig.add_trace(go.Barpolar(
                r=[1],  # Always width of 1 for each ring
                theta=[emotion_angles[emotion_type]],
                width=[angular_width],
                base=slide_num - 0.5,  # Start radius for this ring
                marker=dict(
                    color=emotion_color,
                    opacity=opacity,
                    line=dict(color='white', width=1)
                ),
                name=f"Slide {slide_num}: {submission_count} {emotion_emoji}",
                showlegend=False,
                hovertemplate=(
                    f"<b>Slide #{slide_num} - {slide_title}</b><br>"
                    f"Emotion: {emotion_emoji} {emotion_name}<br>"
                    f"Reactions: {submission_count}<br>"
                    f"Participants: {participant_count}<br>"
                    f"<extra></extra>"
                )
            ))

    return fig

def clean_text_for_json(text):
    """Clean text to prevent JSON parsing issues"""
    if pd.isna(text) or text is None:
        return "Unknown"
    text = str(text)
    # Remove or escape problematic characters
    text = text.replace('"', "'")
    text = text.replace('\n', ' ')
    text = text.replace('\r', ' ')
    text = text.replace('\t', ' ')
    text = text.replace('\\', '/')
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    text = text.replace('{', '(').replace('}', ')')

    # empty string causing chart to break, so replace it with a space
    if text == '':
        text = ' '
    return text[:100]  # Limit length to prevent huge strings

def create_emotional_wheel(all_reactions_df):
    fig = create_colored_segment_wheel(all_reactions_df)

    # Configure layout
    max_slide = int(all_reactions_df['slide_order'].max()) if len(all_reactions_df) > 0 else 10

    fig.update_layout(
        title="🎭 Emotion Wheel - Colored Segments<br><sub>Each ring = slide | Each segment = emotion type | Color intensity = reaction count</sub>",
        polar=dict(
            bgcolor='rgba(250,250,250,0.8)',
            radialaxis=dict(
                visible=False,
                range=[0, max_slide + 1],
                tickmode='linear',
                tick0=1,
                dtick=1,
                title="Slide Number",
                gridcolor='lightgray',
                gridwidth=1
            ),
            angularaxis=dict(
                visible=True,
                tickmode='array',
                tickvals=[config['angle'] for config in emotion_map.values()],
                ticktext=[f"{config['emoji']} {config['name']}" for config in emotion_map.values()],
                direction='clockwise',
                rotation=0,
                gridcolor='lightgray',
                linecolor='darkgray'
            )
        ),
        width=800,
        height=800,
        showlegend=False
    )

    # Display the chart
    st.plotly_chart(fig, use_container_width=True)


def create_reaction_detailed_analysis(all_reactions_df):
    # ===== DETAILED ANALYSIS =====
    st.markdown("---")
    st.subheader("📊 Detailed Reaction Analysis")

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Slides", all_reactions_df['slide_order'].nunique())

    with col2:
        st.metric("Total Submissions", all_reactions_df['submission_count'].sum())

    with col3:
        st.metric("Reaction Types", all_reactions_df['reaction_type'].nunique())

    with col4:
        avg_per_slide = all_reactions_df.groupby('slide_order')['submission_count'].sum().mean()
        st.metric("Avg per Slide", f"{avg_per_slide:.1f}")

    # Reaction breakdown by type
    st.write("### 🎭 Overall Emotion Distribution")
    emotion_totals = all_reactions_df.groupby(['reaction_type', 'emotion_emoji', 'emotion_name'])['submission_count'].sum().reset_index()
    emotion_totals = emotion_totals.sort_values('submission_count', ascending=False)

    for _, row in emotion_totals.iterrows():
        percentage = (row['submission_count'] / emotion_totals['submission_count'].sum()) * 100
        st.write(f"{row['emotion_emoji']} **{row['emotion_name']}**: {row['submission_count']} submissions ({percentage:.1f}%)")

    # Most engaging slides
    st.write("### 🔥 Most Engaging Slides (by total reactions)")
    slide_totals = all_reactions_df.groupby(['slide_order', 'slide_title'])['submission_count'].sum().reset_index()
    slide_totals = slide_totals.sort_values('submission_count', ascending=False).head(5)

    for _, slide in slide_totals.iterrows():
        st.write(f"**Slide {slide['slide_order']}**: {slide['slide_title']} - {slide['submission_count']} total reactions")

    # Export functionality
    if st.button("💾 Export Colored Segment Data"):
        all_reactions_df.to_csv('/mnt/user-data/outputs/colored_segment_reactions.csv', index=False)
        st.success("✅ Colored segment reaction data exported!")


if __name__ == "__main__":
    params = st.query_params
    user_id = params.get('user_id', 1918789)
    presentation_df = get_presentations_of_user(user_id)

    presentations = presentation_df.to_dict(orient='records')

    default_idx = 1
    selected_presentation = st.selectbox('Select presentation:', list(presentations), format_func=lambda x: x['name'], index=default_idx)
    st.session_state.selected_presentation = selected_presentation

    if st.session_state.selected_presentation:
        presentation_id = st.session_state.selected_presentation['id']
    else:
        presentation_id = 7021758

    presentation_id = 4405400

    # Load data
    df = load_reaction_data(presentation_id)
    st.title("🎭 Emotion Wheel - Colored Segments")
    st.write("Each ring represents a slide, each colored segment shows reaction intensity")

    # Show basic data info
    st.write(f"**Total reactions:** {len(df)} | **Unique slides:** {df['Slide Order'].nunique()} | **Participants:** {df['Participant Id'].nunique()}")
    # Process all reactions
    all_reactions_df = get_all_slide_reactions(df, emotion_map)

    # Display processed data
    if len(all_reactions_df) > 0:
        st.write("### 📊 All Reactions per Slide")
        display_df = all_reactions_df[['slide_order', 'slide_title', 'reaction_type', 'emotion_emoji', 'submission_count', 'participant_count']].copy()
        display_df.columns = ['Slide', 'Title', 'Reaction Type', 'Emoji', 'Submissions', 'Participants']
        st.dataframe(display_df, width='stretch')
    else:
        st.warning("No reaction data found for this presentation.")
        st.stop()

    #Create the chart
    if len(all_reactions_df) > 0:
        create_emotional_wheel(all_reactions_df)
    else:
        st.error("No data to display.")

    st.markdown("""
    ---
    ### 📖 How to Read This Colored Segment Emotion Wheel:

    - **Each concentric ring** = One slide (inner rings = early slides)
    - **Each colored segment** = One emotion type (❤️ Heart, 👍 Like, etc.)
    - **Color intensity/opacity** = Number of reactions (darker = more reactions)
    - **Angular position** = Emotion type (consistent across all slides)
    - **White lines** = Segment boundaries for clear separation

    **Example**: In slide 3's ring, if you see:
    - Bright pink segment at top = Many heart reactions
    - Light green segment at right = Few like reactions
    - Dark gold segment = Many laugh reactions

    This gives you a **complete emotional landscape** for each slide! 🎭
    """)