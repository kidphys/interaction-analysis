import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


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
                            f"<b>Slide {slide_num}</b><br>" +
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


def main():

    try:
        df = pd.read_csv("~/Documents/2025-11-21T06-56_export.csv")
        df = df.dropna(subset=['slide_order', 'reaction_type', 'submission_count'])

        create_progressive_ring_wheel(df)
    except Exception as e:
        st.error(f"Error loading your data: {e}")


if __name__ == "__main__":
    main()