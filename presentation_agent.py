"""
This module provides an agent that can query data from a single presentation and provide insights about it.
"""
import pandas as pd
import duckdb
import pyarrow as pa
from functools import lru_cache
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import create_react_agent
from redshift_api import execute_with_columns
from structured_agent import InsightResponse, StructuredAgent, get_conn_for_user, normalize_timestamps, system_prompt
from structured_agent import pre_model_hook

@lru_cache
def get_all_answers(presentation_id: str):
    sql = f"""
    SELECT
        fa.user_id,
        fa.slide_id,
        fa.question_id,
        fa.participant_id,
        fa.master_presentation_id as presentation_id,
        fa.slide_type,
        dq.slide_title,
        dp.title as presentation_title,
        fa.submitted_answer_text,
        fa.correct,
        fa.createdat
    FROM aha_report_v5.fact_answers fa
    JOIN aha_report_v5.dim_questions dq
        ON fa.question_id = dq.id
    JOIN aha_report_v5.dim_presentations dp
        ON fa.master_presentation_id = dp.id
    WHERE fa.presentation_id = '{presentation_id}'
    """
    try:
        rows, cols = execute_with_columns(sql)
        return {
            'rows': rows,
            'cols': cols,
        }
    except Exception as e:
        import traceback
        print(f'Exception type: {type(e)}')
        print(f'Args: {e.args}')
        print('Full traceback:')
        traceback.print_exc()
        raise e

@lru_cache
def get_conn_for_presentation(presentation_id):
    all_answers = get_all_answers(presentation_id)
    df = pd.DataFrame(all_answers['rows'])
    df.columns = all_answers['cols']
    con = duckdb.connect(database=":memory:")
    table = pa.Table.from_pandas(df)
    con.register("answers", table)
    return con


def presentation_query(sql: str, config: RunnableConfig):
    """
    Run a query on the DuckDb inmem OLAP db given the following table:
    `answers`
        user_id (varchar)
        slide_id (varchar)
        question_id (varchar)
        participant_id (varchar)
        presentation_id (varchar)
        presentation_title (varchar)
        slide_type (varchar): can be 'Pick Answer', 'Poll', 'Open Ended'
        slide_title (varchar): the title of the question asked in the slide
        submitted_answer_text (varchar): the answer that this participant submitted
        correct (boolean): true if the answer is correct
        createdat (timestamp)
    """
    print(f'\n')
    print(f'FAST QUERY: {sql}\n')
    con = get_conn_for_presentation(config['metadata']['presentation_id'])
    res = con.execute(sql).fetchdf()
    res = normalize_timestamps(res)
    return res.to_dict(orient='list')


class PresentationAgent(StructuredAgent):

    def __init__(self, presentation_id: str):
        super().__init__()
        self.presentation_id = presentation_id

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        memory = MemorySaver()
        model = init_chat_model(self.model_name, max_tokens=8096)
        tools = [presentation_query]
        sys_message = SystemMessage(content=system_prompt)

        self.agent_executor = create_react_agent(
            model, tools, checkpointer=memory,
            prompt=sys_message, response_format=InsightResponse,
            pre_model_hook=pre_model_hook
        )

    def _get_config(self):
        return {
            "configurable": {
                "thread_id": f"user_{self.user_id}",
                "presentation_id": self.presentation_id
            }
        }

    def query(self, prompt: str):
        return super().query(prompt)

    def stream_query(self, prompt: str):
        return super().stream_query(prompt)