import pytest

from src.services.elo_service import actual_score, expected_score, update_elo


def test_equal_ratings_have_equal_expectation() -> None:
    probability = expected_score(1500, 1500)

    assert probability == pytest.approx(0.5)


def test_home_win_increases_home_rating() -> None:
    result = update_elo(
        home_elo=1500,
        away_elo=1500,
        home_goals=2,
        away_goals=1,
    )

    assert result.home_elo_after > 1500
    assert result.away_elo_after < 1500


def test_away_win_decreases_home_rating() -> None:
    result = update_elo(
        home_elo=1500,
        away_elo=1500,
        home_goals=1,
        away_goals=3,
    )

    assert result.home_elo_after < 1500
    assert result.away_elo_after > 1500


@pytest.mark.parametrize(
    ("home_goals", "away_goals", "expected"),
    [
        (2, 1, 1.0),
        (1, 1, 0.5),
        (0, 2, 0.0),
    ],
)
def test_actual_score(
    home_goals: int,
    away_goals: int,
    expected: float,
) -> None:
    assert actual_score(home_goals, away_goals) == expected