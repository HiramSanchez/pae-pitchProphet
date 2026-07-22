import math

from src.config import (
    DRAW_DECAY_SCALE,
    ELO_HOME_ADVANTAGE,
    MAX_DRAW_PROBABILITY,
    MIN_DRAW_PROBABILITY,
)
from src.models.elo import expected_score
from src.models.prediction import (
    PredictedResult,
    Prediction,
    TeamRating,
)


class EloPredictionModel:
    name = "elo"
    version = "1.0.0"

    def __init__(
        self,
        home_advantage: float = ELO_HOME_ADVANTAGE,
        max_draw_probability: float = MAX_DRAW_PROBABILITY,
        min_draw_probability: float = MIN_DRAW_PROBABILITY,
        draw_decay_scale: float = DRAW_DECAY_SCALE,
    ) -> None:
        if home_advantage < 0:
            raise ValueError(
                "home_advantage cannot be negative"
            )

        if not 0 <= min_draw_probability <= 1:
            raise ValueError(
                "min_draw_probability must be between 0 and 1"
            )

        if not 0 <= max_draw_probability <= 1:
            raise ValueError(
                "max_draw_probability must be between 0 and 1"
            )

        if min_draw_probability > max_draw_probability:
            raise ValueError(
                "min_draw_probability cannot exceed "
                "max_draw_probability"
            )

        if draw_decay_scale <= 0:
            raise ValueError(
                "draw_decay_scale must be positive"
            )

        self.home_advantage = home_advantage
        self.max_draw_probability = max_draw_probability
        self.min_draw_probability = min_draw_probability
        self.draw_decay_scale = draw_decay_scale

    @property
    def configuration(self) -> dict[str, float]:
        return {
            "home_advantage": self.home_advantage,
            "max_draw_probability": self.max_draw_probability,
            "min_draw_probability": self.min_draw_probability,
            "draw_decay_scale": self.draw_decay_scale,
        }

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        adjusted_home_elo = (
            home_team.elo + self.home_advantage
        )

        home_expected_score = expected_score(
            adjusted_home_elo,
            away_team.elo,
        )

        draw_probability = self._calculate_draw_probability(
            adjusted_home_elo=adjusted_home_elo,
            away_elo=away_team.elo,
        )

        decisive_probability = 1.0 - draw_probability
        home_probability = (
            home_expected_score * decisive_probability
        )
        away_probability = (
            (1.0 - home_expected_score)
            * decisive_probability
        )

        probabilities = {
            PredictedResult.HOME: home_probability,
            PredictedResult.DRAW: draw_probability,
            PredictedResult.AWAY: away_probability,
        }

        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=home_probability,
            draw_probability=draw_probability,
            away_probability=away_probability,
            predicted_result=max(
                probabilities,
                key=probabilities.get,
            ),
        )

    def _calculate_draw_probability(
        self,
        adjusted_home_elo: float,
        away_elo: float,
    ) -> float:
        elo_difference = abs(
            adjusted_home_elo - away_elo
        )
        dynamic_draw_probability = (
            self.max_draw_probability
            * math.exp(
                -elo_difference / self.draw_decay_scale
            )
        )

        return max(
            self.min_draw_probability,
            dynamic_draw_probability,
        )
