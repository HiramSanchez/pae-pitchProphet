import json
import sqlite3

import pytest

from scripts.predict_round import display_predictions
from src.database.migrations import (
    migrate_prediction_persistence_schema,
)
from src.models.prediction import PredictedResult
from src.services.prediction_service import PredictionService


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.executescript(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            current_elo REAL NOT NULL
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            status TEXT NOT NULL
        );

        INSERT INTO teams (id, name, current_elo)
        VALUES
            (1, 'Local', 1500.0),
            (2, 'Visitante', 1500.0),
            (3, 'Favorito', 1800.0);

        INSERT INTO matches (
            id,
            tournament_id,
            round_number,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals,
            status
        )
        VALUES
            (1, 1, 2, 1, 2, NULL, NULL, 'scheduled'),
            (2, 1, 2, 2, 3, 1, 0, 'completed'),
            (3, 1, 2, 3, 1, NULL, NULL, 'postponed'),
            (4, 1, 3, 2, 1, NULL, NULL, 'scheduled'),
            (5, 2, 2, 3, 2, NULL, NULL, 'scheduled');
        """
    )
    migrate_prediction_persistence_schema(connection)

    return connection


def test_predict_round_returns_only_scheduled_matches() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    predictions = service.predict_round(
        tournament_id=1,
        round_number=2,
    )

    assert len(predictions) == 1

    match_prediction = predictions[0]
    assert match_prediction.match_id == 1
    assert match_prediction.tournament_id == 1
    assert match_prediction.round_number == 2
    assert match_prediction.home_team_name == "Local"
    assert match_prediction.away_team_name == "Visitante"
    assert (
        match_prediction.prediction.predicted_result
        == PredictedResult.HOME
    )

    connection.close()


def test_predict_round_returns_empty_list_for_empty_round() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    predictions = service.predict_round(
        tournament_id=1,
        round_number=99,
    )

    assert predictions == []

    connection.close()


def test_predict_round_reuses_existing_versioned_prediction() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    first_result = service.predict_round(1, 2)
    second_result = service.predict_round(1, 2)

    stored_count = connection.execute(
        "SELECT COUNT(1) FROM predictions"
    ).fetchone()[0]

    assert stored_count == 1
    assert second_result == first_result

    connection.close()


def test_predict_round_stores_reproducible_snapshot() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    service.predict_round(1, 2)

    row = connection.execute(
        """
        SELECT
            p.model_name,
            p.model_version,
            p.confidence,
            p.input_snapshot_json,
            mv.configuration_json
        FROM predictions p
        INNER JOIN model_versions mv
            ON mv.model_name = p.model_name
           AND mv.model_version = p.model_version
        """
    ).fetchone()
    snapshot = json.loads(row["input_snapshot_json"])
    configuration = json.loads(row["configuration_json"])

    assert row["model_name"] == "elo"
    assert row["model_version"] == "1.0.0"
    assert row["confidence"] > 0
    assert snapshot["home_team"] == {
        "team_id": 1,
        "elo": 1500.0,
    }
    assert snapshot["away_team"] == {
        "team_id": 2,
        "elo": 1500.0,
    }
    assert snapshot["model_configuration"] == configuration
    assert snapshot["generated_at"]

    connection.close()


def test_display_predictions_explains_empty_round(
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_predictions([])

    output = capsys.readouterr().out
    assert "No hay partidos programados" in output
