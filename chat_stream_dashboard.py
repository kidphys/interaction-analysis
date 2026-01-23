from langchain_core.messages import AIMessageChunk
from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model


from typing import TypedDict, List

from langgraph.graph import StateGraph, END
from langchain.chat_models import init_chat_model
from langchain.schema import BaseMessage

from streamable_markdown.markdown_streamer import MarkdownStreamer
from streamable_markdown.parser import parse_text_to_dataframe


# -------- State --------
class ChatState(TypedDict):
    messages: List[BaseMessage]


# -------- Model --------
model = init_chat_model("anthropic:claude-sonnet-4-20250514")


# -------- Node --------
def chat_node(state: ChatState):
    response = model.invoke(state["messages"])
    return {"messages": state["messages"] + [response]}


# -------- Graph --------
builder = StateGraph(ChatState)
builder.add_node("chat", chat_node)
builder.set_entry_point("chat")
builder.add_edge("chat", END)

graph = builder.compile()


system_prompt = """
Answer my question and use following markdown syntax to display supported table
```df
format: csv
dtypes: age=int, price=float, active=bool


name,age,price,active
A,30,9.5,true
B,20,5.0,false
```

Give me a table of world population data
"""

import streamlit as st

def st_stream_markdown():
    input_messages = [
        {"role": "user", "content": system_prompt}
    ]

    markdown_stream = MarkdownStreamer()
    for event in graph.stream(
        {"messages": input_messages},
        stream_mode="messages"
    ):
        for msg in event:
            if isinstance(msg, AIMessageChunk):
                markdown_stream.add(msg.content)
                markdown_s = markdown_stream.get_markdowns()
                if len(markdown_s) > 0:
                    for markdown in markdown_s:
                        if isinstance(markdown, str):
                            yield markdown
                        elif isinstance(markdown, dict):
                            df = parse_text_to_dataframe(markdown['content'])
                            yield df


# -------- Run with streaming --------
if __name__ == "__main__":
    st.write_stream(st_stream_markdown())