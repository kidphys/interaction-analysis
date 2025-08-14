from dotenv import load_dotenv
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.engine.url import URL

load_dotenv('.env.local')
import os

# Redshift connection parameters from environment
REDSHIFT_USER = os.getenv("REDSHIFT_USER")
REDSHIFT_PASSWORD = os.getenv("REDSHIFT_PASSWORD")

# build the sqlalchemy URL
url = URL.create(
    drivername='redshift+redshift_connector', # indicate redshift_connector driver and dialect will be used
    host='datawarehouse-prd.cps9bf1es8tr.us-east-1.redshift.amazonaws.com', # Amazon Redshift host
    port=5439, # Amazon Redshift port
    database='ahaslides', # Amazon Redshift database
    username=REDSHIFT_USER, # Amazon Redshift username
    password=REDSHIFT_PASSWORD # Amazon Redshift password
)
engine = sa.create_engine(url)

sql = """
SELECT 1;
"""

with engine.connect() as conn:
    res = conn.execute(text(sql))
    rows = res.fetchall()