import sqlite3

from src.models.evaluation import ModelEvaluation


class EvaluationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(self, evaluation: ModelEvaluation) -> ModelEvaluation:
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        )

    def find_ranking(
        self,
        tournament_id: int | None = None,
    ) -> list[ModelEvaluation]:
        if tournament_id is None:
            rows = self.connection.execute(
                """
                SELECT *
                FROM model_evaluations
                ORDER BY log_loss, brier_score, accuracy DESC, id
                """
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT *
                FROM model_evaluations
                WHERE tournament_id = ?
                ORDER BY log_loss, brier_score, accuracy DESC, id
                """,
                (tournament_id,),
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
        )
