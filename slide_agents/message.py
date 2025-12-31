
from pydantic import BaseModel, Field
from typing import List, Literal
from typing import Union


class ResearchInput(BaseModel):
    questions: List[str] = Field(..., description="List of questions to answer")


message_with_cititation_prompt = """
An analysis with data reference (using citation_id) to support your argument.
Keep the tone playful yet scientific.
"""

message_prompt = """
Simple message, including reply, recommendation, arugment or encouragement from the agent.
Keep the tone playful yet scientific.
"""

class Message(BaseModel):
    type: Literal["message"] = "message"
    content: str = Field(description=message_prompt)

class MessageWithCitation(BaseModel):
    type: Literal["message_with_citation"] = "message_with_citation"
    content: str = Field(description=message_with_cititation_prompt)
    citation_id: str = Field(description="ID of the InsightItem this message references (if there is no citation, leave it blank)")


class InsightResponseV2(BaseModel):
    items: List[Union[Message, MessageWithCitation]] = Field(description="List of messages")