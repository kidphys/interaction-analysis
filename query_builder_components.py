import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class FilterOperator(Enum):
    EQUALS = "="
    NOT_EQUALS = "!="
    CONTAINS = "LIKE"
    NOT_CONTAINS = "NOT LIKE"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    IN = "IN"
    NOT_IN = "NOT IN"

@dataclass
class FilterCondition:
    column: str
    operator: FilterOperator
    value: Any = None

@dataclass
class SortCondition:
    column: str
    direction: str = "ASC"  # ASC or DESC

@dataclass
class AggregationConfig:
    column: str
    functions: List[str]  # e.g., ['count', 'sum', 'mean']

@dataclass
class QueryConfig:
    selected_columns: List[str]
    filters: List[FilterCondition]
    group_by_columns: List[str]
    aggregations: List[AggregationConfig]
    sort_conditions: List[SortCondition]
    limit: int = 100

class QueryBuilderComponents:
    """Modular components for building database queries"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        # Filter out columns ending with "_id"
        self.columns = [col for col in df.columns if not col.endswith('_id')]

    def render_column_selector(self, key_prefix: str = "") -> List[str]:
        """Render column selection multiselect"""
        st.subheader("📋 Select Columns")
        selected_cols = st.multiselect(
            "Choose columns to display:",
            options=self.columns,
            default=self.columns,  # Default to first 5 columns
            key=f"{key_prefix}_columns"
        )

        if not selected_cols:
            st.warning("Please select at least one column")
            return self.columns[:1]  # Return first column as fallback

        return selected_cols

    def render_filter_builder(self, key_prefix: str = "") -> List[FilterCondition]:
        """Render filter condition builder"""
        st.subheader("🔍 Filter Conditions")

        filters = []

        # Simple approach: just use the number input directly without complex state management
        filter_count = st.number_input(
            "Number of filters:",
            min_value=0,
            max_value=10,
            value=0,
            key=f"{key_prefix}_filter_count",
            help="Change this number to add or remove filters"
        )

        for i in range(filter_count):
            with st.expander(f"Filter {i+1}", expanded=True):
                col1, col2, col3 = st.columns([2, 1, 2])

                with col1:
                    filter_column = st.selectbox(
                        "Column:",
                        options=self.columns,
                        key=f"{key_prefix}_filter_col_{i}"
                    )

                with col2:
                    # Get column data type to suggest appropriate operators
                    col_dtype = self.df[filter_column].dtype

                    if pd.api.types.is_numeric_dtype(col_dtype):
                        default_operators = [
                            FilterOperator.EQUALS, FilterOperator.NOT_EQUALS,
                            FilterOperator.GREATER_THAN, FilterOperator.LESS_THAN,
                            FilterOperator.GREATER_EQUAL, FilterOperator.LESS_EQUAL,
                            FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL
                        ]
                    else:
                        default_operators = [
                            FilterOperator.EQUALS, FilterOperator.NOT_EQUALS,
                            FilterOperator.CONTAINS, FilterOperator.NOT_CONTAINS,
                            FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL,
                            FilterOperator.IN, FilterOperator.NOT_IN
                        ]

                    operator = st.selectbox(
                        "Operator:",
                        options=default_operators,
                        format_func=lambda x: x.value,
                        key=f"{key_prefix}_filter_op_{i}"
                    )

                with col3:
                    filter_value = None

                    if operator not in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
                        if operator in [FilterOperator.IN, FilterOperator.NOT_IN]:
                            # For IN operators, show multiselect with unique values
                            unique_values = self.df[filter_column].dropna().unique()
                            if len(unique_values) <= 100:  # Only show if reasonable number of options
                                filter_value = st.multiselect(
                                    "Values:",
                                    options=unique_values,
                                    key=f"{key_prefix}_filter_val_{i}"
                                )
                            else:
                                filter_value = st.text_input(
                                    "Values (comma-separated):",
                                    key=f"{key_prefix}_filter_val_{i}"
                                )
                        elif operator in [FilterOperator.CONTAINS, FilterOperator.NOT_CONTAINS]:
                            filter_value = st.text_input(
                                "Search text:",
                                key=f"{key_prefix}_filter_val_{i}"
                            )
                        elif pd.api.types.is_numeric_dtype(self.df[filter_column].dtype):
                            filter_value = st.number_input(
                                "Value:",
                                key=f"{key_prefix}_filter_val_{i}"
                            )
                        elif pd.api.types.is_datetime64_any_dtype(self.df[filter_column].dtype):
                            filter_value = st.date_input(
                                "Date:",
                                key=f"{key_prefix}_filter_val_{i}"
                            )
                        else:
                            # For categorical/string columns, show selectbox with unique values if reasonable
                            unique_values = self.df[filter_column].dropna().unique()
                            if len(unique_values) <= 50:
                                filter_value = st.selectbox(
                                    "Value:",
                                    options=[""] + list(unique_values),
                                    key=f"{key_prefix}_filter_val_{i}"
                                )
                            else:
                                filter_value = st.text_input(
                                    "Value:",
                                    key=f"{key_prefix}_filter_val_{i}"
                                )

                if operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL] or filter_value:
                    filters.append(FilterCondition(
                        column=filter_column,
                        operator=operator,
                        value=filter_value
                    ))

        return filters

    def render_group_by_builder(self, selected_columns: List[str], key_prefix: str = "") -> List[str]:
        """Render group by column selector"""
        st.subheader("📊 Group By")

        group_by_cols = st.multiselect(
            "Group by columns:",
            options=selected_columns,
            key=f"{key_prefix}_group_by"
        )

        if group_by_cols:
            st.info(f"Grouping by: {', '.join(group_by_cols)}")

        return group_by_cols

    def render_sort_builder(self, selected_columns: List[str], group_by_columns: List[str] = None, key_prefix: str = "") -> List[SortCondition]:
        """Render sort condition builder"""
        st.subheader("🔀 Sort Conditions")

        sort_conditions = []

        # Build available sort columns including potential aggregated columns
        available_columns = selected_columns.copy()

        # If group by is used, add potential aggregated column names
        if group_by_columns:
            agg_columns = [col for col in selected_columns if col not in group_by_columns]
            agg_column_names = []

            for col in agg_columns:
                if col in self.df.columns and pd.api.types.is_numeric_dtype(self.df[col]):
                    # Add common aggregation column names
                    new_agg_cols = [f"{col}_count", f"{col}_sum", f"{col}_mean", f"{col}_min", f"{col}_max"]
                    available_columns.extend(new_agg_cols)
                    agg_column_names.extend(new_agg_cols)
                else:
                    # Add count and nunique for non-numeric columns
                    new_agg_cols = [f"{col}_count", f"{col}_nunique"]
                    available_columns.extend(new_agg_cols)
                    agg_column_names.extend(new_agg_cols)

            if agg_column_names:
                st.info(f"💡 **Group By detected!** You can now sort by aggregated columns: {', '.join(agg_column_names[:5])}{'...' if len(agg_column_names) > 5 else ''}")

        # Remove duplicates while preserving order
        seen = set()
        unique_columns = []
        for col in available_columns:
            if col not in seen:
                unique_columns.append(col)
                seen.add(col)

        sort_count = st.number_input(
            "Number of sort columns:",
            min_value=0,
            max_value=5,
            value=1,
            key=f"{key_prefix}_sort_count"
        )

        for i in range(sort_count):
            col1, col2 = st.columns([3, 1])

            with col1:
                sort_column = st.selectbox(
                    f"Sort column {i+1}:",
                    options=unique_columns,
                    key=f"{key_prefix}_sort_col_{i}"
                )

            with col2:
                sort_direction = st.selectbox(
                    "Direction:",
                    options=["ASC", "DESC"],
                    key=f"{key_prefix}_sort_dir_{i}"
                )

            sort_conditions.append(SortCondition(
                column=sort_column,
                direction=sort_direction
            ))

        return sort_conditions

    def render_limit_selector(self, key_prefix: str = "") -> int:
        """Render result limit selector"""
        st.subheader("📏 Result Limit")
        limit = st.number_input(
            "Maximum number of rows:",
            min_value=1,
            max_value=10000,
            value=100,
            step=50,
            key=f"{key_prefix}_limit"
        )
        return limit

class QueryExecutor:
    """Execute queries on pandas DataFrame"""

    @staticmethod
    def apply_filters(df: pd.DataFrame, filters: List[FilterCondition]) -> pd.DataFrame:
        """Apply filter conditions to DataFrame"""
        result_df = df.copy()

        for filter_cond in filters:
            column = filter_cond.column
            operator = filter_cond.operator
            value = filter_cond.value

            if operator == FilterOperator.EQUALS:
                result_df = result_df[result_df[column] == value]
            elif operator == FilterOperator.NOT_EQUALS:
                result_df = result_df[result_df[column] != value]
            elif operator == FilterOperator.CONTAINS:
                result_df = result_df[result_df[column].astype(str).str.contains(str(value), na=False)]
            elif operator == FilterOperator.NOT_CONTAINS:
                result_df = result_df[~result_df[column].astype(str).str.contains(str(value), na=False)]
            elif operator == FilterOperator.GREATER_THAN:
                result_df = result_df[result_df[column] > value]
            elif operator == FilterOperator.LESS_THAN:
                result_df = result_df[result_df[column] < value]
            elif operator == FilterOperator.GREATER_EQUAL:
                result_df = result_df[result_df[column] >= value]
            elif operator == FilterOperator.LESS_EQUAL:
                result_df = result_df[result_df[column] <= value]
            elif operator == FilterOperator.IS_NULL:
                result_df = result_df[result_df[column].isna()]
            elif operator == FilterOperator.IS_NOT_NULL:
                result_df = result_df[result_df[column].notna()]
            elif operator == FilterOperator.IN:
                if isinstance(value, list):
                    result_df = result_df[result_df[column].isin(value)]
                elif isinstance(value, str):
                    # Parse comma-separated values
                    values = [v.strip() for v in value.split(',')]
                    result_df = result_df[result_df[column].isin(values)]
            elif operator == FilterOperator.NOT_IN:
                if isinstance(value, list):
                    result_df = result_df[~result_df[column].isin(value)]
                elif isinstance(value, str):
                    # Parse comma-separated values
                    values = [v.strip() for v in value.split(',')]
                    result_df = result_df[~result_df[column].isin(values)]

        return result_df

    @staticmethod
    def apply_groupby(df: pd.DataFrame, group_by_cols: List[str], aggregations: List, selected_columns: List[str]) -> pd.DataFrame:
        """Apply group by aggregation with custom aggregation functions"""
        if not group_by_cols:
            return df[selected_columns]

        if not aggregations:
            # If all selected columns are group by columns, just return unique combinations
            return df[group_by_cols].drop_duplicates().reset_index(drop=True)

        # Build aggregation dictionary from user selections
        agg_dict = {}
        for agg_config in aggregations:
            if agg_config.column in df.columns:
                agg_dict[agg_config.column] = agg_config.functions

        if not agg_dict:
            return df[group_by_cols].drop_duplicates().reset_index(drop=True)

        # Perform aggregation
        grouped = df.groupby(group_by_cols).agg(agg_dict).reset_index()

        # Flatten column names
        if isinstance(grouped.columns, pd.MultiIndex):
            grouped.columns = [
                col[0] if col[1] == '' else f"{col[0]}_{col[1]}"
                for col in grouped.columns
            ]

        return grouped

    @staticmethod
    def apply_sorting(df: pd.DataFrame, sort_conditions: List[SortCondition]) -> pd.DataFrame:
        """Apply sorting to DataFrame"""
        if not sort_conditions:
            return df

        sort_columns = []
        sort_ascending = []

        for sort_cond in sort_conditions:
            if sort_cond.column in df.columns:
                sort_columns.append(sort_cond.column)
                sort_ascending.append(sort_cond.direction == "ASC")

        if sort_columns:
            return df.sort_values(by=sort_columns, ascending=sort_ascending)

        return df

    @staticmethod
    def execute_query(df: pd.DataFrame, config: QueryConfig) -> pd.DataFrame:
        """Execute complete query configuration on DataFrame"""
        # Apply filters
        filtered_df = QueryExecutor.apply_filters(df, config.filters)

        # Apply group by (this also selects columns)
        grouped_df = QueryExecutor.apply_groupby(
            filtered_df,
            config.group_by_columns,
            config.aggregations,
            config.selected_columns
        )

        # Apply sorting
        sorted_df = QueryExecutor.apply_sorting(grouped_df, config.sort_conditions)

        # Apply limit
        limited_df = sorted_df.head(config.limit)

        return limited_df

def render_query_summary(config: QueryConfig) -> None:
    """Render a summary of the current query configuration"""
    st.subheader("📝 Query Summary")

    with st.expander("Query Configuration", expanded=False):
        st.write("**Selected Columns:**")
        st.write(config.selected_columns)

        if config.filters:
            st.write("**Filters:**")
            for i, filter_cond in enumerate(config.filters):
                st.write(f"  {i+1}. {filter_cond.column} {filter_cond.operator.value} {filter_cond.value}")

        if config.group_by_columns:
            st.write("**Group By:**")
            st.write(config.group_by_columns)

        if config.sort_conditions:
            st.write("**Sort By:**")
            for sort_cond in config.sort_conditions:
                st.write(f"  {sort_cond.column} {sort_cond.direction}")

        st.write(f"**Limit:** {config.limit} rows")