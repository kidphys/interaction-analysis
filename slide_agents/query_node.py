

from typing import Any, Dict, List

import duckdb
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from slide_agents.prompt_sql_generator import prompt_template
from slide_agents.prompt_data_commentor import prompt_template as data_commentor_prompt_template


def create_sql_query(question: str, schema: str, model: str = 'claude-haiku-4-5-20251001', model_provider='') -> str:
  if model_provider != '':
    llm = init_chat_model(model, model_provider=model_provider)
  else:
    llm = init_chat_model(model)
  prompt = ChatPromptTemplate.from_template(prompt_template)
  chain = prompt | llm
  response = chain.invoke({"desc": question, "schema_info": schema})
  return response.content.strip()


def query_db(sql: str, conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
  res = conn.execute(sql).fetchdf()
  return res


def get_table_schemas(conn: duckdb.DuckDBPyConnection) -> Dict[str, str]:
  def get_table_schema(table_name):
    res = conn.execute(f"DESCRIBE {table_name};").fetchdf()
    return res[["column_name", "column_type"]].to_string()
  res = conn.execute("SHOW TABLES;").fetchdf()

  schema = ''
  for table in res.to_dict(orient='records'):
    schema += f"Table: {table['name']}\n"
    schema += f"Schema: {get_table_schema(table['name'])}\n"
  return schema


def analyze_data(question: str, data_table: str, model: str = 'anthropic:claude-sonnet-4-20250514', model_provider: str = '') -> Dict[str, Any]:
    try:
        if model_provider != '':
          llm = init_chat_model(model=model, model_provider=model_provider)
        else:
          llm = init_chat_model(model=model)
        prompt = ChatPromptTemplate.from_template(data_commentor_prompt_template)
        chain = prompt | llm
        response = chain.invoke({"question": question, "data_table": data_table})
        return response.content.strip()
    except Exception as e:
        return f"Questino: {question}\nError analyzing data: {e}"


sample_queries_2 = [
  "What are the top 20 most frequently appearing presentation titles, and how many times has each been delivered?",
  "What are the most common slide topics or themes across all presentations (identify by slide_title and slide_description patterns)?",
  "Which presentations have been delivered multiple times to similar audiences? Look for repeated presentation_titles across different delivery dates.",
  "What is the distribution of slide types across all presentations? Which formats dominate (e.g., text, interactive, visual)?",
  "Which slides or topics show the lowest engagement (answer_percentage)? What are their titles and descriptions?",
  "Are there presentations that have high participant counts but low answer engagement? What topics do these cover?"
]


if __name__ == "__main__":
    conn = duckdb.connect('temp.duckdb')
    table_schemas = get_table_schemas(conn)
    # question = 'What are the most common slide topics or themes across all presentations (identify by slide_title and slide_description patterns)?'
    question = sample_queries_2[2]
    # model = 'anthropic:claude-sonnet-4-20250514'
    # model = 'qwen/qwen3-32b'
    model = 'llama-3.3-70b-versatile'
    model_provider = 'groq'
    sql = create_sql_query(question, table_schemas, model='anthropic:claude-sonnet-4-20250514')
    data = query_db(sql, conn)
    analysis = analyze_data(question, str(data), model=model, model_provider=model_provider)
    print('\n')
    print('\n')
    print(sql)
    print('\n')
    print('\n')
    print(data)
    print('\n')
    print('\n')
    print(analysis)