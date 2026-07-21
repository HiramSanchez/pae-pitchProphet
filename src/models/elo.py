from math import pow


def expected_score(
    rating_a: float,
    rating_b: float,
) -> float:
    return 1.0 / (
        1.0 + pow(10.0, (rating_b - rating_a) / 400.0)
    )
