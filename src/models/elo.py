from math import pow
from dataclasses import dataclass


@dataclass(frozen=True)
class EloUpdate:
    home_elo_before: float
    away_elo_before: float
    home_elo_after: float
    away_elo_after: float
    home_change: float
    away_change: float


def expected_score(
    rating_a: float,
    rating_b: float,
) -> float:
    return 1.0 / (
        1.0 + pow(10.0, (rating_b - rating_a) / 400.0)
    )
