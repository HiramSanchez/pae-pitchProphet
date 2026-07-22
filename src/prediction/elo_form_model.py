from src.config import (
    DRAW_DECAY_SCALE,
    ELO_HOME_ADVANTAGE,
    MAX_DRAW_PROBABILITY,
    MIN_DRAW_PROBABILITY,
)
from src.models.prediction import Prediction, TeamRating
from src.prediction.elo_model import EloPredictionModel


class EloFormPredictionModel:
    name = "elo_form"
    version = "1.0.0"

    def __init__(
        self,
        home_advantage: float = ELO_HOME_ADVANTAGE,
        max_draw_probability: float = MAX_DRAW_PROBABILITY,
        min_draw_probability: float = MIN_DRAW_PROBABILITY,
        draw_decay_scale: float = DRAW_DECAY_SCALE,
        recent_points_weight: float = 4.0,
        recent_goal_difference_weight: float = 3.0,
        venue_performance_weight: float = 20.0,
    ) -> None:
        weights = {
            "recent_points_weight": recent_points_weight,
            "recent_goal_difference_weight": (
                recent_goal_difference_weight
            ),
            "venue_performance_weight": venue_performance_weight,
        }
        for name, value in weights.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")

        self.elo_model = EloPredictionModel(
            home_advantage=home_advantage,
            max_draw_probability=max_draw_probability,
            min_draw_probability=min_draw_probability,
            draw_decay_scale=draw_decay_scale,
        )
        self.recent_points_weight = recent_points_weight
        self.recent_goal_difference_weight = (
            recent_goal_difference_weight
        )
        self.venue_performance_weight = venue_performance_weight

    @property
    def configuration(self) -> dict[str, float]:
        return {
            **self.elo_model.configuration,
            "recent_points_weight": self.recent_points_weight,
            "recent_goal_difference_weight": (
                self.recent_goal_difference_weight
            ),
            "venue_performance_weight": (
                self.venue_performance_weight
            ),
        }

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        adjusted_home = TeamRating(
            team_id=home_team.team_id,
            name=home_team.name,
            elo=(
                home_team.elo
                + home_team.recent_points
                * self.recent_points_weight
                + home_team.recent_goal_difference
                * self.recent_goal_difference_weight
                + home_team.home_points_per_match
                * self.venue_performance_weight
            ),
        )
        adjusted_away = TeamRating(
            team_id=away_team.team_id,
            name=away_team.name,
            elo=(
                away_team.elo
                + away_team.recent_points
                * self.recent_points_weight
                + away_team.recent_goal_difference
                * self.recent_goal_difference_weight
                + away_team.away_points_per_match
                * self.venue_performance_weight
            ),
        )
        return self.elo_model.predict(adjusted_home, adjusted_away)
