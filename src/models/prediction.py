from dataclasses import dataclass
from enum import StrEnum


class PredictedResult(StrEnum):
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"


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