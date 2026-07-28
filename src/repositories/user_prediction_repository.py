import sqlite3
from datetime import datetime, timezone

from src.models.prediction import PredictedResult
from src.models.user_prediction import (
    UserPrediction,
    UserPredictionRound,
    UserPredictionRoundStatus,
)


class UserPredictionRoundStateError(ValueError):
    """Raised when a journal write conflicts with its round state."""


class UserPredictionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_round(
        self,
        tournament_id: int,
        round_number: int,
        predictor: str,
    ) -> UserPredictionRound | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM user_prediction_rounds
            WHERE tournament_id = ?
              AND round_number = ?
              AND predictor = ?
            """,
            (tournament_id, round_number, predictor),
        ).fetchone()
        return self._round_from_row(row) if row is not None else None

    def open_round(
        self,
        tournament_id: int,
        round_number: int,
        predictor: str,
        opened_at: str | None = None,
    ) -> UserPredictionRound:
        timestamp = opened_at or self._now()
        self.connection.execute(
            """
            INSERT INTO user_prediction_rounds (
                tournament_id, round_number, predictor, status,
                opened_at, updated_at
            )
            VALUES (?, ?, ?, 'open', ?, ?)
            ON CONFLICT(tournament_id, round_number, predictor)
            DO NOTHING
            """,
            (
                tournament_id,
                round_number,
                self._validate_predictor(predictor),
                timestamp,
                timestamp,
            ),
        )
        journal_round = self.find_round(
            tournament_id, round_number, predictor
        )
        if journal_round is None:
            raise RuntimeError("Prediction round could not be opened")
        return journal_round

    def find_prediction(
        self,
        match_id: int,
        predictor: str,
    ) -> UserPrediction | None:
        row = self.connection.execute(
            """
            SELECT
                up.id,
                up.match_id,
                m.tournament_id,
                m.round_number,
                up.predictor,
                up.predicted_outcome,
                up.points_awarded,
                up.created_at,
                up.updated_at,
                up.evaluated_at
            FROM user_predictions up
            INNER JOIN matches m ON m.id = up.match_id
            WHERE up.match_id = ?
              AND up.predictor = ?
              AND up.is_final = 1
            """,
            (match_id, predictor),
        ).fetchone()
        return self._prediction_from_row(row) if row is not None else None

    def find_prediction_by_id(
        self,
        prediction_id: int,
        predictor: str,
    ) -> UserPrediction | None:
        row = self.connection.execute(
            """
            SELECT
                up.id,
                up.match_id,
                m.tournament_id,
                m.round_number,
                up.predictor,
                up.predicted_outcome,
                up.points_awarded,
                up.created_at,
                up.updated_at,
                up.evaluated_at
            FROM user_predictions up
            INNER JOIN matches m ON m.id = up.match_id
            WHERE up.id = ?
              AND up.predictor = ?
              AND up.is_final = 1
            """,
            (prediction_id, predictor),
        ).fetchone()
        return self._prediction_from_row(row) if row is not None else None

    def find_by_round(
        self,
        tournament_id: int,
        round_number: int,
        predictor: str,
    ) -> list[UserPrediction]:
        rows = self.connection.execute(
            """
            SELECT
                up.id,
                up.match_id,
                m.tournament_id,
                m.round_number,
                up.predictor,
                up.predicted_outcome,
                up.points_awarded,
                up.created_at,
                up.updated_at,
                up.evaluated_at
            FROM user_predictions up
            INNER JOIN matches m ON m.id = up.match_id
            WHERE m.tournament_id = ?
              AND m.round_number = ?
              AND up.predictor = ?
              AND up.is_final = 1
            ORDER BY up.match_id
            """,
            (tournament_id, round_number, predictor),
        ).fetchall()
        return [self._prediction_from_row(row) for row in rows]

    def find_rounds_for_evaluation(
        self,
        predictor: str,
        tournament_ids: set[int] | None = None,
    ) -> list[UserPredictionRound]:
        parameters: list[object] = [predictor]
        tournament_filter = ""
        if tournament_ids is not None:
            if not tournament_ids:
                return []
            placeholders = ",".join("?" for _ in tournament_ids)
            tournament_filter = (
                f" AND tournament_id IN ({placeholders})"
            )
            parameters.extend(sorted(tournament_ids))
        rows = self.connection.execute(
            f"""
            SELECT *
            FROM user_prediction_rounds
            WHERE predictor = ?
              AND status IN ('finalized', 'evaluated')
              {tournament_filter}
            ORDER BY tournament_id, round_number, id
            """,
            parameters,
        ).fetchall()
        return [self._round_from_row(row) for row in rows]

    def set_prediction_evaluation(
        self,
        prediction_id: int,
        points_awarded: int,
        evaluated_at: str,
    ) -> bool:
        if points_awarded not in {0, 1}:
            raise ValueError("points_awarded must be zero or one")
        current = self.connection.execute(
            """
            SELECT points_awarded, evaluated_at
            FROM user_predictions
            WHERE id = ?
            """,
            (prediction_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Personal prediction was not found")
        if (
            current["points_awarded"] == points_awarded
            and current["evaluated_at"] is not None
        ):
            return False
        self.connection.execute(
            """
            UPDATE user_predictions
            SET points_awarded = ?, evaluated_at = ?
            WHERE id = ?
            """,
            (points_awarded, evaluated_at, prediction_id),
        )
        return True

    def mark_round_evaluated(
        self,
        round_id: int,
        evaluated_at: str,
    ) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE user_prediction_rounds
            SET status = 'evaluated',
                evaluated_at = ?,
                updated_at = ?
            WHERE id = ? AND status = 'finalized'
            """,
            (evaluated_at, evaluated_at, round_id),
        )
        return cursor.rowcount == 1

    def save_open_prediction(
        self,
        tournament_id: int,
        round_number: int,
        predictor: str,
        match_id: int,
        predicted_result: PredictedResult,
        updated_at: str | None = None,
    ) -> UserPrediction:
        journal_round = self.find_round(
            tournament_id, round_number, predictor
        )
        if (
            journal_round is None
            or journal_round.status != UserPredictionRoundStatus.OPEN
        ):
            raise UserPredictionRoundStateError(
                "Personal prediction round is not open"
            )
        match = self.connection.execute(
            """
            SELECT 1
            FROM matches
            WHERE id = ?
              AND tournament_id = ?
              AND round_number = ?
            """,
            (match_id, tournament_id, round_number),
        ).fetchone()
        if match is None:
            raise ValueError(
                "Match does not belong to the prediction round"
            )

        timestamp = updated_at or self._now()
        self.connection.execute(
            """
            INSERT INTO user_predictions (
                match_id, predictor, predicted_outcome, is_final,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(match_id, predictor, is_final)
            DO UPDATE SET
                predicted_outcome = excluded.predicted_outcome,
                updated_at = excluded.updated_at,
                points_awarded = NULL,
                evaluated_at = NULL
            """,
            (
                match_id,
                predictor,
                predicted_result.value.lower(),
                timestamp,
                timestamp,
            ),
        )
        prediction = self.find_prediction(match_id, predictor)
        if prediction is None:
            raise RuntimeError("Personal prediction could not be saved")
        return prediction

    def finalize_round(
        self,
        tournament_id: int,
        round_number: int,
        predictor: str,
        finalized_at: str | None = None,
    ) -> UserPredictionRound:
        journal_round = self.find_round(
            tournament_id, round_number, predictor
        )
        if journal_round is None:
            raise UserPredictionRoundStateError(
                "Personal prediction round was not opened"
            )
        if journal_round.status == UserPredictionRoundStatus.FINALIZED:
            return journal_round
        if journal_round.status != UserPredictionRoundStatus.OPEN:
            raise UserPredictionRoundStateError(
                "Only an open prediction round can be finalized"
            )

        timestamp = finalized_at or self._now()
        self.connection.execute(
            """
            UPDATE user_prediction_rounds
            SET status = 'finalized',
                finalized_at = ?,
                updated_at = ?
            WHERE id = ? AND status = 'open'
            """,
            (timestamp, timestamp, journal_round.round_id),
        )
        finalized = self.find_round(
            tournament_id, round_number, predictor
        )
        if finalized is None:
            raise RuntimeError("Prediction round could not be finalized")
        return finalized

    @staticmethod
    def _round_from_row(row: sqlite3.Row) -> UserPredictionRound:
        return UserPredictionRound(
            round_id=int(row["id"]),
            tournament_id=int(row["tournament_id"]),
            round_number=int(row["round_number"]),
            predictor=str(row["predictor"]),
            status=UserPredictionRoundStatus(str(row["status"])),
            opened_at=str(row["opened_at"]),
            finalized_at=(
                str(row["finalized_at"])
                if row["finalized_at"] is not None
                else None
            ),
            evaluated_at=(
                str(row["evaluated_at"])
                if row["evaluated_at"] is not None
                else None
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _prediction_from_row(row: sqlite3.Row) -> UserPrediction:
        return UserPrediction(
            prediction_id=int(row["id"]),
            match_id=int(row["match_id"]),
            tournament_id=int(row["tournament_id"]),
            round_number=int(row["round_number"]),
            predictor=str(row["predictor"]),
            predicted_result=PredictedResult(
                str(row["predicted_outcome"]).upper()
            ),
            points_awarded=(
                int(row["points_awarded"])
                if row["points_awarded"] is not None
                else None
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            evaluated_at=(
                str(row["evaluated_at"])
                if row["evaluated_at"] is not None
                else None
            ),
        )

    @staticmethod
    def _validate_predictor(predictor: str) -> str:
        normalized = predictor.strip()
        if not normalized:
            raise ValueError("predictor is required")
        return normalized

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
