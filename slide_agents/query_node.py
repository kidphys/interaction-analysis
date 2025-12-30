

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

import duckdb
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
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

from typing import Any, Dict, List, Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field

# --- Items ---

class MessageItem(BaseModel):
    type: Literal["message"] = "message"
    content: str = Field(description="Agent insight summary / analysis message")

class TableViz(BaseModel):
    type: Literal["table"] = "table"
    title: str = Field(description="Title for the table")
    data: Dict[str, List[Any]] = Field(
        description="Table data in 'series' orient: {column_name: [values]}. All columns must be same length."
    )

class ChartViz(BaseModel):
    type: Literal["chart"] = "chart"
    title: str = Field(description="Title for the chart")

    chart_type: Literal["bar", "line", "pie", "scatter", "stacked_bar"] = Field(
        description="Type of chart"
    )

    # ✅ Optional because pie charts don't have axes
    x_field: Optional[str] = Field(default=None, description="Column name used for x-axis/categories")
    y_field: Optional[str] = Field(default=None, description="Column name used for y-axis/values")

    series_field: Optional[str] = Field(default=None, description="Optional column used for grouping/series")

    data: Dict[str, List[Any]] = Field(
        description="Chart data in 'series' orient: {column_name: [values]}"
    )

    # ✅ Enforce what pie needs vs what cartesian charts need
    # If you want strict validation, keep this validator; otherwise omit it.
    # Pydantic v2:
    @classmethod
    def _is_pie(cls, v: "ChartViz") -> bool:
        return v.chart_type == "pie"

    def model_post_init(self, __context: Any) -> None:
        if self.chart_type == "pie":
            # For pie, require exactly two columns in data OR at least "label" + "value"-like
            # (You can tighten this if you standardize keys.)
            if self.x_field is not None or self.y_field is not None:
                # allow, but typically not needed
                pass
        else:
            # For bar/line/scatter/etc, axes must be present
            if not self.x_field or not self.y_field:
                raise ValueError("x_field and y_field are required for non-pie charts")


# ✅ Discriminated union so Pydantic chooses correctly based on `type`
VisualizationItem = Annotated[Union[TableViz, ChartViz], Field(discriminator="type")]

insight_message_prompt = """
Return insights as 2–3 sentences ONLY.

Each insight must:
- Make one clear claim
- Cite at least one specific data point (number, %, delta, comparison)
- Explain why it matters or what action it suggests

Do NOT summarize data.
Do NOT use vague language (e.g., "high", "low", "many").
If you cannot support a claim with data, return NO_INSIGHT.
"""

class InsightItem(BaseModel):
    id: Optional[str] = Field(
        default=None,
        description="Backend-assigned unique ID"
    )
    message: MessageItem = Field(description=insight_message_prompt)
    visualization: VisualizationItem = Field(description="Exactly one visualization (table or chart)")

class InsightResponse(BaseModel):
    items: List[InsightItem] = Field(description="List of message+visualization pairs")


from langchain.output_parsers import PydanticOutputParser


def analyze_data(question: str, data_table: str, model: str = 'anthropic:claude-sonnet-4-20250514', model_provider: str = '') -> InsightResponse:
    parser = PydanticOutputParser(pydantic_object=InsightResponse)

    try:
        if model_provider != '':
          llm = init_chat_model(model=model, model_provider=model_provider)
        else:
          llm = init_chat_model(model=model)
        prompt = ChatPromptTemplate.from_template(data_commentor_prompt_template)
        chain = prompt | llm | parser
        response = chain.invoke({"question": question, "data_table": data_table, "output_schema": parser.get_format_instructions()})
        return response
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