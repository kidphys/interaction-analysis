import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# Generate some example data
np.random.seed(0)

data = pd.DataFrame({
    'Date': pd.date_range('2023-01-01', periods=100),
    'Category A': np.random.randn(100).cumsum(),
    'Category B': np.random.randn(100).cumsum(),
    'Category C': np.random.randn(100).cumsum()
})

# Add a filter for categories using an auto-suggest box
categories = list(data.columns[1:])  # Excluding 'Date'
selected_categories = st.multiselect(
    'Select categories to display',
    categories,
    default=categories
)

# Filter the data based on selected categories
filtered_data = data[['Date'] + selected_categories]

# Create a line chart with filtered data
chart = alt.Chart(filtered_data).transform_fold(
    selected_categories,
    as_=['Category', 'Value']
).mark_line().encode(
    x='Date:T',
    y='Value:Q',
    color='Category:N'
)

# Display the chart
st.altair_chart(chart, use_container_width=True)