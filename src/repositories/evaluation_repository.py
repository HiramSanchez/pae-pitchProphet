import sqlite3

from src.models.evaluation import ModelEvaluation


class EvaluationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(self, evaluation: ModelEvaluation) -> ModelEvaluation:
        if evaluation.evaluation_key is not None:
            existing = self.find_by_key(evaluation.evaluation_key)
            if existing is not None:
                return existing
        cursor = self.connection.execute(
            """
            INSERT INTO model_evaluations (
                model_name,
                model_version,
                tournament_id,
                evaluated_matches,
                log_loss,
                brier_score,
                accuracy,
                top_two_accuracy,
                calibration_error,
                evaluated_at
                ,evaluation_key, from_round, to_round
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation.model_name,
                evaluation.model_version,
                evaluation.tournament_id,
                evaluation.evaluated_matches,
                evaluation.log_loss,
                evaluation.brier_score,
                evaluation.accuracy,
                evaluation.top_two_accuracy,
                evaluation.calibration_error,
                evaluation.evaluated_at,
                evaluation.evaluation_key,
                evaluation.from_round,
                evaluation.to_round,
            ),
        )
        return ModelEvaluation(
            model_name=evaluation.model_name,
            model_version=evaluation.model_version,
            tournament_id=evaluation.tournament_id,
            evaluated_matches=evaluation.evaluated_matches,
            log_loss=evaluation.log_loss,
            brier_score=evaluation.brier_score,
            accuracy=evaluation.accuracy,
            top_two_accuracy=evaluation.top_two_accuracy,
            calibration_error=evaluation.calibration_error,
            confusion_matrix=evaluation.confusion_matrix,
            evaluated_at=evaluation.evaluated_at,
            evaluation_id=int(cursor.lastrowid),
            evaluation_key=evaluation.evaluation_key,
            from_round=evaluation.from_round,
            to_round=evaluation.to_round,
        )

    def find_by_key(self, evaluation_key: str) -> ModelEvaluation | None:
        row = self.connection.execute(
            "SELECT * FROM model_evaluations WHERE evaluation_key = ?",
            (evaluation_key,),
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def find_latest_by_model(
        self,
        model_name: str,
        model_version: str,
        tournament_id: int,
    ) -> ModelEvaluation | None:
        row = self.connection.execute(
            """
            SELECT * FROM model_evaluations
            WHERE model_name = ? AND model_version = ?
              AND tournament_id = ?
            ORDER BY evaluated_at DESC, id DESC
            LIMIT 1
            """,
            (model_name, model_version, tournament_id),
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def find_ranking(
        self,
        tournament_id: int | None = None,
    ) -> list[ModelEvaluation]:
        if tournament_id is None:
            rows = self.connection.execute(
                """
                SELECT *
                FROM model_evaluations
                ORDER BY
                    log_loss,
                    calibration_error,
                    brier_score,
                    accuracy DESC,
                    id
                """
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT *
                FROM model_evaluations
                WHERE tournament_id = ?
                ORDER BY
                    log_loss,
                    calibration_error,
                    brier_score,
                    accuracy DESC,
                    id
                """,
                (tournament_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_latest_for_tournament(
        self, tournament_id: int
    ) -> list[ModelEvaluation]:
        rows = self.connection.execute(
            """
            SELECT * FROM (
                SELECT model_evaluations.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY model_name, model_version
                        ORDER BY evaluated_at DESC, id DESC
                    ) AS position
                FROM model_evaluations WHERE tournament_id = ?
            ) WHERE position = 1
            ORDER BY log_loss, calibration_error, brier_score,
                accuracy DESC, id
            """,
            (tournament_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_recent_by_model(
        self,
        model_name: str,
        model_version: str,
        tournament_id: int,
        limit: int,
    ) -> list[ModelEvaluation]:
        rows = self.connection.execute(
            """
            SELECT * FROM model_evaluations
            WHERE model_name = ? AND model_version = ?
              AND tournament_id = ?
            ORDER BY evaluated_at DESC, id DESC LIMIT ?
            """,
            (model_name, model_version, tournament_id, limit),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ModelEvaluation:
        return ModelEvaluation(
            evaluation_id=int(row["id"]),
            model_name=str(row["model_name"]),
            model_version=str(row["model_version"]),
            tournament_id=(
                int(row["tournament_id"])
                if row["tournament_id"] is not None
                else None
            ),
            evaluated_matches=int(row["evaluated_matches"]),
            log_loss=float(row["log_loss"]),
            brier_score=float(row["brier_score"]),
            accuracy=float(row["accuracy"]),
            top_two_accuracy=float(row["top_two_accuracy"]),
            calibration_error=float(row["calibration_error"]),
            confusion_matrix={},
            evaluated_at=str(row["evaluated_at"]),
            evaluation_key=(
                str(row["evaluation_key"])
                if "evaluation_key" in row.keys()
                and row["evaluation_key"] is not None
                else None
            ),
            from_round=(
                int(row["from_round"])
                if "from_round" in row.keys()
                and row["from_round"] is not None
                else None
            ),
            to_round=(
                int(row["to_round"])
                if "to_round" in row.keys()
                and row["to_round"] is not None
                else None
            ),
        )
