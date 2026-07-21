from typing import Protocol

from src.models.prediction import Prediction, TeamRating


class PredictionModel(Protocol):
    name: str
    version: str

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        ...
