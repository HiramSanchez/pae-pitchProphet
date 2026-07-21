import sqlite3

from src.config import (
    DRAW_DECAY_SCALE,
    ELO_HOME_ADVANTAGE,
    MAX_DRAW_PROBABILITY,
    MIN_DRAW_PROBABILITY,
)
from src.models.match import MatchPrediction
from src.models.prediction import Prediction, PredictionInput, TeamRating
from src.prediction.base import PredictionModel
from src.prediction.elo_model import EloPredictionModel
from src.repositories.match_repository import MatchRepository
from src.repositories.team_repository import TeamRepository


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
        *,
        model: PredictionModel | None = None,
    ) -> None:
        self.match_repository = MatchRepository(connection)
        self.team_repository = TeamRepository(connection)
        self.model = (
            model
            if model is not None
            else EloPredictionModel(
                home_advantage=home_advantage,
                max_draw_probability=max_draw_probability,
                min_draw_probability=min_draw_probability,
                draw_decay_scale=draw_decay_scale,
            )
        )

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
        return self.model.predict(
            home_team=home_team,
            away_team=away_team,
        )

    def predict_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[MatchPrediction]:
        scheduled_matches = (
            self.match_repository.find_scheduled_by_round(
                tournament_id=tournament_id,
                round_number=round_number,
            )
        )

        predictions: list[MatchPrediction] = []

        for match in scheduled_matches:
            prediction = self.predict(
                PredictionInput(
                    home_team_id=match.home_team_id,
                    away_team_id=match.away_team_id,
                )
            )
            predictions.append(
                MatchPrediction(
                    match_id=match.match_id,
                    tournament_id=match.tournament_id,
                    round_number=match.round_number,
                    home_team_name=match.home_team_name,
                    away_team_name=match.away_team_name,
                    prediction=prediction,
                )
            )

        return predictions

    def _get_team(self, team_id: int) -> TeamRating:
        team = self.team_repository.find_rating_by_id(team_id)

        if team is None:
            raise TeamNotFoundError(
                f"Team with id {team_id} was not found"
            )

        return team
