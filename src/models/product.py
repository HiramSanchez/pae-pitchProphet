from dataclasses import dataclass

from src.models.prediction import PredictedResult
from src.models.query import PredictionView
from src.models.user_prediction import (
    UserPrediction,
    UserPredictionRound,
)


@dataclass(frozen=True)
class ProductMatch:
    match_id: int
    home_team_name: str
    away_team_name: str
    status: str
    match_date: str | None
    personal_pick: UserPrediction | None
    predictions: tuple[PredictionView, ...]


@dataclass(frozen=True)
class NextRound:
    tournament_id: int
    round_number: int
    journal: UserPredictionRound | None
    matches: tuple[ProductMatch, ...]


@dataclass(frozen=True)
class RoundResult:
    match_id: int
    home_team_name: str
    away_team_name: str
    status: str
    home_goals: int | None
    away_goals: int | None
    actual_result: PredictedResult | None
    personal_pick: UserPrediction | None


@dataclass(frozen=True)
class RoundResults:
    tournament_id: int
    round_number: int
    journal: UserPredictionRound | None
    matches: tuple[RoundResult, ...]
