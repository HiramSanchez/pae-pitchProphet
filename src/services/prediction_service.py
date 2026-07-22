import json
import math
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

from src.config import (
    DRAW_DECAY_SCALE,
    ELO_HOME_ADVANTAGE,
    MAX_DRAW_PROBABILITY,
    MIN_DRAW_PROBABILITY,
)
from src.models.match import MatchPrediction, ScheduledMatch
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


class InvalidPredictionError(ValueError):
    """Raised when a model returns invalid probabilities."""


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
        prediction = self.model.predict(
            home_team=home_team,
            away_team=away_team,
        )
        probabilities = (
            prediction.home_probability,
            prediction.draw_probability,
            prediction.away_probability,
        )
        if (
            any(not math.isfinite(value) or not 0 <= value <= 1
                for value in probabilities)
            or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-9)
        ):
            raise InvalidPredictionError(
                f"Model {self.model.name} returned invalid probabilities"
            )
        return prediction

    def predict_round(
        self,
        tournament_id: int,
        round_number: int,
        *,
        refresh_scheduled: bool = False,
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
                if refresh_scheduled:
                    refreshed = self._refresh_if_changed(existing, match)
                    existing = refreshed
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
                home_team = self._get_team_with_features(
                    team_id=match.home_team_id,
                    tournament_id=match.tournament_id,
                    before_round=match.round_number,
                )
                away_team = self._get_team_with_features(
                    team_id=match.away_team_id,
                    tournament_id=match.tournament_id,
                    before_round=match.round_number,
                )
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
                        "home_team": self._team_snapshot(home_team),
                        "away_team": self._team_snapshot(away_team),
                        "model_configuration": (
                            self.model.configuration
                        ),
                        "model_output": self._model_output(
                            prediction
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

    def _refresh_if_changed(
        self,
        existing: VersionedPrediction,
        match: ScheduledMatch,
    ) -> VersionedPrediction:
        home_team = self._get_team_with_features(
            match.home_team_id, match.tournament_id, match.round_number
        )
        away_team = self._get_team_with_features(
            match.away_team_id, match.tournament_id, match.round_number
        )
        prediction = self.predict_from_ratings(home_team, away_team)
        comparable = {
            "home_team": self._team_snapshot(home_team),
            "away_team": self._team_snapshot(away_team),
            "model_configuration": self.model.configuration,
            "model_output": self._model_output(prediction),
        }
        existing_comparable = {
            key: existing.input_snapshot.get(key)
            for key in comparable
        }
        if self._canonical_json(existing_comparable) == self._canonical_json(
            comparable
        ):
            return existing
        generated_at = datetime.now(timezone.utc).isoformat()
        refreshed = VersionedPrediction(
            prediction_id=existing.prediction_id,
            match_id=existing.match_id,
            model_name=existing.model_name,
            model_version=existing.model_version,
            configuration=existing.configuration,
            prediction=prediction,
            input_snapshot={**comparable, "generated_at": generated_at},
            created_at=generated_at,
        )
        refreshed = replace(
            refreshed,
            explanation=self.explanation_service.generate(refreshed),
        )
        return self.prediction_repository.update_scheduled(refreshed)

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _get_team(self, team_id: int) -> TeamRating:
        team = self.team_repository.find_rating_by_id(team_id)

        if team is None:
            raise TeamNotFoundError(
                f"Team with id {team_id} was not found"
            )

        return team

    def _get_team_with_features(
        self,
        team_id: int,
        tournament_id: int,
        before_round: int,
    ) -> TeamRating:
        configuration = self.model.configuration
        team = self.team_repository.find_prediction_features(
            team_id=team_id,
            tournament_id=tournament_id,
            before_round=before_round,
            prior_matches=float(
                configuration.get("prior_matches", 5.0)
            ),
            default_home_goals=float(
                configuration.get(
                    "default_home_goals_average",
                    1.4,
                )
            ),
            default_away_goals=float(
                configuration.get(
                    "default_away_goals_average",
                    1.1,
                )
            ),
        )

        if team is None:
            raise TeamNotFoundError(
                f"Team with id {team_id} was not found"
            )

        return team

    @staticmethod
    def _team_snapshot(team: TeamRating) -> dict[str, object]:
        return {
            "team_id": team.team_id,
            "elo": team.elo,
            "recent_points": team.recent_points,
            "recent_goal_difference": team.recent_goal_difference,
            "home_points_per_match": team.home_points_per_match,
            "away_points_per_match": team.away_points_per_match,
            "home_attack_strength": team.home_attack_strength,
            "home_defense_strength": team.home_defense_strength,
            "away_attack_strength": team.away_attack_strength,
            "away_defense_strength": team.away_defense_strength,
            "league_home_goals_average": (
                team.league_home_goals_average
            ),
            "league_away_goals_average": (
                team.league_away_goals_average
            ),
        }

    @staticmethod
    def _model_output(prediction: Prediction) -> dict[str, object] | None:
        if (
            prediction.expected_home_goals is None
            and prediction.component_probabilities is None
        ):
            return None
        output: dict[str, object] = {}
        if prediction.expected_home_goals is not None:
            output.update(
                {
                    "expected_home_goals": (
                        prediction.expected_home_goals
                    ),
                    "expected_away_goals": (
                        prediction.expected_away_goals
                    ),
                    "most_likely_score": (
                        prediction.most_likely_score
                    ),
                    "score_matrix": prediction.score_matrix,
                }
            )
        if prediction.component_probabilities is not None:
            output["component_probabilities"] = (
                prediction.component_probabilities
            )
        return output
