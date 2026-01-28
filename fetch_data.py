from datetime import timedelta

import streamlit as st
import pandas as pd
import pydash as _
import os

CACHE_TTL = timedelta(days=1)

# from utils import redshift_execute
from redshift_api import execute

USE_FILE_CACHE = False

def fetch(query, filename, columns=None):
    full_filename = f'data_dump/{filename}.parquet'
    if USE_FILE_CACHE and os.path.exists(full_filename):
        return pd.read_parquet(full_filename, columns=columns)
    # rows = redshift_execute(query)
    rows = execute(query)
    df = pd.DataFrame(data=rows) if columns is None else pd.DataFrame(columns=columns, data=rows)
    if USE_FILE_CACHE:
        df.to_parquet(full_filename)
    return df


@st.cache_data(ttl=CACHE_TTL)
def fetch_sessions_by_users(user_ids, filename='sessions_by_users', prefix=''):
    query = f'''
    select hosted_by_id, id, hosted_date from aha_report_v5.dim_sessions
    where hosted_by_id in ({_.join(user_ids, ',')}) and hosted_date is not null
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_presentations_by_users(user_ids, filename='presentations_by_users', prefix=''):
    query = f'''
    select user_id, id, createdat_date from aha_report_v5.dim_presentations
    where user_id in ({_.join(user_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_users(user_ids, filename='users', prefix=''):
    query = f'''
    select id, email, first_name, last_name from aha_report_v5.dim_users
    where id in ({_.join(user_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_participants_by_users(user_ids, filename='participants', prefix=''):
    query = f'''
    select participant_id, createdat_date, user_id, presentation_id from aha_report_v5.dim_participants
    where user_id in ({_.join(user_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_answers_by_users(user_ids, filename='answers', prefix=''):
    query = f'''
    select createdat_date, user_id, presentation_id, participant_id from aha_report_v5.fact_answers2
    where user_id in ({_.join(user_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_participants_by_presentations(presentation_ids, filename='participants', prefix=''):
    query = f'''
    select participant_id, createdat_date, user_id, presentation_id from aha_report_v5.dim_participants
    where presentation_id in ({_.join(presentation_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_answers_by_presentations(presentation_ids, filename='answers', prefix=''):
    query = f'''
    select createdat_date, user_id, presentation_id, participant_id from aha_report_v5.fact_answers2
    where presentation_id in ({_.join(presentation_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_sessions_by_account(account_id, filename='sessions_by_account', prefix=''):
    query = f'''
    select hosted_by_id, id, hosted_date from aha_report_v5.dim_sessions
    where hosted_by_id in (select id from aha_report_v5.dim_users where account_id = {account_id})
    and hosted_date is not null
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_presentations_by_account(account_id, filename='presentations_by_account', prefix=''):
    query = f'''
    select user_id, id, createdat_date from aha_report_v5.dim_presentations
    where user_id in (select id from aha_report_v5.dim_users where account_id = {account_id})
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_user_count_by_account(account_id, filename='user_count_by_account', prefix=''):
    query = f'''
    select count(*) as cnt from aha_report_v5.dim_users
    where account_id = {account_id}
    '''
    return fetch(query, f'{prefix}{filename}')


@st.cache_data(ttl=CACHE_TTL)
def fetch_presentations_by_ids(presentation_ids, filename='presentations_by_ids', prefix=''):
    query = f'''
    select id, title, user_id from aha_report_v5.dim_presentations
    where id in ({_.join(presentation_ids, ',')})
    '''
    return fetch(query, f'{prefix}{filename}')
