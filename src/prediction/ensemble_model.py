import math
from collections.abc import Iterable, Mapping

from src.models.prediction import (
    PredictedResult,
    Prediction,
    TeamRating,
)
from src.prediction.base import PredictionModel


def model_identity(model: PredictionModel) -> str:
    return f"{model.name}:{model.version}"


class EnsemblePredictionModel:
    name = "ensemble"
    version = "1.0.0"

    def __init__(
        self,
        models: Iterable[PredictionModel],
        weights: Mapping[str, float] | None = None,
    ) -> None:
        self.models = tuple(models)
        if len(self.models) < 2:
            raise ValueError("Ensemble requires at least two models")

        identities = [model_identity(model) for model in self.models]
        if len(set(identities)) != len(identities):
            raise ValueError("Ensemble model identities must be unique")

        configured_weights = (
            dict(weights)
            if weights is not None
            else {identity: 1.0 for identity in identities}
        )
        if set(configured_weights) != set(identities):
            raise ValueError("Weights must match all ensemble models")
        if any(
            not math.isfinite(weight) or weight <= 0
            for weight in configured_weights.values()
        ):
            raise ValueError("Ensemble weights must be positive")

        total_weight = sum(configured_weights.values())
        self.weights = {
            identity: weight / total_weight
            for identity, weight in configured_weights.items()
        }

    @property
    def configuration(self) -> dict[str, float]:
        configuration: dict[str, float] = {}
        for model in self.models:
            identity = model_identity(model)
            configuration[f"weight:{identity}"] = self.weights[identity]
            for key, value in model.configuration.items():
                configuration[f"component:{identity}:{key}"] = value
        return configuration

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        component_predictions = {
            model_identity(model): model.predict(home_team, away_team)
            for model in self.models
        }
        probabilities = {
            result: sum(
                self.weights[identity]
                * self._probability(prediction, result)
                for identity, prediction in component_predictions.items()
            )
            for result in PredictedResult
        }

        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=probabilities[PredictedResult.HOME],
            draw_probability=probabilities[PredictedResult.DRAW],
            away_probability=probabilities[PredictedResult.AWAY],
            predicted_result=max(
                probabilities,
                key=probabilities.__getitem__,
            ),
            component_probabilities={
                identity: {
                    "home": prediction.home_probability,
                    "draw": prediction.draw_probability,
                    "away": prediction.away_probability,
                }
                for identity, prediction in component_predictions.items()
            },
        )

    @staticmethod
    def _probability(
        prediction: Prediction,
        result: PredictedResult,
    ) -> float:
        return {
            PredictedResult.HOME: prediction.home_probability,
            PredictedResult.DRAW: prediction.draw_probability,
            PredictedResult.AWAY: prediction.away_probability,
        }[result]
