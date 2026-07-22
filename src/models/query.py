from dataclasses import dataclass

from src.models.prediction import Prediction


@dataclass(frozen=True)
class PredictionView:
    prediction_id: int
    match_id: int
    tournament_id: int
    round_number: int
    home_team_name: str
    away_team_name: str
    model_name: str
    model_version: str
    prediction: Prediction
    confidence: float
    explanation: dict[str, object] | None
    created_at: str


@dataclass(frozen=True)
class BestPrediction:
    prediction: PredictionView
    agreement_ratio: float
    agreeing_models: tuple[str, ...]
    calibration_error: float | None
    evaluated_matches: int


@dataclass(frozen=True)
class PredictionExplanation:
    prediction: PredictionView
    explanation: dict[str, object]


@dataclass(frozen=True)
class ModelComparison:
    match_id: int
    predictions: tuple[PredictionView, ...]
    favorites: dict[str, str]
    agreed_result: str | None
    probability_ranges: dict[str, tuple[float, float]]


@dataclass(frozen=True)
class PredictionRevision:
    revision_id: int
    prediction_id: int
    match_id: int
    model_name: str
    model_version: str
    prediction: Prediction
    confidence: float
    input_snapshot: dict[str, object]
    created_at: str
    replaced_at: str


@dataclass(frozen=True)
class PredictionChange:
    previous: PredictionRevision
    current: PredictionView
    result_changed: bool
    probability_deltas: dict[str, float]
