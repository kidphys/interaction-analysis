import streamlit as st
import pandas as pd
import altair as alt

from redshift_api import execute


QUERY = """
WITH duplicates AS (
    SELECT
        cookie,
        presentation_id,
        participant_id,
        createdat,
        ROW_NUMBER() OVER (
            PARTITION BY cookie, presentation_id
            ORDER BY createdat
        ) AS rn
    FROM aha_report_v5.dim_participants
    WHERE cookie IS NOT NULL AND cookie != ''
      AND deleted = false
)
SELECT
    DATE_TRUNC('day', createdat)::date AS period,
    COUNT(*) AS duplicate_count
FROM duplicates
WHERE rn > 1
GROUP BY 1
ORDER BY 1
"""


def fetch_duplicates():
    rows = execute(QUERY)
    return pd.DataFrame(rows, columns=['period', 'duplicate_count'])


def render():
    st.set_page_config(layout="wide", page_title="Cookie Duplication Dashboard")
    st.title("Same-Presentation Duplicate Participants by Cookie")
    st.caption(
        "Counts participants that share the same cookie within the same presentation. "
        "The 2nd, 3rd, ... participant records are counted as duplicates, bucketed by their createdAt."
    )

    with st.spinner("Querying Redshift..."):
        df = fetch_duplicates()

    if df.empty:
        st.info("No duplicates found.")
        return

    df['period'] = pd.to_datetime(df['period'])

    all_days = pd.DataFrame({
        'period': pd.date_range(df['period'].min(), df['period'].max(), freq='D')
    })
    df = all_days.merge(df, on='period', how='left').fillna({'duplicate_count': 0})
    df['duplicate_count'] = df['duplicate_count'].astype(int)
    df['period_label'] = df['period'].dt.strftime('%Y-%m-%d')

    st.metric("Total duplicates", int(df['duplicate_count'].sum()))

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X('period_label:N', title=None, sort=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('duplicate_count:Q', title='Duplicate count'),
            tooltip=[
                alt.Tooltip('period_label:N', title='Date'),
                alt.Tooltip('duplicate_count:Q', title='Duplicates'),
            ],
        )
        .properties(height=400)
        .configure_view(strokeWidth=0)
        .configure_axis(grid=True, gridColor='#eee')
    )
    st.altair_chart(chart, use_container_width=True)


if __name__ == '__main__':
    render()
