import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Event Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .filter-section {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file_path):
    """Load and preprocess the interaction data"""
    try:
        df = pd.read_csv(file_path, low_memory=False)

        # Convert date columns to datetime
        date_columns = ['Createdat', 'Updatedat', 'Answeredtimestamp',
                       'Audience Created At', 'Audience Updated At',
                       'Slide Created At', 'Slide Updated At']

        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], format='%d-%m-%Y, %H:%M', errors='coerce')

        # Clean up interaction source
        if 'Interaction Source' in df.columns:
            df['Interaction Source'] = df['Interaction Source'].fillna('unknown')

        # Clean up slide type
        if 'Slidetypenormalized' in df.columns:
            df['Slidetypenormalized'] = df['Slidetypenormalized'].fillna('unknown')

        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

def parse_json_options(options_str):
    """Safely parse JSON options"""
    try:
        if pd.isna(options_str) or options_str == '':
            return []
        return json.loads(options_str)
    except:
        return []

def get_event_properties(df):
    """Extract and categorize event properties"""
    properties = {}

    # Basic event properties
    if 'Interaction Source' in df.columns:
        properties['Event Type'] = df['Interaction Source'].unique().tolist()

    if 'Slidetypenormalized' in df.columns:
        properties['Slide Type'] = df['Slidetypenormalized'].unique().tolist()

    if 'Presentation Name' in df.columns:
        properties['Presentation'] = df['Presentation Name'].unique().tolist()

    if 'Team Name' in df.columns:
        properties['Team'] = df['Team Name'].dropna().unique().tolist()

    if 'Audience Name' in df.columns:
        properties['Audience'] = df['Audience Name'].dropna().unique().tolist()

    # Reaction types
    if 'Reactiontype' in df.columns:
        properties['Reaction Type'] = df['Reactiontype'].dropna().unique().tolist()

    # Poll options (extract from first few rows)
    if 'Slideoptions' in df.columns:
        sample_options = df['Slideoptions'].dropna().head(100)
        all_options = []
        for opt in sample_options:
            parsed = parse_json_options(opt)
            if parsed:
                all_options.extend([item.get('title', '') for item in parsed if item.get('title')])
        properties['Poll Options'] = list(set(all_options))[:20]  # Limit to 20 unique options

    return properties

def filter_data(df, filters):
    """Apply filters to the dataset"""
    filtered_df = df.copy()

    for filter_name, filter_value in filters.items():
        if filter_value and filter_value != 'All':
            if filter_name == 'Event Type':
                filtered_df = filtered_df[filtered_df['Interaction Source'] == filter_value]
            elif filter_name == 'Slide Type':
                filtered_df = filtered_df[filtered_df['Slidetypenormalized'] == filter_value]
            elif filter_name == 'Presentation':
                filtered_df = filtered_df[filtered_df['Presentation Name'] == filter_value]
            elif filter_name == 'Team':
                filtered_df = filtered_df[filtered_df['Team Name'] == filter_value]
            elif filter_name == 'Reaction Type':
                filtered_df = filtered_df[filtered_df['Reactiontype'] == filter_value]

    return filtered_df

def create_time_series_data(df, time_column='Createdat', time_granularity='1H'):
    """Create time series data for events and distinct properties"""
    if time_column not in df.columns:
        st.error(f"Time column '{time_column}' not found in data")
        return None, None

    # Remove rows with missing timestamps
    df_clean = df.dropna(subset=[time_column])

    if df_clean.empty:
        st.error("No valid timestamps found in data")
        return None, None

    # Set time column as index and resample
    df_clean = df_clean.set_index(time_column).sort_index()

    # Event count over time
    event_counts = df_clean.resample(time_granularity).size()

    # Distinct properties count over time
    distinct_properties = df_clean.resample(time_granularity).agg({
        'Interaction Source': 'nunique',
        'Slidetypenormalized': 'nunique',
        'Audienceid': 'nunique',
        'Slideid': 'nunique'
    }).sum(axis=1)

    return event_counts, distinct_properties

def create_charts(event_counts, distinct_properties, filters_applied):
    """Create the main charts"""
    if event_counts is None or distinct_properties is None:
        return

    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Event Count Over Time', 'Distinct Properties Count Over Time'),
        vertical_spacing=0.1,
        shared_xaxes=True
    )

    # Event count chart
    fig.add_trace(
        go.Scatter(
            x=event_counts.index,
            y=event_counts.values,
            mode='lines+markers',
            name='Event Count',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6)
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
            line=dict(color='#ff7f0e', width=2),
            marker=dict(size=6)
        ),
        row=2, col=1
    )

    # Update layout
    fig.update_layout(
        height=600,
        showlegend=True,
        title_text=f"Event Analysis Dashboard{f' - Filtered by: {', '.join([f'{k}: {v}' for k, v in filters_applied.items() if v != 'All'])}' if any(v != 'All' for v in filters_applied.values()) else ''}",
        title_x=0.5
    )

    # Update axes labels
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=1)

    return fig

def main():
    st.markdown('<h1 class="main-header">📊 Event Analysis Dashboard</h1>', unsafe_allow_html=True)

    # Sidebar for file selection and filters
    st.sidebar.header("📁 Data & Filters")

    # File selection
    file_options = {
        'Sample Data': 'sample_presentation_data.csv',
        'Dave Presentation': 'dave_presentation_interactions.csv',
        'Duke Presentation': 'duke_presentation_interactions.csv'
    }

    selected_file = st.sidebar.selectbox(
        "Select Data File",
        options=list(file_options.keys()),
        index=0
    )

    # Load data
    df = load_data(file_options[selected_file])

    if df is None:
        st.error("Failed to load data. Please check your file.")
        return

    # Display data info
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Dataset Info:**")
    st.sidebar.markdown(f"📊 **Total Rows:** {len(df):,}")
    st.sidebar.markdown(f"📅 **Date Range:** {df['Createdat'].min().strftime('%Y-%m-%d') if 'Createdat' in df.columns and not df['Createdat'].isna().all() else 'N/A'} to {df['Createdat'].max().strftime('%Y-%m-%d') if 'Createdat' in df.columns and not df['Createdat'].isna().all() else 'N/A'}")

    # Get available properties for filtering
    properties = get_event_properties(df)

    # Filter section
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔍 Filters**")

    filters = {}
    for prop_name, prop_values in properties.items():
        if prop_values:
            # Add 'All' option
            all_values = ['All'] + sorted(prop_values)
            selected_value = st.sidebar.selectbox(
                f"Filter by {prop_name}",
                options=all_values,
                index=0
            )
            filters[prop_name] = selected_value

    # Time granularity selection
    st.sidebar.markdown("---")
    st.sidebar.markdown("**⏰ Time Granularity**")
    time_granularity = st.sidebar.selectbox(
        "Select time grouping",
        options=['1H', '2H', '4H', '6H', '12H', '1D'],
        index=0
    )

    # Apply filters
    filtered_df = filter_data(df, filters)

    # Main content area
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Events",
            f"{len(filtered_df):,}",
            delta=f"{len(filtered_df) - len(df):,}" if len(filtered_df) != len(df) else None
        )

    with col2:
        if 'Audienceid' in filtered_df.columns:
            unique_audiences = filtered_df['Audienceid'].nunique()
            st.metric("Unique Audiences", f"{unique_audiences:,}")

    with col3:
        if 'Slideid' in filtered_df.columns:
            unique_slides = filtered_df['Slideid'].nunique()
            st.metric("Unique Slides", f"{unique_slides:,}")

    with col4:
        if 'Interaction Source' in filtered_df.columns:
            event_types = filtered_df['Interaction Source'].nunique()
            st.metric("Event Types", f"{event_types:,}")

    # Create time series data
    event_counts, distinct_properties = create_time_series_data(
        filtered_df,
        time_column='Createdat',
        time_granularity=time_granularity
    )

    # Create and display charts
    if event_counts is not None and distinct_properties is not None:
        fig = create_charts(event_counts, distinct_properties, filters)
        st.plotly_chart(fig, use_container_width=True)

        # Additional insights
        st.markdown("---")
        st.subheader("📈 Key Insights")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Event Count Analysis:**")
            if len(event_counts) > 0:
                st.markdown(f"• **Peak Events:** {event_counts.max():.0f} events at {event_counts.idxmax().strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"• **Average Events:** {event_counts.mean():.1f} events per {time_granularity}")
                st.markdown(f"• **Total Time Periods:** {len(event_counts)} periods")

        with col2:
            st.markdown("**Properties Analysis:**")
            if len(distinct_properties) > 0:
                st.markdown(f"• **Peak Properties:** {distinct_properties.max():.0f} distinct properties at {distinct_properties.idxmax().strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"• **Average Properties:** {distinct_properties.mean():.1f} distinct properties per {time_granularity}")

    # Data table view
    st.markdown("---")
    st.subheader("📋 Filtered Data Preview")

    # Show relevant columns
    display_columns = ['Createdat', 'Interaction Source', 'Slidetypenormalized',
                      'Slidetitle', 'Audience Name', 'Team Name', 'Presentation Name']

    available_columns = [col for col in display_columns if col in filtered_df.columns]

    if available_columns:
        st.dataframe(
            filtered_df[available_columns].head(100),
            use_container_width=True
        )
    else:
        st.info("No displayable columns found in the filtered data.")

if __name__ == "__main__":
    main()