import pytest

from src.models.prediction import TeamRating
from src.prediction.poisson_model import PoissonPredictionModel


def test_poisson_prediction_is_normalized_and_exposes_scores() -> None:
    model = PoissonPredictionModel()
    home = TeamRating(1, "Local", 1500.0)
    away = TeamRating(2, "Visitante", 1500.0)

    prediction = model.predict(home, away)

    assert prediction.total_probability == pytest.approx(1.0)
    assert prediction.expected_home_goals == pytest.approx(1.4)
    assert prediction.expected_away_goals == pytest.approx(1.1)
    assert prediction.most_likely_score == (1, 1)
    assert prediction.score_matrix is not None
    assert len(prediction.score_matrix) == 121
    assert sum(prediction.score_matrix.values()) == pytest.approx(1.0)


def test_stronger_home_attack_increases_expected_goals() -> None:
    model = PoissonPredictionModel()
    away = TeamRating(2, "Visitante", 1500.0)

    baseline = model.predict(TeamRating(1, "Local", 1500.0), away)
    stronger = model.predict(
        TeamRating(
            1,
            "Local",
            1500.0,
            home_attack_strength=1.5,
        ),
        away,
    )

    assert stronger.expected_home_goals is not None
    assert baseline.expected_home_goals is not None
    assert stronger.expected_home_goals > baseline.expected_home_goals
    assert stronger.home_probability > baseline.home_probability


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("default_home_goals_average", 0.0),
        ("default_away_goals_average", -1.0),
        ("prior_matches", 0.0),
        ("max_goals", 0),
    ],
)
def test_rejects_invalid_configuration(
    keyword: str,
    value: float,
) -> None:
    with pytest.raises(ValueError):
        PoissonPredictionModel(**{keyword: value})


def test_rejects_negative_expected_goals() -> None:
    model = PoissonPredictionModel()
    invalid = TeamRating(
        1,
        "Local",
        1500.0,
        home_attack_strength=-1.0,
    )

    with pytest.raises(ValueError, match="cannot be negative"):
        model.predict(invalid, TeamRating(2, "Visitante", 1500.0))
