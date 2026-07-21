from dataclasses import dataclass

from src.models.prediction import PredictedResult, Prediction


@dataclass(frozen=True)
class BacktestPrediction:
    match_id: int
    tournament_id: int
    round_number: int
    prediction: Prediction
    actual_result: PredictedResult
    home_elo_before: float
    away_elo_before: float


@dataclass(frozen=True)
class ModelEvaluation:
    model_name: str
    model_version: str
    tournament_id: int | None
    evaluated_matches: int
    log_loss: float
    brier_score: float
    accuracy: float
    top_two_accuracy: float
    calibration_error: float
    confusion_matrix: dict[str, dict[str, int]]
    evaluated_at: str
    evaluation_id: int | None = None
