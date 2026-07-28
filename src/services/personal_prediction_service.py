import sqlite3

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


class PredictionRoundNotFoundError(LookupError):
    """Raised when a tournament round has no active matches."""


class UserPredictionNotFoundError(LookupError):
    """Raised when a personal prediction does not exist."""


class PersonalPredictionService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        predictor: str = SINGLE_USER_PREDICTOR,
    ) -> None:
        self.connection = connection
        self.predictor = predictor
        self.matches = MatchRepository(connection)
        self.predictions = UserPredictionRepository(connection)

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
        return self.predictions.finalize_round(
            tournament_id, round_number, self.predictor
        )

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
