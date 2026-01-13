from typing import Any, Dict, Iterator
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import create_react_agent
from redshift_api import execute_with_columns
from session_insight.tasks import MART_SQL
from structured_agent import InsightResponse, StructuredAgent, system_prompt
import pandas as pd
import os


def query_participant_answers(presentation_id: str):
    filepath = f"participant_answers_{presentation_id}.parquet"
    if os.path.exists(filepath):
        df = pd.read_parquet(filepath)
    else:
        sql = MART_SQL.format(presentation_id=presentation_id)
        rows, cols = execute_with_columns(sql)
        df = pd.DataFrame(rows, columns=cols)
        print('saving file', filepath)
        df.to_parquet(filepath)

    tf = pd.pivot_table(df, index='participant_name', values=['answer_text', 'answer_time_seconds'], columns=['slide_index', 'slide_title', 'slide_type'], aggfunc=lambda x: ','.join(map(str, x.dropna())))
    # return tf.to_csv(index=False)
    return str(tf.to_dict(orient='records'))


@tool
def tool_query_participant_answers(runnable_config: RunnableConfig):
    """
    Query the participant answers for a given presentation ID.
    Only call this once
    """
    presentation_id = runnable_config['configurable']['presentation_id']
    return query_participant_answers(presentation_id)

simple_system_prompt = """
You are a **helpful assistant** that provides **concise, structured insights** about the data.

3. **chart** – for visualizing data
   - Always include a **descriptive title**
   - Only **2 columns allowed**:
     - 1st column → x-axis
     - 2nd column → y-axis
   - Supported types: `bar`, `line`, `area`, `pie`, etc.
   - Use creativity to pick the best visualization for the insight

## 📚 Knowledge Base
- **Completion rate** = answered questions ÷ all questions
- **Accuracy rate** = correct answers ÷ all answers
- `all` can refer to:
  - all questions of a **presentation**
  - all questions of a **participant**
- **Opinion slides** (Poll, Open Ended):
  - Provide insights by **segmenting participants by their answers**

---

## 🔑 Guidelines
- Be **concise**: avoid long explanations (token limits)
- Prioritize **key insights** over verbose analysis
- Always provide **actionable takeaways**
- Keep data visualizations and tables **focused on what supports the insight**
"""

def convert_insight_response_to_assistant_message(insight_response: InsightResponse):
    message_items = [item.content for item in insight_response.items if item.type == "message"]
    return AIMessage(content="\n".join(message_items))


class ParticipantInsightAgent(StructuredAgent):
    def __init__(self, user_id: str = "1472007", presentation_id: str = "7880449"):
        self.user_id = user_id
        self.presentation_id = presentation_id
        self.insight_response = None   # ✅ add this

        data_str = query_participant_answers(self.presentation_id)

        enhanced_system_prompt = f"""
        {simple_system_prompt}

        # Data of this presentation
        {data_str}
        """
        sys_message = SystemMessage(content=enhanced_system_prompt, cache_control={ "type": "ephemeral" })
        self.messages = [sys_message]
        super().__init__()

    def _initialize_agent(self):
        """Initialize the React agent with memory"""
        model = init_chat_model(self.model_name, max_tokens=8096)
        llm = model.with_structured_output(InsightResponse)
        self.llm = llm

    def invoke(self, prompt: str):
        self.messages.append(HumanMessage(content=prompt))
        ai_message = self.llm.invoke(self.messages)
        self.messages.append(convert_insight_response_to_assistant_message(ai_message))
        return ai_message

    def set_presentation_id(self, presentation_id: str):
        self.presentation_id = presentation_id

    def _get_config(self):
        return {
            "configurable": {
                "thread_id": f"user_{self.user_id}",
                "user_id": self.user_id,
                "presentation_id": self.presentation_id
            }
        }