import pytest

from src.models.prediction import PredictionInput


def test_prediction_input_accepts_different_teams() -> None:
    prediction_input = PredictionInput(
        home_team_id=1,
        away_team_id=2,
    )

    assert prediction_input.home_team_id == 1
    assert prediction_input.away_team_id == 2


def test_prediction_input_rejects_same_team() -> None:
    with pytest.raises(
        ValueError,
        match="must be different",
    ):
        PredictionInput(
            home_team_id=1,
            away_team_id=1,
        )


@pytest.mark.parametrize(
    "home_team_id, away_team_id",
    [
        (0, 1),
        (-1, 1),
        (1, 0),
        (1, -1),
    ],
)
def test_prediction_input_rejects_invalid_ids(
    home_team_id: int,
    away_team_id: int,
) -> None:
    with pytest.raises(ValueError):
        PredictionInput(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )