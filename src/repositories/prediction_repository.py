import json
import sqlite3
from datetime import datetime, timezone

from src.models.prediction import (
    PredictedResult,
    Prediction,
    VersionedPrediction,
)
from src.models.query import PredictionRevision, PredictionView


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

    def update_scheduled(
        self,
        prediction: VersionedPrediction,
    ) -> VersionedPrediction:
        status = self.connection.execute(
            "SELECT status FROM matches WHERE id = ?",
            (prediction.match_id,),
        ).fetchone()
        if status is None or str(status["status"]) != "scheduled":
            raise ValueError("Only scheduled predictions can be refreshed")
        current = self.connection.execute(
            """
            SELECT * FROM predictions
            WHERE match_id = ? AND model_name = ? AND model_version = ?
            """,
            (
                prediction.match_id,
                prediction.model_name,
                prediction.model_version,
            ),
        ).fetchone()
        if current is None:
            raise ValueError("Prediction to refresh was not found")
        snapshot_json = self._serialize(prediction.input_snapshot)
        if str(current["input_snapshot_json"]) == snapshot_json:
            return prediction
        self.connection.execute(
            """
            INSERT INTO prediction_revisions (
                prediction_id, match_id, model_name, model_version,
                home_probability, draw_probability, away_probability,
                predicted_result, confidence, input_snapshot_json,
                explanation_json, created_at, replaced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(current["id"]), int(current["match_id"]),
                str(current["model_name"]), str(current["model_version"]),
                float(current["home_probability"]),
                float(current["draw_probability"]),
                float(current["away_probability"]),
                str(current["predicted_result"]), float(current["confidence"]),
                str(current["input_snapshot_json"]),
                current["explanation_json"], str(current["created_at"]),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.connection.execute(
            """
            UPDATE predictions SET home_probability = ?, draw_probability = ?,
                away_probability = ?, predicted_result = ?, confidence = ?,
                input_snapshot_json = ?, explanation_json = ?, created_at = ?
            WHERE match_id = ? AND model_name = ? AND model_version = ?
            """,
            (
                prediction.prediction.home_probability,
                prediction.prediction.draw_probability,
                prediction.prediction.away_probability,
                prediction.prediction.predicted_result.value,
                prediction.confidence,
                snapshot_json,
                self._serialize(prediction.explanation),
                prediction.created_at,
                prediction.match_id,
                prediction.model_name,
                prediction.model_version,
            ),
        )
        return prediction

    def find_views_by_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[PredictionView]:
        rows = self.connection.execute(
            """
            SELECT p.*, mv.configuration_json,
                m.tournament_id, m.round_number,
                home.name AS home_team_name,
                away.name AS away_team_name
            FROM predictions p
            JOIN model_versions mv ON mv.model_name = p.model_name
                AND mv.model_version = p.model_version
            JOIN matches m ON m.id = p.match_id
            JOIN teams home ON home.id = m.home_team_id
            JOIN teams away ON away.id = m.away_team_id
            WHERE m.tournament_id = ? AND m.round_number = ?
            ORDER BY p.match_id, p.model_name, p.model_version
            """,
            (tournament_id, round_number),
        ).fetchall()
        return [self._view_from_row(row) for row in rows]

    def find_views_by_match(self, match_id: int) -> list[PredictionView]:
        rows = self.connection.execute(
            """
            SELECT p.*, mv.configuration_json,
                m.tournament_id, m.round_number,
                home.name AS home_team_name,
                away.name AS away_team_name
            FROM predictions p
            JOIN model_versions mv ON mv.model_name = p.model_name
                AND mv.model_version = p.model_version
            JOIN matches m ON m.id = p.match_id
            JOIN teams home ON home.id = m.home_team_id
            JOIN teams away ON away.id = m.away_team_id
            WHERE p.match_id = ?
            ORDER BY p.model_name, p.model_version
            """,
            (match_id,),
        ).fetchall()
        return [self._view_from_row(row) for row in rows]

    def find_latest_revisions(
        self,
        tournament_id: int | None = None,
        limit: int = 50,
    ) -> list[PredictionRevision]:
        parameters: list[object] = []
        tournament_filter = ""
        if tournament_id is not None:
            tournament_filter = "WHERE m.tournament_id = ?"
            parameters.append(tournament_id)
        parameters.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT r.* FROM prediction_revisions r
            JOIN matches m ON m.id = r.match_id
            JOIN (
                SELECT prediction_id, MAX(id) AS revision_id
                FROM prediction_revisions GROUP BY prediction_id
            ) latest ON latest.revision_id = r.id
            {tournament_filter}
            ORDER BY r.replaced_at DESC, r.id DESC LIMIT ?
            """,
            parameters,
        ).fetchall()
        return [self._revision_from_row(row) for row in rows]

    def find_view_by_prediction_id(
        self, prediction_id: int
    ) -> PredictionView | None:
        row = self.connection.execute(
            """
            SELECT p.*, mv.configuration_json,
                m.tournament_id, m.round_number,
                home.name AS home_team_name,
                away.name AS away_team_name
            FROM predictions p
            JOIN model_versions mv ON mv.model_name = p.model_name
                AND mv.model_version = p.model_version
            JOIN matches m ON m.id = p.match_id
            JOIN teams home ON home.id = m.home_team_id
            JOIN teams away ON away.id = m.away_team_id
            WHERE p.id = ?
            """,
            (prediction_id,),
        ).fetchone()
        return self._view_from_row(row) if row is not None else None

    @staticmethod
    def _view_from_row(row: sqlite3.Row) -> PredictionView:
        versioned = PredictionRepository._from_row(row)
        return PredictionView(
            prediction_id=int(row["id"]),
            match_id=int(row["match_id"]),
            tournament_id=int(row["tournament_id"]),
            round_number=int(row["round_number"]),
            home_team_name=str(row["home_team_name"]),
            away_team_name=str(row["away_team_name"]),
            model_name=str(row["model_name"]),
            model_version=str(row["model_version"]),
            prediction=versioned.prediction,
            confidence=versioned.confidence,
            explanation=versioned.explanation,
            created_at=versioned.created_at,
        )

    @staticmethod
    def _revision_from_row(row: sqlite3.Row) -> PredictionRevision:
        snapshot = json.loads(str(row["input_snapshot_json"]))
        return PredictionRevision(
            revision_id=int(row["id"]),
            prediction_id=int(row["prediction_id"]),
            match_id=int(row["match_id"]),
            model_name=str(row["model_name"]),
            model_version=str(row["model_version"]),
            prediction=Prediction(
                home_team_id=int(snapshot["home_team"]["team_id"]),
                away_team_id=int(snapshot["away_team"]["team_id"]),
                home_probability=float(row["home_probability"]),
                draw_probability=float(row["draw_probability"]),
                away_probability=float(row["away_probability"]),
                predicted_result=PredictedResult(str(row["predicted_result"])),
            ),
            confidence=float(row["confidence"]),
            input_snapshot=snapshot,
            created_at=str(row["created_at"]),
            replaced_at=str(row["replaced_at"]),
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
        model_output = snapshot.get("model_output")
        if not isinstance(model_output, dict):
            model_output = {}
        likely_score = model_output.get("most_likely_score")
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
                expected_home_goals=PredictionRepository._optional_float(
                    model_output.get("expected_home_goals")
                ),
                expected_away_goals=PredictionRepository._optional_float(
                    model_output.get("expected_away_goals")
                ),
                most_likely_score=(
                    (int(likely_score[0]), int(likely_score[1]))
                    if isinstance(likely_score, list)
                    and len(likely_score) == 2
                    else None
                ),
                score_matrix=(
                    {
                        str(score): float(probability)
                        for score, probability in matrix.items()
                    }
                    if isinstance(
                        matrix := model_output.get("score_matrix"),
                        dict,
                    )
                    else None
                ),
                component_probabilities=(
                    {
                        str(identity): {
                            str(result): float(probability)
                            for result, probability in values.items()
                        }
                        for identity, values in components.items()
                        if isinstance(values, dict)
                    }
                    if isinstance(
                        components := model_output.get(
                            "component_probabilities"
                        ),
                        dict,
                    )
                    else None
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

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if value is not None else None
