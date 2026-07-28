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


class ProductMatchResponse(BaseModel):
    match_id: int
    home_team_name: str
    away_team_name: str
    status: str
    match_date: str | None
    personal_pick: object | None
    predictions: list[object]


class NextRoundResponse(BaseModel):
    tournament_id: int
    round_number: int
    journal: object | None
    matches: list[ProductMatchResponse]


class RoundResultResponse(BaseModel):
    match_id: int
    home_team_name: str
    away_team_name: str
    status: str
    home_goals: int | None
    away_goals: int | None
    actual_result: str | None
    personal_pick: object | None


class RoundResultsResponse(BaseModel):
    tournament_id: int
    round_number: int
    journal: object | None
    matches: list[RoundResultResponse]


class PersonalPerformanceResponse(BaseModel):
    tournament_id: int
    evaluated_matches: int
    correct: int
    accuracy: float


class PerformanceParticipantResponse(BaseModel):
    name: str
    correct: int
    accuracy: float


class PersonalModelComparisonResponse(BaseModel):
    tournament_id: int
    evaluated_matches: int
    participants: list[PerformanceParticipantResponse]
