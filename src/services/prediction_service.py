import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

from src.config import (
    DRAW_DECAY_SCALE,
    ELO_HOME_ADVANTAGE,
    MAX_DRAW_PROBABILITY,
    MIN_DRAW_PROBABILITY,
)
from src.models.match import MatchPrediction
from src.models.prediction import (
    Prediction,
    PredictionInput,
    TeamRating,
    VersionedPrediction,
)
from src.prediction.base import PredictionModel
from src.prediction.elo_model import EloPredictionModel
from src.repositories.match_repository import MatchRepository
from src.repositories.prediction_repository import (
    ModelConfigurationMismatchError,
    PredictionRepository,
)
from src.repositories.team_repository import TeamRepository
from src.services.explanation_service import ExplanationService


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
        self.prediction_repository = PredictionRepository(connection)
        self.team_repository = TeamRepository(connection)
        self.explanation_service = ExplanationService()
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
            existing = (
                self.prediction_repository.find_by_match_and_model(
                    match_id=match.match_id,
                    model_name=self.model.name,
                    model_version=self.model.version,
                )
            )

            if existing is not None:
                if existing.configuration != self.model.configuration:
                    raise ModelConfigurationMismatchError(
                        "Stored configuration differs for "
                        f"{self.model.name} {self.model.version}"
                    )
                if existing.explanation is None:
                    explanation = self.explanation_service.generate(
                        existing
                    )
                    existing = (
                        self.prediction_repository.update_explanation(
                            existing,
                            explanation,
                        )
                    )
                versioned_prediction = existing
            else:
                home_team = self._get_team(match.home_team_id)
                away_team = self._get_team(match.away_team_id)
                prediction = self.predict_from_ratings(
                    home_team=home_team,
                    away_team=away_team,
                )
                generated_at = datetime.now(timezone.utc).isoformat()
                versioned_prediction = VersionedPrediction(
                    match_id=match.match_id,
                    model_name=self.model.name,
                    model_version=self.model.version,
                    configuration=self.model.configuration,
                    prediction=prediction,
                    input_snapshot={
                        "home_team": {
                            "team_id": home_team.team_id,
                            "elo": home_team.elo,
                        },
                        "away_team": {
                            "team_id": away_team.team_id,
                            "elo": away_team.elo,
                        },
                        "model_configuration": (
                            self.model.configuration
                        ),
                        "generated_at": generated_at,
                    },
                    created_at=generated_at,
                )
                versioned_prediction = replace(
                    versioned_prediction,
                    explanation=self.explanation_service.generate(
                        versioned_prediction
                    ),
                )
                versioned_prediction = self.prediction_repository.save(
                    versioned_prediction
                )

            prediction = versioned_prediction.prediction
            predictions.append(
                MatchPrediction(
                    match_id=match.match_id,
                    tournament_id=match.tournament_id,
                    round_number=match.round_number,
                    home_team_name=match.home_team_name,
                    away_team_name=match.away_team_name,
                    prediction=prediction,
                    explanation=versioned_prediction.explanation,
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
