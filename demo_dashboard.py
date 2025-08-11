import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Event Analysis Demo",
    page_icon="📊",
    layout="wide"
)

def load_sample_data():
    """Load the sample presentation data"""
    try:
        df = pd.read_csv('sample_presentation_data.csv', low_memory=False)

        # Convert date columns to datetime
        if 'Createdat' in df.columns:
            df['Createdat'] = pd.to_datetime(df['Createdat'], format='%d-%m-%Y, %H:%M', errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error loading sample data: {e}")
        return None

def create_simple_charts(df):
    """Create simple charts for demonstration"""
    if 'Createdat' not in df.columns:
        st.error("Createdat column not found")
        return None

    # Remove rows with missing timestamps
    df_clean = df.dropna(subset=['Createdat'])

    if df_clean.empty:
        st.error("No valid timestamps found")
        return None

    # Set time column as index and resample hourly
    df_clean = df_clean.set_index('Createdat').sort_index()

    # Event count over time (hourly)
    event_counts = df_clean.resample('1H').size()

    # Distinct properties count over time
    distinct_properties = df_clean.resample('1H').agg({
        'Interaction Source': 'nunique',
        'Slidetypenormalized': 'nunique',
        'Audienceid': 'nunique'
    }).sum(axis=1)

    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Event Count Over Time (Hourly)', 'Distinct Properties Count Over Time (Hourly)'),
        vertical_spacing=0.1
    )

    # Event count chart
    fig.add_trace(
        go.Scatter(
            x=event_counts.index,
            y=event_counts.values,
            mode='lines+markers',
            name='Event Count',
            line=dict(color='#1f77b4', width=2)
        ),
        row=1, col=1
    )

    # Distinct properties chart
    fig.add_trace(
        go.Scatter(
            x=distinct_properties.index,
            y=distinct_properties.values,
            mode='lines+markers',
            name='Distinct Properties',
            line=dict(color='#ff7f0e', width=2)
        ),
        row=2, col=1
    )

    fig.update_layout(height=600, showlegend=True)
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=1)

    return fig, event_counts, distinct_properties

def main():
    st.title("📊 Event Analysis Dashboard - Demo")
    st.markdown("This is a simplified demo of the event analysis dashboard.")

    # Load data
    df = load_sample_data()

    if df is None:
        st.error("Failed to load sample data. Please ensure 'sample_presentation_data.csv' is in the current directory.")
        return

    # Display basic info
    st.sidebar.header("📊 Dataset Info")
    st.sidebar.markdown(f"**Total Rows:** {len(df):,}")

    if 'Createdat' in df.columns and not df['Createdat'].isna().all():
        st.sidebar.markdown(f"**Date Range:** {df['Createdat'].min().strftime('%Y-%m-%d')} to {df['Createdat'].max().strftime('%Y-%m-%d')}")

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Events", f"{len(df):,}")

    with col2:
        if 'Audienceid' in df.columns:
            unique_audiences = df['Audienceid'].nunique()
            st.metric("Unique Audiences", f"{unique_audiences:,}")

    with col3:
        if 'Slideid' in df.columns:
            unique_slides = df['Slideid'].nunique()
            st.metric("Unique Slides", f"{unique_slides:,}")

    with col4:
        if 'Interaction Source' in df.columns:
            event_types = df['Interaction Source'].nunique()
            st.metric("Event Types", f"{event_types:,}")

    # Create and display charts
    st.markdown("---")
    st.subheader("📈 Event Analysis Charts")

    fig, event_counts, distinct_properties = create_simple_charts(df)

    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)

        # Display insights
        st.markdown("---")
        st.subheader("📊 Key Insights")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Event Count Analysis:**")
            if event_counts is not None and len(event_counts) > 0:
                st.markdown(f"• **Peak Events:** {event_counts.max():.0f} events at {event_counts.idxmax().strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"• **Average Events:** {event_counts.mean():.1f} events per hour")
                st.markdown(f"• **Total Hours:** {len(event_counts)} hours")

        with col2:
            st.markdown("**Properties Analysis:**")
            if distinct_properties is not None and len(distinct_properties) > 0:
                st.markdown(f"• **Peak Properties:** {distinct_properties.max():.0f} distinct properties at {distinct_properties.idxmax().strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"• **Average Properties:** {distinct_properties.mean():.1f} distinct properties per hour")

    # Data preview
    st.markdown("---")
    st.subheader("📋 Data Preview")

    # Show relevant columns
    display_columns = ['Createdat', 'Interaction Source', 'Slidetypenormalized',
                      'Slidetitle', 'Audience Name', 'Team Name', 'Presentation Name']

    available_columns = [col for col in display_columns if col in df.columns]

    if available_columns:
        st.dataframe(
            df[available_columns].head(50),
            use_container_width=True
        )
    else:
        st.info("No displayable columns found in the data.")

    # Event type breakdown
    st.markdown("---")
    st.subheader("🔍 Event Type Breakdown")

    if 'Interaction Source' in df.columns:
        event_counts = df['Interaction Source'].value_counts()
        st.bar_chart(event_counts)

        st.markdown("**Event Type Details:**")
        for event_type, count in event_counts.items():
            st.markdown(f"• **{event_type}**: {count:,} events")

if __name__ == "__main__":
    main()