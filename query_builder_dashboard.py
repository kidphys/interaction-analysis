import streamlit as st
import pandas as pd
from typing import Optional
from structured_agent import get_all_answers
from query_builder_components import (
    QueryBuilderComponents,
    QueryExecutor,
    QueryConfig,
    FilterCondition,
    FilterOperator,
    SortCondition,
    AggregationConfig,
    render_query_summary
)

def load_answers_data(user_id: str) -> pd.DataFrame:
    """Load answers data for the user"""
    try:
        with st.spinner("Loading data..."):
            answers_data = get_all_answers(user_id)
            df = pd.DataFrame(answers_data['rows'])
            df.columns = answers_data['cols']
            return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def display_data_overview(df: pd.DataFrame) -> None:
    """Display overview of the loaded data"""
    st.subheader("📊 Data Overview")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Rows", len(df))
    with col2:
        st.metric("Total Columns", len(df.columns))
    with col3:
        if 'presentation_id' in df.columns:
            unique_presentations = df['presentation_id'].nunique()
            st.metric("Unique Presentations", unique_presentations)

    if not df.empty:
        with st.expander("Column Information", expanded=False):
            col_info = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                null_count = df[col].isnull().sum()
                unique_count = df[col].nunique()
                col_info.append({
                    "Column": col,
                    "Data Type": dtype,
                    "Null Values": null_count,
                    "Unique Values": unique_count
                })

            info_df = pd.DataFrame(col_info)
            st.dataframe(info_df, use_container_width=True)

def render_sample_data(df: pd.DataFrame) -> None:
    """Render sample data preview"""
    st.subheader("🔍 Sample Data Preview")
    if not df.empty:
        sample_size = min(5, len(df))
        st.dataframe(df.head(sample_size), use_container_width=True)
    else:
        st.info("No data available")

def export_results(df: pd.DataFrame) -> None:
    """Provide export options for query results"""
    if df.empty:
        return

    st.subheader("💾 Export Results")

    col1, col2 = st.columns(2)

    with col1:
        # CSV download
        csv = df.to_csv(index=False)
        st.download_button(
            label="📁 Download as CSV",
            data=csv,
            file_name=f"query_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    with col2:
        # JSON download
        json_str = df.to_json(orient='records', indent=2)
        st.download_button(
            label="📋 Download as JSON",
            data=json_str,
            file_name=f"query_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

def create_query_builder_dashboard(username: str, user_id: str):
    """Main query builder dashboard"""

    # Page configuration
    st.set_page_config(
        page_title="Query Builder",
        page_icon="🔍",
        layout="wide"
    )

    # Header
    st.title("🔍 Build your own query")
    st.markdown(f"**Welcome, {username.capitalize()}!** Build custom queries on your presentation data.")

    # Load data
    if 'answers_df' not in st.session_state or st.session_state.get('current_user_id') != user_id:
        st.session_state.answers_df = load_answers_data(user_id)
        st.session_state.current_user_id = user_id

    df = st.session_state.answers_df

    if df.empty:
        st.error("Unable to load data. Please try again later.")
        return

    # Data overview
    # display_data_overview(df)


    # Initialize query builder components
    query_builder = QueryBuilderComponents(df)

    # Initialize session state for query results
    if 'query_executed' not in st.session_state:
        st.session_state.query_executed = False

    # Two-column layout: Settings on left, Results on right
    settings_col, results_col = st.columns([1, 1])

    with settings_col:

        # Compact column selection
        selected_columns = st.multiselect(
            "📋 **Select Columns**",
            options=query_builder.columns,
            default=query_builder.columns,
            key="main_columns"
        )

        # Compact filter section
        filter_count = st.number_input("🔍 **Number of Filters**", 0, 5, 0, key="main_filter_count")
        filters = []

        for i in range(filter_count):
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                filter_column = st.selectbox("Column", query_builder.columns, key=f"main_filter_col_{i}")
            with col2:
                operator = st.selectbox("Op", [FilterOperator.EQUALS, FilterOperator.CONTAINS, FilterOperator.GREATER_THAN],
                                      format_func=lambda x: x.value, key=f"main_filter_op_{i}")
            with col3:
                if operator not in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
                    filter_value = st.text_input("Value", key=f"main_filter_val_{i}")
                    if filter_value:
                        filters.append(FilterCondition(filter_column, operator, filter_value))

        # Group by section
        group_by_columns = st.multiselect("📊 **Group By**", selected_columns, key="main_group_by")

        # Aggregation selection (only show if group by is selected)
        aggregations = []
        if group_by_columns:
            st.write("**📈 Aggregations**")
            agg_columns = [col for col in selected_columns if col not in group_by_columns]

            for col in agg_columns:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"*{col}:*")
                with col2:
                    # Available aggregation functions
                    if col in query_builder.df.columns and pd.api.types.is_numeric_dtype(query_builder.df[col]):
                        available_funcs = ['count', 'sum', 'mean', 'min', 'max', 'std']
                        default_funcs = ['count', 'mean']
                    else:
                        available_funcs = ['count', 'nunique']
                        default_funcs = ['count']

                    selected_funcs = st.multiselect(
                        f"Functions for {col}",
                        available_funcs,
                        default=default_funcs,
                        key=f"main_agg_{col}",
                        label_visibility="collapsed"
                    )

                    if selected_funcs:
                        aggregations.append(AggregationConfig(col, selected_funcs))

        # Sort section
        if selected_columns:
            # Build potential sort columns including aggregated ones
            sort_options = selected_columns.copy()
            if aggregations:
                for agg in aggregations:
                    for func in agg.functions:
                        sort_options.append(f"{agg.column}_{func}")

            col1, col2 = st.columns(2)
            with col1:
                sort_column = st.selectbox("🔀 **Sort By**", [""] + sort_options, key="main_sort_col")
            with col2:
                sort_direction = st.selectbox("Direction", ["ASC", "DESC"], key="main_sort_dir")

            sort_conditions = [SortCondition(sort_column, sort_direction)] if sort_column else []
        else:
            sort_conditions = []

        # Compact settings row
        col1, col2, col3 = st.columns(3)
        with col1:
            limit = st.number_input("📏 **Limit**", 1, 1000, 100, key="main_limit")
        with col2:
            show_raw_data = st.checkbox("Raw data", key="main_raw_data")
        with col3:
            if st.button("🔄", help="Reset"):
                for key in list(st.session_state.keys()):
                    if key.startswith('main_'):
                        del st.session_state[key]
                st.rerun()

        # Build and execute
        query_config = QueryConfig(selected_columns, filters, group_by_columns, aggregations, sort_conditions, limit)

        if st.button("🚀 **Execute Query**", type="primary", use_container_width=True):
            with st.spinner("Running..."):
                try:
                    result_df = QueryExecutor.execute_query(df, query_config)
                    st.session_state.query_result = result_df
                    st.session_state.query_executed = True
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.session_state.query_executed = False

    with results_col:
        st.header("📊 Results")

        if st.session_state.get('query_executed', False) and 'query_result' in st.session_state:
            result_df = st.session_state.query_result

            if result_df.empty:
                st.warning("No results found.")
            else:
                # Quick stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Rows", len(result_df))
                with col2:
                    st.metric("Cols", len(result_df.columns))
                with col3:
                    # Quick export
                    csv = result_df.to_csv(index=False)
                    st.download_button("📁 CSV", csv, f"results_{pd.Timestamp.now().strftime('%H%M%S')}.csv", "text/csv")

                # Results table
                st.dataframe(result_df, use_container_width=True, height=500)

        else:
            st.info("👆 Build your query and execute to see results.")

        # Raw data preview
        if show_raw_data:
            st.caption("Raw Data Sample")
            st.dataframe(df.head(3), use_container_width=True)


if __name__ == "__main__":
    st.logo('https://ahaslides.com/wp-content/uploads/2025/05/logo-full.png')

    # Get user from query parameters
    query_params = st.query_params
    user = query_params.get("user", "duke")  # Default to "duke"

    # User mapping (same as in react_agent_dashboard.py)
    user_map = {
        'tara': 3146502,
        'april': 2992027,
        'kiotViet': 259137,
        'cheryl': 1918789,
        'duke': 1472007,
    }

    if user in user_map:
        create_query_builder_dashboard(user, str(user_map[user]))
    else:
        st.error(f'User "{user}" is not supported. Available users: {", ".join(user_map.keys())}')
        st.info("Add ?user=duke to the URL to specify a user (e.g., ?user=tara)")