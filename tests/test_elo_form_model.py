import pytest

from src.models.prediction import TeamRating
from src.prediction.elo_form_model import EloFormPredictionModel
from src.prediction.elo_model import EloPredictionModel


def test_model_has_versioned_configuration() -> None:
    model = EloFormPredictionModel()

    assert model.name == "elo_form"
    assert model.version == "1.0.0"
    assert model.configuration["recent_points_weight"] == 4.0
    assert (
        model.configuration["recent_goal_difference_weight"]
        == 3.0
    )
    assert model.configuration["venue_performance_weight"] == 20.0


def test_positive_home_form_increases_home_probability() -> None:
    home = TeamRating(
        1,
        "Local",
        1500.0,
        recent_points=15.0,
        recent_goal_difference=8.0,
        home_points_per_match=3.0,
    )
    away = TeamRating(2, "Visitante", 1500.0)

    elo_prediction = EloPredictionModel().predict(home, away)
    form_prediction = EloFormPredictionModel().predict(home, away)

    assert (
        form_prediction.home_probability
        > elo_prediction.home_probability
    )


def test_positive_away_form_increases_away_probability() -> None:
    home = TeamRating(1, "Local", 1500.0)
    away = TeamRating(
        2,
        "Visitante",
        1500.0,
        recent_points=15.0,
        recent_goal_difference=8.0,
        away_points_per_match=3.0,
    )

    elo_prediction = EloPredictionModel().predict(home, away)
    form_prediction = EloFormPredictionModel().predict(home, away)

    assert (
        form_prediction.away_probability
        > elo_prediction.away_probability
    )


def test_neutral_form_matches_base_elo_model() -> None:
    home = TeamRating(1, "Local", 1500.0)
    away = TeamRating(2, "Visitante", 1500.0)

    elo_prediction = EloPredictionModel().predict(home, away)
    form_prediction = EloFormPredictionModel().predict(home, away)

    assert form_prediction == elo_prediction


@pytest.mark.parametrize(
    "parameter",
    [
        "recent_points_weight",
        "recent_goal_difference_weight",
        "venue_performance_weight",
    ],
)
def test_negative_weights_are_rejected(parameter: str) -> None:
    with pytest.raises(ValueError, match=parameter):
        EloFormPredictionModel(**{parameter: -1.0})
