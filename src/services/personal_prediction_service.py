import json
import logging
import sqlite3
from datetime import datetime, timezone

from src.config import SINGLE_USER_PREDICTOR
from src.models.prediction import PredictedResult
from src.models.user_prediction import (
    UserPickSelection,
    UserPrediction,
    UserPredictionRound,
    UserPredictionRoundStatus,
)
from src.repositories.match_repository import MatchRepository
from src.repositories.user_prediction_repository import (
    UserPredictionRepository,
    UserPredictionRoundStateError,
)
from src.repositories.prediction_repository import PredictionRepository


class PredictionRoundNotFoundError(LookupError):
    """Raised when a tournament round has no active matches."""


class UserPredictionNotFoundError(LookupError):
    """Raised when a personal prediction does not exist."""


class PersonalPredictionService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        predictor: str = SINGLE_USER_PREDICTOR,
        logger: logging.Logger | None = None,
    ) -> None:
        self.connection = connection
        self.predictor = predictor
        self.matches = MatchRepository(connection)
        self.predictions = UserPredictionRepository(connection)
        self.model_predictions = PredictionRepository(connection)
        self.logger = logger or logging.getLogger(
            "pitchprophet.personal_predictions"
        )

    def open_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> UserPredictionRound:
        self._active_match_ids(tournament_id, round_number)
        return self.predictions.open_round(
            tournament_id, round_number, self.predictor
        )

    def save_picks(
        self,
        tournament_id: int,
        round_number: int,
        picks: list[UserPickSelection],
    ) -> list[UserPrediction]:
        journal_round = self.predictions.find_round(
            tournament_id, round_number, self.predictor
        )
        if (
            journal_round is None
            or journal_round.status != UserPredictionRoundStatus.OPEN
        ):
            self._log_conflict(
                "save_picks", tournament_id, round_number
            )
            raise UserPredictionRoundStateError(
                "Personal prediction round is not open"
            )
        match_ids = [pick.match_id for pick in picks]
        if len(match_ids) != len(set(match_ids)):
            raise ValueError("Each match may appear only once")
        active_match_ids = set(
            self._active_match_ids(tournament_id, round_number)
        )
        if not set(match_ids).issubset(active_match_ids):
            raise ValueError(
                "Every pick must belong to an active match in the round"
            )

        self.connection.execute("SAVEPOINT save_personal_picks")
        try:
            for pick in picks:
                self.predictions.save_open_prediction(
                    tournament_id,
                    round_number,
                    self.predictor,
                    pick.match_id,
                    pick.predicted_result,
                )
            self.connection.execute("RELEASE save_personal_picks")
        except Exception:
            self.connection.execute("ROLLBACK TO save_personal_picks")
            self.connection.execute("RELEASE save_personal_picks")
            raise
        return self.predictions.find_by_round(
            tournament_id, round_number, self.predictor
        )

    def update_pick(
        self,
        prediction_id: int,
        predicted_result: PredictedResult,
    ) -> UserPrediction:
        existing = self.predictions.find_prediction_by_id(
            prediction_id, self.predictor
        )
        if existing is None:
            raise UserPredictionNotFoundError(
                "Personal prediction was not found"
            )
        return self.predictions.save_open_prediction(
            existing.tournament_id,
            existing.round_number,
            self.predictor,
            existing.match_id,
            predicted_result,
        )

    def finalize_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> UserPredictionRound:
        expected = set(
            self._active_match_ids(tournament_id, round_number)
        )
        actual = {
            item.match_id
            for item in self.predictions.find_by_round(
                tournament_id, round_number, self.predictor
            )
        }
        if actual != expected:
            missing = len(expected - actual)
            raise ValueError(
                "The prediction round is incomplete: "
                f"{missing} active match picks are missing"
            )
        timestamp = datetime.now(timezone.utc).isoformat()
        self.connection.execute("SAVEPOINT finalize_personal_round")
        try:
            for user_prediction in self.predictions.find_by_round(
                tournament_id, round_number, self.predictor
            ):
                for model_prediction in (
                    self.model_predictions.find_views_by_match(
                        user_prediction.match_id
                    )
                ):
                    self.predictions.save_model_snapshot(
                        user_prediction.prediction_id,
                        model_prediction,
                        timestamp,
                    )
            finalized = self.predictions.finalize_round(
                tournament_id,
                round_number,
                self.predictor,
                timestamp,
            )
            self.connection.execute("RELEASE finalize_personal_round")
            return finalized
        except Exception:
            self.connection.execute("ROLLBACK TO finalize_personal_round")
            self.connection.execute("RELEASE finalize_personal_round")
            self._log_conflict(
                "finalize_round", tournament_id, round_number
            )
            raise

    def _active_match_ids(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[int]:
        match_ids = self.matches.find_active_match_ids_by_round(
            tournament_id, round_number
        )
        if not match_ids:
            raise PredictionRoundNotFoundError(
                "Tournament round has no active matches"
            )
        return match_ids

    def _log_conflict(
        self,
        operation: str,
        tournament_id: int,
        round_number: int,
    ) -> None:
        self.logger.warning(
            json.dumps(
                {
                    "event": "personal_prediction_conflict",
                    "operation": operation,
                    "tournament_id": tournament_id,
                    "round_number": round_number,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
