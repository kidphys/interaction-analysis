"""
Redshift engine compatible with streamlit cache
"""

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

@st.cache_resource(ttl='60m')
def create_engine():
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


@st.cache_data(ttl='60m')
def execute(sql):
    engine = create_engine()
    with engine.connect() as conn:
        res = conn.execute(text(sql))
        rows = res.fetchall()
    return rows