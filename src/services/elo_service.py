from src.config import ELO_K_FACTOR, HOME_ADVANTAGE_ELO
from src.models.elo import EloUpdate, expected_score


# Transitional re-export kept for compatibility with existing imports.
# New code should import expected_score from src.models.elo.


def actual_score(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0

    if home_goals < away_goals:
        return 0.0

    return 0.5


def goal_difference_multiplier(
    home_goals: int,
    away_goals: int,
) -> float:
    difference = abs(home_goals - away_goals)

    if difference <= 1:
        return 1.0

    if difference == 2:
        return 1.5

    return min(2.5, 1.5 + (difference - 2) * 0.25)


def update_elo(
    home_elo: float,
    away_elo: float,
    home_goals: int,
    away_goals: int,
    k_factor: float = ELO_K_FACTOR,
    home_advantage: float = HOME_ADVANTAGE_ELO,
) -> EloUpdate:
    adjusted_home_elo = home_elo + home_advantage

    expected_home = expected_score(adjusted_home_elo, away_elo)
    actual_home = actual_score(home_goals, away_goals)

    multiplier = goal_difference_multiplier(home_goals, away_goals)
    change = k_factor * multiplier * (actual_home - expected_home)

    return EloUpdate(
        home_elo_before=home_elo,
        away_elo_before=away_elo,
        home_elo_after=home_elo + change,
        away_elo_after=away_elo - change,
        home_change=change,
        away_change=-change,
    )
