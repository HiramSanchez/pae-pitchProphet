import pytest

from src.models.prediction import PredictedResult, TeamRating
from src.prediction.elo_model import EloPredictionModel


def team(
    team_id: int,
    elo: float,
) -> TeamRating:
    return TeamRating(
        team_id=team_id,
        name=f"Equipo {team_id}",
        elo=elo,
    )


def test_model_has_name_and_version() -> None:
    model = EloPredictionModel()

    assert model.name == "elo"
    assert model.version == "1.0.0"
    assert model.configuration == {
        "home_advantage": 80.0,
        "max_draw_probability": 0.28,
        "min_draw_probability": 0.12,
        "draw_decay_scale": 400.0,
    }


def test_probabilities_sum_to_one_and_are_valid() -> None:
    prediction = EloPredictionModel().predict(
        home_team=team(1, 1800.0),
        away_team=team(2, 1300.0),
    )

    assert prediction.total_probability == pytest.approx(1.0)
    assert 0 <= prediction.home_probability <= 1
    assert 0 <= prediction.draw_probability <= 1
    assert 0 <= prediction.away_probability <= 1


def test_home_advantage_favors_home_team_with_equal_elo() -> None:
    prediction = EloPredictionModel().predict(
        home_team=team(1, 1500.0),
        away_team=team(2, 1500.0),
    )

    assert (
        prediction.home_probability
        > prediction.away_probability
    )
    assert prediction.predicted_result == PredictedResult.HOME


def test_much_stronger_away_team_is_favorite() -> None:
    prediction = EloPredictionModel().predict(
        home_team=team(1, 1300.0),
        away_team=team(2, 1800.0),
    )

    assert (
        prediction.away_probability
        > prediction.home_probability
    )
    assert prediction.predicted_result == PredictedResult.AWAY


def test_balanced_teams_have_more_draw_probability() -> None:
    model = EloPredictionModel(home_advantage=0.0)

    balanced = model.predict(
        home_team=team(1, 1500.0),
        away_team=team(2, 1500.0),
    )
    unbalanced = model.predict(
        home_team=team(3, 1800.0),
        away_team=team(4, 1300.0),
    )

    assert (
        balanced.draw_probability
        > unbalanced.draw_probability
    )


@pytest.mark.parametrize(
    ("configuration", "message"),
    [
        ({"home_advantage": -1.0}, "home_advantage"),
        (
            {"min_draw_probability": -0.1},
            "min_draw_probability",
        ),
        (
            {"min_draw_probability": 1.1},
            "min_draw_probability",
        ),
        (
            {"max_draw_probability": -0.1},
            "max_draw_probability",
        ),
        (
            {"max_draw_probability": 1.1},
            "max_draw_probability",
        ),
        (
            {
                "min_draw_probability": 0.4,
                "max_draw_probability": 0.3,
            },
            "cannot exceed",
        ),
        ({"draw_decay_scale": 0.0}, "draw_decay_scale"),
        ({"draw_decay_scale": -1.0}, "draw_decay_scale"),
    ],
)
def test_invalid_configuration_raises_error(
    configuration: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        EloPredictionModel(**configuration)
