import math

from src.config import (
    POISSON_DEFAULT_AWAY_GOALS,
    POISSON_DEFAULT_HOME_GOALS,
    POISSON_MAX_GOALS,
    POISSON_PRIOR_MATCHES,
)
from src.models.prediction import (
    PredictedResult,
    Prediction,
    TeamRating,
)


class PoissonPredictionModel:
    """Poisson model normalized over the score range 0..max_goals."""

    name = "poisson"
    version = "1.0.0"

    def __init__(
        self,
        default_home_goals_average: float = (
            POISSON_DEFAULT_HOME_GOALS
        ),
        default_away_goals_average: float = (
            POISSON_DEFAULT_AWAY_GOALS
        ),
        prior_matches: float = POISSON_PRIOR_MATCHES,
        max_goals: int = POISSON_MAX_GOALS,
    ) -> None:
        if default_home_goals_average <= 0:
            raise ValueError(
                "default_home_goals_average must be positive"
            )
        if default_away_goals_average <= 0:
            raise ValueError(
                "default_away_goals_average must be positive"
            )
        if prior_matches <= 0:
            raise ValueError("prior_matches must be positive")
        if max_goals < 1:
            raise ValueError("max_goals must be at least 1")

        self.default_home_goals_average = (
            default_home_goals_average
        )
        self.default_away_goals_average = (
            default_away_goals_average
        )
        self.prior_matches = prior_matches
        self.max_goals = max_goals

    @property
    def configuration(self) -> dict[str, float]:
        return {
            "default_home_goals_average": (
                self.default_home_goals_average
            ),
            "default_away_goals_average": (
                self.default_away_goals_average
            ),
            "prior_matches": self.prior_matches,
            "max_goals": float(self.max_goals),
        }

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        expected_home_goals = (
            home_team.league_home_goals_average
            * home_team.home_attack_strength
            * away_team.away_defense_strength
        )
        expected_away_goals = (
            away_team.league_away_goals_average
            * away_team.away_attack_strength
            * home_team.home_defense_strength
        )
        if expected_home_goals < 0 or expected_away_goals < 0:
            raise ValueError("Expected goals cannot be negative")

        raw_matrix: dict[str, float] = {}
        total_mass = 0.0
        for home_goals in range(self.max_goals + 1):
            home_probability = self._poisson_probability(
                expected_home_goals,
                home_goals,
            )
            for away_goals in range(self.max_goals + 1):
                probability = (
                    home_probability
                    * self._poisson_probability(
                        expected_away_goals,
                        away_goals,
                    )
                )
                raw_matrix[f"{home_goals}-{away_goals}"] = (
                    probability
                )
                total_mass += probability

        score_matrix = {
            score: probability / total_mass
            for score, probability in raw_matrix.items()
        }
        home_probability = 0.0
        draw_probability = 0.0
        away_probability = 0.0

        for score, probability in score_matrix.items():
            home_goals, away_goals = (
                int(value) for value in score.split("-")
            )
            if home_goals > away_goals:
                home_probability += probability
            elif home_goals < away_goals:
                away_probability += probability
            else:
                draw_probability += probability

        probabilities = {
            PredictedResult.HOME: home_probability,
            PredictedResult.DRAW: draw_probability,
            PredictedResult.AWAY: away_probability,
        }
        most_likely_score = max(
            score_matrix,
            key=score_matrix.__getitem__,
        )

        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=home_probability,
            draw_probability=draw_probability,
            away_probability=away_probability,
            predicted_result=max(
                probabilities,
                key=probabilities.__getitem__,
            ),
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
            most_likely_score=tuple(
                int(value)
                for value in most_likely_score.split("-")
            ),
            score_matrix=score_matrix,
        )

    @staticmethod
    def _poisson_probability(
        expected_goals: float,
        goals: int,
    ) -> float:
        return (
            math.exp(-expected_goals)
            * expected_goals**goals
            / math.factorial(goals)
        )
