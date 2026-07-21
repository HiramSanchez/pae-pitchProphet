import math
import sqlite3

from src.config import (
    DRAW_DECAY_SCALE,
    ELO_HOME_ADVANTAGE,
    MAX_DRAW_PROBABILITY,
    MIN_DRAW_PROBABILITY,
)
from src.models.prediction import (
    PredictedResult,
    Prediction,
    PredictionInput,
    TeamRating,
)
from src.repositories.team_repository import TeamRepository
from src.services.elo_service import expected_score


class TeamNotFoundError(ValueError):
    """Raised when a requested team does not exist."""


class PredictionService:
    def __init__(
        self,
        connection: sqlite3.Connection,
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

        self.team_repository = TeamRepository(connection)
        self.home_advantage = home_advantage
        self.max_draw_probability = max_draw_probability
        self.min_draw_probability = min_draw_probability
        self.draw_decay_scale = draw_decay_scale

    def predict(
        self,
        prediction_input: PredictionInput,
    ) -> Prediction:
        home_team = self._get_team(
            prediction_input.home_team_id
        )
        away_team = self._get_team(
            prediction_input.away_team_id
        )

        return self.predict_from_ratings(
            home_team=home_team,
            away_team=away_team,
        )

    def predict_from_ratings(
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

        predicted_result = max(
            probabilities,
            key=probabilities.get,
        )

        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=home_probability,
            draw_probability=draw_probability,
            away_probability=away_probability,
            predicted_result=predicted_result,
        )

    def _get_team(self, team_id: int) -> TeamRating:
        team = self.team_repository.find_rating_by_id(team_id)

        if team is None:
            raise TeamNotFoundError(
                f"Team with id {team_id} was not found"
            )

        return team

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