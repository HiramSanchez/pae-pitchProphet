from dataclasses import dataclass, field
from enum import StrEnum


class PredictedResult(StrEnum):
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"


@dataclass(frozen=True)
class TeamRating:
    team_id: int
    name: str
    elo: float
    recent_points: float = 0.0
    recent_goal_difference: float = 0.0
    home_points_per_match: float = 0.0
    away_points_per_match: float = 0.0


@dataclass(frozen=True)
class PredictionInput:
    home_team_id: int
    away_team_id: int

    def __post_init__(self) -> None:
        if self.home_team_id <= 0:
            raise ValueError("home_team_id must be positive")

        if self.away_team_id <= 0:
            raise ValueError("away_team_id must be positive")

        if self.home_team_id == self.away_team_id:
            raise ValueError(
                "Home and away teams must be different"
            )


@dataclass(frozen=True)
class Prediction:
    home_team_id: int
    away_team_id: int
    home_probability: float
    draw_probability: float
    away_probability: float
    predicted_result: PredictedResult

    @property
    def total_probability(self) -> float:
        return (
            self.home_probability
            + self.draw_probability
            + self.away_probability
        )


@dataclass(frozen=True)
class VersionedPrediction:
    match_id: int
    model_name: str
    model_version: str
    configuration: dict[str, float]
    prediction: Prediction
    input_snapshot: dict[str, object]
    created_at: str
    prediction_id: int | None = None
    explanation: dict[str, object] | None = field(
        default=None
    )

    @property
    def confidence(self) -> float:
        return max(
            self.prediction.home_probability,
            self.prediction.draw_probability,
            self.prediction.away_probability,
        )
