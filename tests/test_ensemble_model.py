import pytest

from src.models.prediction import (
    PredictedResult,
    Prediction,
    TeamRating,
)
from src.prediction.ensemble_model import EnsemblePredictionModel


class FixedModel:
    version = "1.0.0"

    def __init__(
        self,
        name: str,
        probabilities: tuple[float, float, float],
    ) -> None:
        self.name = name
        self.probabilities = probabilities

    @property
    def configuration(self) -> dict[str, float]:
        return {"parameter": 1.0}

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        home, draw, away = self.probabilities
        probabilities = {
            PredictedResult.HOME: home,
            PredictedResult.DRAW: draw,
            PredictedResult.AWAY: away,
        }
        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=home,
            draw_probability=draw,
            away_probability=away,
            predicted_result=max(
                probabilities,
                key=probabilities.__getitem__,
            ),
        )


def test_combines_component_probabilities_with_normalized_weights() -> None:
    first = FixedModel("first", (0.6, 0.3, 0.1))
    second = FixedModel("second", (0.2, 0.2, 0.6))
    model = EnsemblePredictionModel(
        [first, second],
        weights={"first:1.0.0": 3.0, "second:1.0.0": 1.0},
    )

    prediction = model.predict(
        TeamRating(1, "Local", 1500.0),
        TeamRating(2, "Visitante", 1500.0),
    )

    assert prediction.home_probability == pytest.approx(0.5)
    assert prediction.draw_probability == pytest.approx(0.275)
    assert prediction.away_probability == pytest.approx(0.225)
    assert prediction.total_probability == pytest.approx(1.0)
    assert prediction.predicted_result == PredictedResult.HOME
    assert prediction.component_probabilities == {
        "first:1.0.0": {"home": 0.6, "draw": 0.3, "away": 0.1},
        "second:1.0.0": {"home": 0.2, "draw": 0.2, "away": 0.6},
    }
    assert model.configuration["weight:first:1.0.0"] == 0.75
    assert model.configuration["component:first:1.0.0:parameter"] == 1.0


@pytest.mark.parametrize(
    "models, weights",
    [
        ([FixedModel("one", (0.4, 0.3, 0.3))], None),
        (
            [
                FixedModel("one", (0.4, 0.3, 0.3)),
                FixedModel("one", (0.4, 0.3, 0.3)),
            ],
            None,
        ),
        (
            [
                FixedModel("one", (0.4, 0.3, 0.3)),
                FixedModel("two", (0.4, 0.3, 0.3)),
            ],
            {"one:1.0.0": 1.0},
        ),
        (
            [
                FixedModel("one", (0.4, 0.3, 0.3)),
                FixedModel("two", (0.4, 0.3, 0.3)),
            ],
            {"one:1.0.0": 1.0, "two:1.0.0": 0.0},
        ),
        (
            [
                FixedModel("one", (0.4, 0.3, 0.3)),
                FixedModel("two", (0.4, 0.3, 0.3)),
            ],
            {"one:1.0.0": 1.0, "two:1.0.0": float("nan")},
        ),
    ],
)
def test_rejects_invalid_ensemble_configuration(
    models: list[FixedModel],
    weights: dict[str, float] | None,
) -> None:
    with pytest.raises(ValueError):
        EnsemblePredictionModel(models, weights)
