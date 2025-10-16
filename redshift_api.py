"""
Redshift engine compatible with streamlit cache
"""

from functools import lru_cache
from typing import Callable
import streamlit as st
from dotenv import load_dotenv
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.engine.url import URL

load_dotenv('.env.local')
import os

# Redshift connection parameters from environment
REDSHIFT_USER = os.getenv("REDSHIFT_USER")
REDSHIFT_PASSWORD = os.getenv("REDSHIFT_PASSWORD")
REDSHIFT_HOST = os.getenv("REDSHIFT_HOST")

def _create_engine():
    # build the sqlalchemy URL
    url = URL.create(
        drivername='redshift+redshift_connector', # indicate redshift_connector driver and dialect will be used
        # drivername="redshift+psycopg2",
        host=REDSHIFT_HOST, # Amazon Redshift host
        port=5439, # Amazon Redshift port
        database='report', # Amazon Redshift database
        username=REDSHIFT_USER, # Amazon Redshift username
        password=REDSHIFT_PASSWORD # Amazon Redshift password
    )
    engine = sa.create_engine(url,
        pool_pre_ping=True,      # ✅ Goes here
        pool_recycle=3600,       # Recycle connections after 1 hour
        pool_size=5,
        max_overflow=10)

    sql = """
    SELECT id FROM aha_report_x.mart_presentation_interactions LIMIT 1;
    """

    with engine.connect() as conn:
        conn.execute(text(sql))
    return engine

import arrow

def _execute(sql, create_engine: Callable):
    now = arrow.now()
    engine = create_engine()
    print(f'\nEngine time: {arrow.now() - now}')
    now = arrow.now()
    with engine.connect() as conn:
        print(f'\nConnection time: {arrow.now() - now}')
        now = arrow.now()
        print(f'\nSQL: {text(sql)}')
        res = conn.execute(text(sql))
        rows = res.fetchall()
        print(f'\nFetching time: {arrow.now() - now}')
    return rows


@st.cache_resource(ttl='60m')
def st_create_engine():
    return _create_engine()


def _pure_execute(sql, create_engine: Callable):
    now = arrow.now()
    engine = create_engine()
    print(f'\nEngine time: {arrow.now() - now}')
    now = arrow.now()
    with engine.connect() as conn:
        print(f'\nConnection time: {arrow.now() - now}')
        now = arrow.now()
        print(f'\nSQL: {text(sql)}')
        res = conn.execute(text(sql))
        print(f'\nResult: {res}, Fetching time: {arrow.now() - now}')
    return None


@st.cache_data(ttl='60m')
def pure_execute(sql):
    return _pure_execute(sql, st_create_engine)


@st.cache_data(ttl='60m')
def execute(sql):
    return _execute(sql, st_create_engine)


def _execute_with_columns(sql, create_engine: Callable):
    engine = create_engine()
    with engine.connect() as conn:
        res = conn.execute(text(sql))
        rows = res.fetchall()
        cols = res.keys()
    return rows, cols


@lru_cache(maxsize=1)
def execute_with_columns(sql):
    print(f'Execute_with_columns: {sql}')
    now = arrow.now()
    rows, cols = _execute_with_columns(sql, _create_engine)
    print(f'{len(rows)} rows in {arrow.now() - now}')
    return rows, cols


