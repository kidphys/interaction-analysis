"""
Streamlit Dashboard for Session Insight Analysis
Runs the session insight graph and visualizes the output with interactive charts and insights.
"""

import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import List, Dict, Any
import sys
import os
from datetime import datetime
import tempfile

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the graph creation function
try:
    from session_insight.graph import create_session_insight_graph
    GRAPH_AVAILABLE = True
except ImportError as e:
    GRAPH_AVAILABLE = False
    GRAPH_IMPORT_ERROR = str(e)
    import traceback
    print(traceback.format_exc())

# Page configuration
st.set_page_config(
    page_title="Session Insight Dashboard",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# Custom CSS for better aesthetics
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .insight-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .coaching-card {
        background-color: #f0f7ff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #3498db;
        margin-bottom: 25px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .recommendation-card {
        background-color: #e8f4f8;
        padding: 15px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 4px solid #2ecc71;
    }
    .observation-card {
        background-color: #fff9e6;
        padding: 15px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 4px solid #f39c12;
    }
    .coaching-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
        font-size: 1.1em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    h1 {
        color: #1f77b4;
    }
    h2 {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
    }
    h3 {
        color: #34495e;
    }
    </style>
""", unsafe_allow_html=True)


def load_analysis_results(file_path: str) -> Dict[str, Any]:
    """Load analysis results from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Handle both new dict structure and old list structure
            if isinstance(data, dict):
                return {
                    "insights": data.get("detailed_insights", []),
                    "coaching_summary": data.get("coaching_summary", ""),
                    "presentation_id": data.get("presentation_id", "Unknown")
                }
            elif isinstance(data, list):
                return {
                    "insights": data,
                    "coaching_summary": "",
                    "presentation_id": "Unknown"
                }
            return {"insights": [], "coaching_summary": "", "presentation_id": "Unknown"}
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return {"insights": [], "coaching_summary": "", "presentation_id": "Unknown"}


def extract_slide_data(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """Extract slide-level data from analysis results."""
    slide_data = []

    for result in results:
        if 'source_data' in result and isinstance(result['source_data'], list):
            for slide in result['source_data']:
                if 'slide_index' in slide:
                    slide_data.append(slide)

    if slide_data:
        df = pd.DataFrame(slide_data)

        # Merge data from different analyses for the same slide
        if 'slide_index' in df.columns:
            # Group by slide_index and aggregate
            agg_dict = {}

            # For each column, determine how to aggregate
            for col in df.columns:
                if col == 'slide_index':
                    continue
                elif col in ['slide_title', 'slide_type']:
                    agg_dict[col] = 'first'  # Take first non-null value
                elif col in ['participants', 'total_responses', 'distinct_responses', 'responses', 'accuracy', 'answer_variability']:
                    agg_dict[col] = 'max'  # Take max to get the most complete data
                else:
                    agg_dict[col] = 'first'

            # Group and aggregate
            df = df.groupby('slide_index', as_index=False).agg(agg_dict)

            # Sort by slide_index
            df = df.sort_values('slide_index').reset_index(drop=True)

        return df
    return pd.DataFrame()


def create_participation_chart(df: pd.DataFrame) -> go.Figure:
    """Create an interactive participation chart."""
    if df.empty or 'slide_index' not in df.columns:
        return None

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['slide_index'],
        y=df.get('participants', df.get('total_responses', [])),
        text=df.get('participants', df.get('total_responses', [])),
        textposition='auto',
        marker=dict(
            color=df.get('participants', df.get('total_responses', [])),
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Participants")
        ),
        hovertemplate='<b>Slide %{x}</b><br>' +
                      'Participants: %{y}<br>' +
                      '<extra></extra>'
    ))

    fig.update_layout(
        title="Participation by Slide",
        xaxis_title="Slide Index",
        yaxis_title="Number of Participants",
        template="plotly_white",
        height=400,
        hovermode='x unified'
    )

    return fig


def create_accuracy_chart(df: pd.DataFrame) -> go.Figure:
    """Create an accuracy comparison chart."""
    if df.empty or 'accuracy' not in df.columns:
        return None

    # Filter out slides with 0 accuracy (polls)
    df_filtered = df[df['accuracy'] > 0].copy()

    if df_filtered.empty:
        return None

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_filtered['slide_index'],
        y=df_filtered['accuracy'] * 100,
        text=[f"{val:.1f}%" for val in df_filtered['accuracy'] * 100],
        textposition='auto',
        marker=dict(
            color=df_filtered['accuracy'] * 100,
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Accuracy %")
        ),
        hovertemplate='<b>Slide %{x}</b><br>' +
                      'Accuracy: %{y:.1f}%<br>' +
                      '<extra></extra>'
    ))

    fig.update_layout(
        title="Accuracy by Slide (Quiz Slides Only)",
        xaxis_title="Slide Index",
        yaxis_title="Accuracy (%)",
        template="plotly_white",
        height=400,
        hovermode='x unified'
    )

    return fig


def create_slide_type_distribution(df: pd.DataFrame) -> go.Figure:
    """Create a pie chart showing slide type distribution."""
    if df.empty or 'slide_type' not in df.columns:
        return None

    type_counts = df['slide_type'].value_counts()

    fig = go.Figure(data=[go.Pie(
        labels=type_counts.index,
        values=type_counts.values,
        hole=0.4,
        marker=dict(colors=px.colors.qualitative.Set3),
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>' +
                      'Count: %{value}<br>' +
                      'Percentage: %{percent}<br>' +
                      '<extra></extra>'
    )])

    fig.update_layout(
        title="Slide Type Distribution",
        template="plotly_white",
        height=400
    )

    return fig


def create_diversity_chart(df: pd.DataFrame) -> go.Figure:
    """Create a chart showing response diversity."""
    if df.empty or 'distinct_responses' not in df.columns or 'total_responses' not in df.columns:
        return None

    df_filtered = df[df['total_responses'] > 0].copy()
    df_filtered['diversity_ratio'] = df_filtered['distinct_responses'] / df_filtered['total_responses']

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_filtered['slide_index'],
        y=df_filtered['diversity_ratio'] * 100,
        mode='lines+markers',
        marker=dict(
            size=10,
            color=df_filtered['diversity_ratio'] * 100,
            colorscale='Plasma',
            showscale=True,
            colorbar=dict(title="Diversity %")
        ),
        line=dict(width=2, color='rgba(100, 100, 100, 0.3)'),
        text=df_filtered['slide_type'],
        hovertemplate='<b>Slide %{x}</b><br>' +
                      'Type: %{text}<br>' +
                      'Diversity: %{y:.1f}%<br>' +
                      '<extra></extra>'
    ))

    fig.update_layout(
        title="Response Diversity by Slide",
        xaxis_title="Slide Index",
        yaxis_title="Diversity Ratio (%)",
        template="plotly_white",
        height=400,
        hovermode='x unified'
    )

    return fig


def display_scope_metrics(result: Dict[str, Any]):
    """Display metadata metrics and coaching message for a single scope analyze."""
    metadata = result.get('metadata', {})
    confidence = metadata.get('confidence_level', 'Unknown')
    assumptions = metadata.get('assumptions_applied', [])
    coaching_message = result.get('coaching_message')

    st.subheader('🌟 Expert Feedback')
    st.markdown(coaching_message)

    # st.markdown("#### ⚙️ Analysis Parameters")
    # col1, col2 = st.columns([1, 2])
    # with col1:
    #     confidence_color = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}.get(confidence, '⚪')
    #     st.markdown(f"**Confidence:** {confidence_color} {confidence.title()}")
    # with col2:
    #     if assumptions:
    #         st.markdown("**Assumptions Applied:**")
    #         for a in assumptions:
    #             st.markdown(f"- {a}")
    # st.markdown("---")


def display_observations_for_scope(observations: List[Dict[str, Any]]):
    """Display key observations for a specific scope."""
    if not observations:
        return

    st.subheader("🔍 Key Observations")
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    sorted_obs = sorted(observations, key=lambda x: severity_order.get(x.get('severity', 'low'), 3))

    for obs in sorted_obs:
        severity = obs.get('severity', 'low')
        severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
        st.markdown(f"{severity_emoji.get(severity, '⚪')} - {obs.get('observation', 'N/A')}")
        col1, col2 = st.columns([1, 5])
        with col1:
            st.badge("Evidence")
        with col2:
            st.caption(f"{obs.get('evidence', 'N/A')}")


def display_insights_for_scope(insights: List[Dict[str, Any]]):
    """Display interpretations for a specific scope."""
    if not insights:
        return

    st.subheader("💡 Insights & Interpretations")
    for interp in insights:
        st.markdown(f"💡 - {interp.get('insight', 'N/A')}")
        col1, col2 = st.columns([1, 5])
        with col1:
            st.badge("Explanation")
        with col2:
            st.caption(f"{interp.get('explanation', 'N/A')}")
            if interp.get('alternative_explanations'):
                with st.expander("Show Alternative Explanations"):
                    for alt in interp['alternative_explanations']:
                        st.caption(f"- {alt}")


def display_recommendations_for_scope(recommendations: List[Dict[str, Any]]):
    """Display recommendations for a specific scope."""
    if not recommendations:
        return

    st.subheader("🎯 Actionable Recommendations")
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    sorted_recs = sorted(recommendations, key=lambda x: priority_order.get(x.get('priority', 'low'), 3))

    for rec in sorted_recs:
        display_recommendation_card(rec)


def display_source_data_for_scope(source_data: Any):
    """Display source data for a specific scope."""
    if not source_data:
        return

    with st.expander("🗄️ View Raw Source Data"):
        if isinstance(source_data, list) and len(source_data) > 0:
            df_source = pd.DataFrame(source_data)
            st.dataframe(df_source, use_container_width=True, hide_index=True)
        elif isinstance(source_data, str):
            st.code(source_data)
        else:
            st.write(source_data)


def display_observations(results: List[Dict[str, Any]]):
    """Display key observations from all analyses."""
    st.header("🔍 Key Observations")

    all_observations = []
    for result in results:
        if 'key_observations' in result:
            scope = result.get('metadata', {}).get('analysis_scope', 'Unknown')
            for obs in result['key_observations']:
                obs['scope'] = scope
                all_observations.append(obs)

    # Group by severity
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    all_observations.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))

    for obs in all_observations:
        severity = obs.get('severity', 'low')
        severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}

        st.markdown(f"""
        <div class="observation-card">
            <h4>{severity_emoji.get(severity, '⚪')} {obs.get('observation', 'N/A')}</h4>
            <p><strong>Evidence:</strong> {obs.get('evidence', 'N/A')}</p>
            <p><strong>Scope:</strong> {obs.get('scope', 'N/A')} | <strong>Severity:</strong> {severity}</p>
        </div>
        """, unsafe_allow_html=True)


def display_insights(results: List[Dict[str, Any]]):
    """Display interpretations and insights with area-specific metadata."""
    st.header("💡 Insights & Interpretations")

    for idx, result in enumerate(results):
        metadata = result.get('metadata', {})
        scope = metadata.get('analysis_scope', 'Unknown').replace('_', ' ').title()
        confidence = metadata.get('confidence_level', 'Unknown')
        assumptions = metadata.get('assumptions_applied', [])

        if 'interpretation' in result and result['interpretation']:
            with st.expander(f"📊 {scope} Analysis Logic & Insights", expanded=idx == 0):
                # Area Metadata section
                st.markdown("#### ⚙️ Analysis Parameters")
                col1, col2 = st.columns([1, 2])
                with col1:
                    confidence_color = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}.get(confidence, '⚪')
                    st.markdown(f"**Confidence:** {confidence_color} {confidence.title()}")
                with col2:
                    if assumptions:
                        st.markdown("**Assumptions Applied:**")
                        for a in assumptions:
                            st.markdown(f"- {a}")

                st.markdown("---")

                # Insights
                for interp in result['interpretation']:
                    st.markdown(f"""
                    <div class="insight-card">
                        <h4>💡 {interp.get('insight', 'N/A')}</h4>
                        <p><strong>Explanation:</strong> {interp.get('explanation', 'N/A')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    if interp.get('alternative_explanations'):
                        st.markdown("**Alternative Explanations:**")
                        for alt in interp['alternative_explanations']:
                            st.markdown(f"- {alt}")


def display_recommendations(results: List[Dict[str, Any]]):
    """Display actionable recommendations."""
    st.header("🎯 Actionable Recommendations")

    all_recommendations = []
    for result in results:
        if 'actionable_recommendations' in result:
            all_recommendations.extend(result['actionable_recommendations'])

    # Group by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    all_recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))

    # Create tabs for different priorities
    high_recs = [r for r in all_recommendations if r.get('priority') == 'high']
    medium_recs = [r for r in all_recommendations if r.get('priority') == 'medium']
    low_recs = [r for r in all_recommendations if r.get('priority') == 'low']

    tab1, tab2, tab3 = st.tabs([
        f"🔴 High Priority ({len(high_recs)})",
        f"🟡 Medium Priority ({len(medium_recs)})",
        f"🟢 Low Priority ({len(low_recs)})"
    ])

    with tab1:
        for rec in high_recs:
            display_recommendation_card(rec)

    with tab2:
        for rec in medium_recs:
            display_recommendation_card(rec)

    with tab3:
        for rec in low_recs:
            display_recommendation_card(rec)


def display_recommendation_card(rec: Dict[str, Any]):
    target_emoji = {
        'slide': '📄',
        'slide_type': '📋',
        'session_flow': '🔄',
        'facilitation': '🎤',
        'analytics': '📊'
    }
    st.markdown(f"{target_emoji.get(rec.get('target', 'slide'), '📌')} - {rec.get('recommendation', 'N/A')}")
    col1, col2 = st.columns([1, 5])
    with col1:
        st.badge("Impact")
    with col2:
        st.caption(f"{rec.get('expected_impact', 'N/A').replace('_', ' ').title()}")
    # """Display a single recommendation card."""
    # target_emoji = {
    #     'slide': '📄',
    #     'slide_type': '📋',
    #     'session_flow': '🔄',
    #     'facilitation': '🎤',
    #     'analytics': '📊'
    # }

    # st.markdown(f"""
    # <div class="recommendation-card">
    #     <h4>{target_emoji.get(rec.get('target', 'slide'), '📌')} {rec.get('recommendation', 'N/A')}</h4>
    #     <p><strong>Target:</strong> {rec.get('target', 'N/A').replace('_', ' ').title()}</p>
    #     <p><strong>Expected Impact:</strong> {rec.get('expected_impact', 'N/A')}</p>
    # </div>
    # """, unsafe_allow_html=True)


def display_coaching_messages(results: List[Dict[str, Any]]):
    """Display coaching messages."""
    st.header("🌟 Coaching Messages")

    messages = [r.get('coaching_message') for r in results if r.get('coaching_message')]

    if messages:
        for idx, message in enumerate(messages, 1):
            st.markdown(f"""
            <div class="coaching-message">
                <h4>Message {idx}</h4>
                <p>{message}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No coaching messages available in this analysis.")


def display_metadata_summary(results: List[Dict[str, Any]]):
    """Display metadata summary in sidebar."""
    st.sidebar.header("📋 Analysis Metadata")

    total_analyses = len(results)
    st.sidebar.metric("Total Analysis Scopes", total_analyses)

    st.sidebar.markdown("**Included Scopes:**")
    for r in results:
        scope_id = r.get('metadata', {}).get('analysis_scope', 'Unknown')
        scope_name = get_human_friendly_scope_name(scope_id)
        st.sidebar.markdown(f"- {scope_name}")


def get_human_friendly_scope_name(scope_id: str) -> str:
    """Map raw scope IDs to human friendly names from specs."""
    mapping = {
        "participation": "Engagement & Flow",
        "accuracy": "Knowledge & Accuracy",
        "free_text": "Audience Answer",
        "participation, accuracy, semantic richness": "Slide Health & Quality",
        "session_flow": "Session Pacing",
        "participant_behavior": "Participant Insights"
    }
    # Handle multiple comma separated scopes if any
    if "," in scope_id and scope_id not in mapping:
        parts = [mapping.get(p.strip(), p.strip().title()) for p in scope_id.split(",")]
        return " & ".join(parts)

    return mapping.get(scope_id, scope_id.replace('_', ' ').title())


def run_graph_analysis(presentation_id: str, progress_callback=None) -> str:
    """
    Run the session insight graph analysis for a given presentation_id.

    Args:
        presentation_id: The presentation ID to analyze
        progress_callback: Optional Streamlit progress callback

    Returns:
        Path to the generated results JSON file

    Raises:
        Exception: If graph execution fails
    """
    if not GRAPH_AVAILABLE:
        raise Exception(f"Graph not available: {GRAPH_IMPORT_ERROR}")

    # Create the graph
    graph = create_session_insight_graph()

    # Prepare input state
    input_state = {
        "presentation_id": presentation_id,
        "insights": [],
        "coaching_message": None,
        "final_output_path": ""
    }

    # Track progress
    nodes_completed = 0
    total_nodes = 3  # load_datamart, analyze_and_refine (multiple), aggregate_insights

    final_state = None

    # Run the graph
    for output in graph.stream(input_state):
        for key, value in output.items():
            nodes_completed += 1
            if progress_callback:
                progress_callback({ "status": f"{key} is working..", "progress": nodes_completed })

            # Store the final state
            if key == "aggregate_insights":
                final_state = value

    if final_state and final_state.get("final_output_path"):
        return final_state["final_output_path"]
    else:
        raise Exception("Graph execution completed but no output file was generated")


def main():
    """Main dashboard application."""
    st.title("📊 Session Insight Dashboard")
    st.markdown("### Interactive Analysis Visualization")

    # Sidebar for configuration
    st.sidebar.title("⚙️ Configuration")

    # Check if graph is available
    if GRAPH_AVAILABLE:
        input_methods = ["Run Analysis (Presentation ID)", "Upload File", "Enter File Path"]
    else:
        input_methods = ["Upload File", "Enter File Path"]
        st.sidebar.warning("⚠️ Graph analysis not available. You can only load existing results.")

    # Input method selection
    upload_option = st.sidebar.radio(
        "Select input method:",
        input_methods
    )

    results = []
    results_file_path = None

    # Handle different input methods
    if upload_option == "Run Analysis (Presentation ID)":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🚀 Run New Analysis")

        presentation_id = st.sidebar.text_input(
            "Presentation ID:",
            placeholder="e.g., 7880449",
            help="Enter the presentation ID to analyze"
        )

        run_button = st.sidebar.button("▶️ Run Analysis", type="primary")

        if run_button:
            if not presentation_id:
                st.sidebar.error("Please enter a presentation ID")
            else:
                # Create a progress container
                progress_container = st.sidebar.container()
                with progress_container:
                    st.info(f"🔄 Running analysis for presentation {presentation_id}...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        # Define progress callback
                        def update_progress(update):
                            status_text.text(update['status'])
                            # total about 12 updates
                            progress_bar.progress(update['progress'] * 8)

                        # Run the analysis
                        with st.spinner("Analyzing presentation..."):
                            results_file_path = run_graph_analysis(
                                presentation_id,
                                progress_callback=update_progress
                            )
                            progress_bar.progress(100)
                            status_text.text('')

                        # Load the results
                        if results_file_path and Path(results_file_path).exists():
                            data = load_analysis_results(results_file_path)
                            results = data["insights"]
                            coaching_summary = data["coaching_summary"]

                            if results:
                                st.sidebar.success(f"✅ Analysis complete! Loaded {len(results)} analyses")
                                st.sidebar.info(f"📄 Results saved to: {results_file_path}")
                            else:
                                st.sidebar.error("Failed to load analysis results")
                        else:
                            st.sidebar.error("Analysis completed but results file not found")

                    except Exception as e:
                        st.sidebar.error(f"❌ Analysis failed: {str(e)}")
                        st.sidebar.exception(e)

        # Show instructions if not running
        if not run_button:
            st.sidebar.markdown("""
            **Instructions:**
            1. Enter a presentation ID
            2. Click "Run Analysis"
            3. Wait for the analysis to complete
            4. View the results in the dashboard

            **Note:** This will:
            - Fetch data from Redshift
            - Run multiple AI analyses
            - Generate insights and recommendations
            - Save results to a JSON file
            """)

    elif upload_option == "Upload File":
        uploaded_file = st.sidebar.file_uploader(
            "Upload analysis results JSON",
            type=['json'],
            help="Upload the JSON file containing session insight analysis results"
        )

        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                if isinstance(data, dict):
                    results = data.get("detailed_insights", [])
                    coaching_summary = data.get("coaching_summary", "")
                else:
                    results = data
                    coaching_summary = ""
                st.sidebar.success(f"✅ Loaded {len(results)} analyses")
            except Exception as e:
                st.sidebar.error(f"Error loading file: {e}")
    else:
        file_path = st.sidebar.text_input(
            "Enter file path:",
            placeholder="/path/to/session_insight_results.json",
            help="Enter the full path to the analysis results JSON file"
        )

        if file_path:
            if Path(file_path).exists():
                data = load_analysis_results(file_path)
                results = data["insights"]
                coaching_summary = data["coaching_summary"]
                if results:
                    st.sidebar.success(f"✅ Loaded {len(results)} analyses")
            else:
                st.sidebar.error("File not found!")

    if not results:
        st.info("👈 Please select an input method to begin.")
        st.markdown("""
        ### How to use this dashboard:

        **Option 1: Run New Analysis** (Recommended)
        1. Select "Run Analysis (Presentation ID)"
        2. Enter a presentation ID (e.g., 7880449)
        3. Click "Run Analysis" and wait for completion
        4. Explore the automatically generated visualizations

        **Option 2: Upload Existing Results**
        1. Select "Upload File"
        2. Upload a previously generated JSON results file
        3. View the analysis

        **Option 3: Load from Path**
        1. Select "Enter File Path"
        2. Enter the full path to a results JSON file
        3. View the analysis

        ### The dashboard provides:
        - **📈 Overview**: High-level session metrics and comparative charts.
        - **🎯 Scope Tabs**: Dedicated analysis for **Participation**, **Accuracy**, and **Diversity** (Free Text).
        - **🌟 Coaching Summary**: Aggregated feedback and motivational messages.

        Within each scope tab, you will find:
        - 🔍 **Key Observations**: Findings with evidence.
        - 💡 **Insights**: Detailed interpretations.
        - 🎯 **Recommendations**: Specific actions to take.
        - 🗄️ **Raw Source Data**: The data table used for that specific analysis.
        """)
        return

    # Display metadata in sidebar
    display_metadata_summary(results)

    # Extract slide data
    df = extract_slide_data(results)

    # Main content tabs - Reorganized by Scope with human friendly names
    scope_names = ["📈 Overview"]
    for r in results:
        scope_id = r.get('metadata', {}).get('analysis_scope', 'Unknown')
        # scope_name = get_human_friendly_scope_name(scope_id)
        scope_name = scope_id
        scope_names.append(f"🎯 {scope_name}")
    scope_names.append("🌟 Final Coaching")

    tabs = st.tabs(scope_names)

    # 1. Overview Tab
    with tabs[0]:
        # Global Coaching Summary
        if 'coaching_summary' in locals() and coaching_summary:
            st.subheader('🌟 Expert Coaching Summary')
            st.markdown(coaching_summary)

        st.subheader('🔍 Key metrics')
        # Key metrics
        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                total_slides = len(df)
                st.metric("Total Slides", total_slides)

            with col2:
                if 'participants' in df.columns:
                    avg_participation = df['participants'].mean()
                    st.metric("Avg Participation", f"{avg_participation:.1f}")

            with col3:
                if 'accuracy' in df.columns:
                    quiz_slides = df[df['accuracy'] > 0]
                    if not quiz_slides.empty:
                        avg_accuracy = quiz_slides['accuracy'].mean() * 100
                        st.metric("Avg Quiz Accuracy", f"{avg_accuracy:.1f}%")

            with col4:
                if 'slide_type' in df.columns:
                    unique_types = df['slide_type'].nunique()
                    st.metric("Slide Types", unique_types)

        # Charts
        col1, col2 = st.columns(2)

        with col1:
            participation_chart = create_participation_chart(df)
            if participation_chart:
                st.plotly_chart(participation_chart, use_container_width=True)

            diversity_chart = create_diversity_chart(df)
            if diversity_chart:
                st.plotly_chart(diversity_chart, use_container_width=True)

        with col2:
            slide_type_chart = create_slide_type_distribution(df)
            if slide_type_chart:
                st.plotly_chart(slide_type_chart, use_container_width=True)

            accuracy_chart = create_accuracy_chart(df)
            if accuracy_chart:
                st.plotly_chart(accuracy_chart, use_container_width=True)

        # Slide details table
        if not df.empty:
            st.subheader("📋 Complete Slide Details")
            display_df = df.copy()

            # Format accuracy as percentage
            if 'accuracy' in display_df.columns:
                display_df['accuracy'] = display_df['accuracy'].apply(
                    lambda x: f"{x*100:.1f}%" if x > 0 else "N/A"
                )

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )

    # 2. Scope-specific Tabs
    for i, result in enumerate(results):
        with tabs[i+1]:
            scope_id = result.get('metadata', {}).get('analysis_scope', 'Unknown')
            scope_name = get_human_friendly_scope_name(scope_id)

            # Metadata & Coaching Message
            display_scope_metrics(result)

            # Components
            display_observations_for_scope(result.get('key_observations', []))
            display_insights_for_scope(result.get('interpretation', []))
            display_recommendations_for_scope(result.get('actionable_recommendations', []))
            display_source_data_for_scope(result.get('source_data'))

    # 3. Coaching Summary Tab
    with tabs[-1]:
        st.header("🌟 Session Wrap-up")
        display_coaching_messages(results)

    # Footer
    st.markdown("---")
    st.markdown(
        f"*Dashboard generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    )


if __name__ == "__main__":
    main()
