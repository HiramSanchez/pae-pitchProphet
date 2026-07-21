import json
import sqlite3

from src.models.prediction import (
    PredictedResult,
    Prediction,
    VersionedPrediction,
)


class PredictionAlreadyExistsError(ValueError):
    """Raised when a versioned prediction already exists."""


class ModelConfigurationMismatchError(ValueError):
    """Raised when a model version has different configuration."""


class PredictionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(
        self,
        versioned_prediction: VersionedPrediction,
    ) -> VersionedPrediction:
        if versioned_prediction.explanation is None:
            raise ValueError(
                "A persisted prediction requires an explanation"
            )

        if self.exists(
            match_id=versioned_prediction.match_id,
            model_name=versioned_prediction.model_name,
            model_version=versioned_prediction.model_version,
        ):
            raise PredictionAlreadyExistsError(
                "Prediction already exists for match "
                f"{versioned_prediction.match_id}, model "
                f"{versioned_prediction.model_name} "
                f"{versioned_prediction.model_version}"
            )

        configuration_json = self._serialize(
            versioned_prediction.configuration
        )
        self._register_model_version(
            model_name=versioned_prediction.model_name,
            model_version=versioned_prediction.model_version,
            configuration_json=configuration_json,
        )

        cursor = self.connection.execute(
            """
            INSERT INTO predictions (
                match_id,
                model_name,
                model_version,
                home_probability,
                draw_probability,
                away_probability,
                predicted_result,
                confidence,
                input_snapshot_json,
                explanation_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                versioned_prediction.match_id,
                versioned_prediction.model_name,
                versioned_prediction.model_version,
                versioned_prediction.prediction.home_probability,
                versioned_prediction.prediction.draw_probability,
                versioned_prediction.prediction.away_probability,
                versioned_prediction.prediction.predicted_result.value,
                versioned_prediction.confidence,
                self._serialize(
                    versioned_prediction.input_snapshot
                ),
                (
                    self._serialize(
                        versioned_prediction.explanation
                    )
                    if versioned_prediction.explanation is not None
                    else None
                ),
                versioned_prediction.created_at,
            ),
        )

        return VersionedPrediction(
            match_id=versioned_prediction.match_id,
            model_name=versioned_prediction.model_name,
            model_version=versioned_prediction.model_version,
            configuration=versioned_prediction.configuration,
            prediction=versioned_prediction.prediction,
            input_snapshot=versioned_prediction.input_snapshot,
            created_at=versioned_prediction.created_at,
            prediction_id=int(cursor.lastrowid),
            explanation=versioned_prediction.explanation,
        )

    def exists(
        self,
        match_id: int,
        model_name: str,
        model_version: str,
    ) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM predictions
            WHERE match_id = ?
              AND model_name = ?
              AND model_version = ?
            """,
            (match_id, model_name, model_version),
        ).fetchone()
        return row is not None

    def find_by_match_and_model(
        self,
        match_id: int,
        model_name: str,
        model_version: str,
    ) -> VersionedPrediction | None:
        row = self.connection.execute(
            """
            SELECT
                p.*,
                mv.configuration_json
            FROM predictions p
            INNER JOIN model_versions mv
                ON mv.model_name = p.model_name
               AND mv.model_version = p.model_version
            WHERE p.match_id = ?
              AND p.model_name = ?
              AND p.model_version = ?
            """,
            (match_id, model_name, model_version),
        ).fetchone()

        return self._from_row(row) if row is not None else None

    def find_by_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[VersionedPrediction]:
        rows = self.connection.execute(
            """
            SELECT
                p.*,
                mv.configuration_json
            FROM predictions p
            INNER JOIN model_versions mv
                ON mv.model_name = p.model_name
               AND mv.model_version = p.model_version
            INNER JOIN matches m
                ON m.id = p.match_id
            WHERE m.tournament_id = ?
              AND m.round_number = ?
            ORDER BY p.match_id, p.model_name, p.model_version
            """,
            (tournament_id, round_number),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_explanation(
        self,
        versioned_prediction: VersionedPrediction,
        explanation: dict[str, object],
    ) -> VersionedPrediction:
        cursor = self.connection.execute(
            """
            UPDATE predictions
            SET explanation_json = ?
            WHERE match_id = ?
              AND model_name = ?
              AND model_version = ?
            """,
            (
                self._serialize(explanation),
                versioned_prediction.match_id,
                versioned_prediction.model_name,
                versioned_prediction.model_version,
            ),
        )

        if cursor.rowcount != 1:
            raise ValueError("Prediction to explain was not found")

        return VersionedPrediction(
            prediction_id=versioned_prediction.prediction_id,
            match_id=versioned_prediction.match_id,
            model_name=versioned_prediction.model_name,
            model_version=versioned_prediction.model_version,
            configuration=versioned_prediction.configuration,
            prediction=versioned_prediction.prediction,
            input_snapshot=versioned_prediction.input_snapshot,
            created_at=versioned_prediction.created_at,
            explanation=explanation,
        )

    def _register_model_version(
        self,
        model_name: str,
        model_version: str,
        configuration_json: str,
    ) -> None:
        row = self.connection.execute(
            """
            SELECT configuration_json
            FROM model_versions
            WHERE model_name = ?
              AND model_version = ?
            """,
            (model_name, model_version),
        ).fetchone()

        if row is None:
            self.connection.execute(
                """
                INSERT INTO model_versions (
                    model_name,
                    model_version,
                    configuration_json
                )
                VALUES (?, ?, ?)
                """,
                (
                    model_name,
                    model_version,
                    configuration_json,
                ),
            )
            return

        if str(row["configuration_json"]) != configuration_json:
            raise ModelConfigurationMismatchError(
                f"Configuration differs for {model_name} "
                f"{model_version}"
            )

    @staticmethod
    def _serialize(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> VersionedPrediction:
        snapshot = json.loads(str(row["input_snapshot_json"]))
        home_team_id = int(snapshot["home_team"]["team_id"])
        away_team_id = int(snapshot["away_team"]["team_id"])
        explanation_json = row["explanation_json"]

        return VersionedPrediction(
            prediction_id=int(row["id"]),
            match_id=int(row["match_id"]),
            model_name=str(row["model_name"]),
            model_version=str(row["model_version"]),
            configuration=json.loads(
                str(row["configuration_json"])
            ),
            prediction=Prediction(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                home_probability=float(row["home_probability"]),
                draw_probability=float(row["draw_probability"]),
                away_probability=float(row["away_probability"]),
                predicted_result=PredictedResult(
                    str(row["predicted_result"])
                ),
            ),
            input_snapshot=snapshot,
            created_at=str(row["created_at"]),
            explanation=(
                json.loads(str(explanation_json))
                if explanation_json is not None
                else None
            ),
        )
