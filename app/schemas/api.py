from typing import Literal

from pydantic import BaseModel, Field


Strategy = Literal["collaborative", "content", "hybrid", "ab_auto"]


class InteractionIn(BaseModel):
    movie_id: int = Field(..., gt=0)
    rating: float = Field(..., ge=0.5, le=5.0)


class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    score: float
    strategy: str
    explanation: str


class RecommendationResponse(BaseModel):
    user_id: int
    served_strategy: str
    model_version: str
    items: list[RecommendationItem]


class ExplainResponse(BaseModel):
    user_id: int
    served_strategy: str
    reasons: list[str]


class RetrainResponse(BaseModel):
    status: str
    model_version: str
