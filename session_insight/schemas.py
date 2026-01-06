from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field


# ----------------------------
# Metadata
# ----------------------------

class AnalysisMetadata(BaseModel):
    analysis_scope: str = Field(
        description="What this analysis focuses on, e.g. participation, accuracy, free_text, flow"
    )
    assumptions_applied: List[str] = Field(
        description="Key assumptions or rules applied during analysis"
    )
    confidence_level: Literal["high", "medium", "low"] = Field(
        description="Overall confidence in the analysis conclusions"
    )


# ----------------------------
# Observations
# ----------------------------

class AffectedEntities(BaseModel):
    slides: List[Union[int, str]] = Field(
        description="Slide indices or titles affected"
    )
    slide_types: List[str] = Field(
        description="Slide types involved in this observation"
    )
    participants: Literal["all", "subset", "specific"] = Field(
        description="Scope of participants affected"
    )


class KeyObservation(BaseModel):
    observation: str = Field(
        description="What was observed in the data"
    )
    evidence: str = Field(
        description="Summary of data evidence supporting the observation"
    )
    affected_entities: AffectedEntities
    severity: Literal["high", "medium", "low"] = Field(
        description="Impact or urgency of the observation"
    )


# ----------------------------
# Interpretation
# ----------------------------

class Interpretation(BaseModel):
    insight: str = Field(
        description="What the observation likely means"
    )
    explanation: str = Field(
        description="Reasoning behind the interpretation"
    )
    alternative_explanations: List[str] = Field(
        description="Other plausible explanations or confounding factors"
    )


# ----------------------------
# Recommendations
# ----------------------------

class ActionableRecommendation(BaseModel):
    recommendation: str = Field(
        description="Concrete action to take"
    )
    target: Literal[
        "slide",
        "slide_type",
        "session_flow",
        "facilitation",
        "analytics"
    ] = Field(
        description="Where the recommendation should be applied"
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Priority of this recommendation"
    )
    expected_impact: str = Field(
        description="What improvement is expected if applied"
    )


# ----------------------------
# Follow-up
# ----------------------------

class FollowUpAnalysis(BaseModel):
    question: str = Field(
        description="Open question raised by this analysis"
    )
    suggested_method: str = Field(
        description="Suggested analysis, data, or experiment to answer it"
    )


# ----------------------------
# Root Output Schema
# ----------------------------

class SlideAnalysisResultBase(BaseModel):
    metadata: AnalysisMetadata
    key_observations: List[KeyObservation]
    interpretation: List[Interpretation]
    actionable_recommendations: List[ActionableRecommendation]
    follow_up_analysis: List[FollowUpAnalysis]
    coaching_message: Optional[str] = Field(
        default=None,
        description="A positive and encouraging message for the presenter related to these insights."
    )

class SlideAnalysisResult(SlideAnalysisResultBase):
    source_data: Optional[Union[List[dict], str]] = Field(
        default=None,
        description="The raw data used for this analysis"
    )
