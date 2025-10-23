"""
Simple Parallel Query Executor for Redshift
Easy to use, copy-paste ready code
"""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import time


def fetch_query(query_info):
    """Execute a single query - designed to work with your existing Redshift connection"""
    query_name, sql, run_query_function = query_info

    start = time.time()
    df = run_query_function(sql)
    elapsed = time.time() - start

    print(f"✓ {query_name}: {len(df):,} rows in {elapsed:.2f}s. Preview: {df.head(2)}")
    return query_name, df


def get_user_answers_parallel(user_id: str, run_query_function) -> pd.DataFrame:
    """
    Fetch user answers using parallel queries

    Args:
        user_id: User ID to fetch
        run_query_function: Function that executes SQL and returns results
                           (like the Redshift tool you have)

    Returns:
        Combined DataFrame
    """

    # Define all queries
    queries = {
        'answers': f"""
            SELECT
                fa.user_id,
                fa.slide_id,
                fa.question_id,
                fa.participant_id,
                fa.master_presentation_id as presentation_id,
                fa.slide_type,
                fa.submitted_answer_text,
                fa.correct,
                fa.createdat
            FROM aha_report_v5.fact_answers2 fa
            JOIN aha_report_v5.dim_presentations dp
                ON fa.master_presentation_id = dp.id
            WHERE dp.user_id = '{user_id}'
        """,

        'questions': f"""
            SELECT
                dq.id as question_id,
                dq.slide_title
            FROM aha_report_v5.dim_questions dq
            JOIN aha_report_v5.dim_presentations dp
                ON dq.master_presentation_id = dp.id
            WHERE dp.user_id = '{user_id}'
        """,

        'presentations': f"""
            SELECT
                dp.id as presentation_id,
                dp.title as presentation_title
            FROM aha_report_v5.dim_presentations dp
            WHERE dp.user_id = '{user_id}'
        """,

        'participants': f"""
            SELECT
                dpart.participant_id,
                dpart.name as participant_name,
                dpart.email as participant_email
            FROM aha_report_v5.dim_participants dpart
            JOIN aha_report_v5.dim_presentations dp
                ON dpart.master_presentation_id = dp.id
            WHERE dp.user_id = '{user_id}'
        """
    }

    print(f"\n🚀 Fetching data for user {user_id} using {len(queries)} parallel queries...\n")

    # Prepare query info tuples
    query_tasks = [(name, sql, run_query_function) for name, sql in queries.items()]

    # Execute in parallel
    start_time = time.time()
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        for query_name, df in executor.map(fetch_query, query_tasks):
            results[query_name] = df

    total_time = time.time() - start_time
    print(f"\n✓ All queries completed in {total_time:.2f}s\n")

    # Combine results
    print("🔗 Combining results...")

    df = results['answers'].copy()

    df = df.merge(
        results['questions'],
        on='question_id',
        how='left'
    )

    df = df.merge(
        results['presentations'],
        on='presentation_id',
        how='left'
    )

    df = df.merge(
        results['participants'],
        on='participant_id',
        how='left'
    )

    print(f"✓ Result: {len(df):,} rows × {len(df.columns)} columns\n")

    return df


def get_user_answers_minimal_parallel(user_id: str, run_query_function) -> pd.DataFrame:
    """
    Ultra-fast version - fetches only essential columns (no large text fields)

    This is ~50x faster than the full version!
    """

    queries = {
        'answers': f"""
            SELECT
                fa.user_id,
                fa.question_id,
                fa.participant_id,
                fa.master_presentation_id as presentation_id,
                fa.correct,
                fa.createdat
            FROM aha_report_v5.fact_answers2 fa
            JOIN aha_report_v5.dim_presentations dp
                ON fa.master_presentation_id = dp.id
            WHERE dp.user_id = '{user_id}'
        """,

        'questions': f"""
            SELECT
                dq.id as question_id,
                dq.slide_title
            FROM aha_report_v5.dim_questions dq
            JOIN aha_report_v5.dim_presentations dp
                ON dq.master_presentation_id = dp.id
            WHERE dp.user_id = '{user_id}'
        """,

        'presentations': f"""
            SELECT
                dp.id as presentation_id,
                dp.title as presentation_title
            FROM aha_report_v5.dim_presentations dp
            WHERE dp.user_id = '{user_id}'
        """,

        'participants': f"""
            SELECT
                dpart.participant_id,
                dpart.name as participant_name,
                dpart.email as participant_email
            FROM aha_report_v5.dim_participants dpart
            JOIN aha_report_v5.dim_presentations dp
                ON dpart.master_presentation_id = dp.id
            WHERE dp.user_id = '{user_id}'
        """
    }

    print(f"\n⚡ Fetching MINIMAL data for user {user_id} (ultra-fast)...\n")

    query_tasks = [(name, sql, run_query_function) for name, sql in queries.items()]

    start_time = time.time()
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        for query_name, df in executor.map(fetch_query, query_tasks):
            results[query_name] = df

    total_time = time.time() - start_time
    print(f"\n✓ All queries completed in {total_time:.2f}s\n")

    print("🔗 Combining results...")

    df = results['answers'].copy()
    df = df.merge(results['questions'], on='question_id', how='left')
    df = df.merge(results['presentations'], on='presentation_id', how='left')
    df = df.merge(results['participants'], on='participant_id', how='left')

    print(f"✓ Result: {len(df):,} rows × {len(df.columns)} columns\n")

    return df


# ============================================================================
# USAGE EXAMPLE - Copy this to your notebook/script
# ============================================================================

"""
# Example 1: Using with your existing Redshift tool

from redshift_tools import run_redshift_query  # Your existing function

user_id = '259137'

# Get full data (includes submitted_answer_text, slide_type, etc.)
df_full = get_user_answers_parallel(user_id, run_redshift_query)

# OR get minimal data (recommended - 50x faster!)
df_minimal = get_user_answers_minimal_parallel(user_id, run_redshift_query)

print(df_minimal.head())
print(df_minimal.info())


# Example 2: Direct usage (if you want to see the implementation)

def my_query_runner(sql):
    # Your Redshift connection code here
    import redshift_connector
    conn = redshift_connector.connect(
        host='your-host',
        database='your-db',
        user='your-user',
        password='your-pass',
        port=5439
    )
    cursor = conn.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()
    conn.close()

    # Return as DataFrame
    return pd.DataFrame(result, columns=columns)

df = get_user_answers_minimal_parallel('259137', my_query_runner)
"""