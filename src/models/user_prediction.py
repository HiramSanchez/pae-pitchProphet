from dataclasses import dataclass
from enum import StrEnum

from src.models.prediction import PredictedResult


class UserPredictionRoundStatus(StrEnum):
    OPEN = "open"
    FINALIZED = "finalized"
    EVALUATED = "evaluated"


@dataclass(frozen=True)
class UserPredictionRound:
    round_id: int
    tournament_id: int
    round_number: int
    predictor: str
    status: UserPredictionRoundStatus
    opened_at: str
    finalized_at: str | None
    evaluated_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class UserPrediction:
    prediction_id: int
    match_id: int
    tournament_id: int
    round_number: int
    predictor: str
    predicted_result: PredictedResult
    points_awarded: int | None
    created_at: str
    updated_at: str
    evaluated_at: str | None


@dataclass(frozen=True)
class UserPickSelection:
    match_id: int
    predicted_result: PredictedResult


@dataclass(frozen=True)
class UserPredictionModelSnapshot:
    snapshot_id: int
    user_prediction_id: int
    prediction_id: int
    model_name: str
    model_version: str
    predicted_result: PredictedResult
    home_probability: float
    draw_probability: float
    away_probability: float
    captured_at: str


@dataclass(frozen=True)
class PerformanceParticipant:
    name: str
    correct: int
    accuracy: float


@dataclass(frozen=True)
class PersonalPerformance:
    tournament_id: int
    evaluated_matches: int
    correct: int
    accuracy: float


@dataclass(frozen=True)
class PersonalModelComparison:
    tournament_id: int
    evaluated_matches: int
    participants: tuple[PerformanceParticipant, ...]
