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
    engine = sa.create_engine(url)

    sql = """
    SELECT id FROM aha_report_x.mart_presentation_interactions LIMIT 1;
    """

    with engine.connect() as conn:
        conn.execute(text(sql))
    return engine


def _execute(sql, create_engine: Callable):
    engine = create_engine()
    with engine.connect() as conn:
        res = conn.execute(text(sql))
        rows = res.fetchall()
    return rows


@st.cache_resource(ttl='60m')
def st_create_engine():
    return _create_engine()


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
    return _execute_with_columns(sql, _create_engine)


