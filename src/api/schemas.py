from typing import Literal

from pydantic import BaseModel, Field

from src.models.match import ExternalMatch


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    tournament_id: int = Field(gt=0)
    match_id: int | None = Field(default=None, gt=0)


class QueryResponse(BaseModel):
    intent: str
    message: str
    data: object


class UpdateRequest(BaseModel):
    source_name: str = Field(default="api", min_length=1)
    matches: list[ExternalMatch]


class UpdateResponse(BaseModel):
    run_id: int
    matches_added: int
    matches_updated: int
    predictions_generated: int


class UserPickRequest(BaseModel):
    match_id: int = Field(gt=0)
    predicted_outcome: Literal["home", "draw", "away"]


class UserPicksRequest(BaseModel):
    picks: list[UserPickRequest]


class UserPickUpdateRequest(BaseModel):
    predicted_outcome: Literal["home", "draw", "away"]
