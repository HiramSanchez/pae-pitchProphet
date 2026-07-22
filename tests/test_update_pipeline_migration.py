import sqlite3

import pytest

from src.database.migrations import (
    migrate_evaluation_persistence_schema,
    migrate_update_pipeline_schema,
)


def test_update_pipeline_migration_is_idempotent_and_enforces_sources() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("CREATE TABLE matches (id INTEGER PRIMARY KEY)")

    migrate_update_pipeline_schema(connection)
    migrate_update_pipeline_schema(connection)
    connection.execute(
        "INSERT INTO matches (id) VALUES (1)"
    )
    connection.execute(
        "INSERT INTO match_sources VALUES ('source', 'external-1', 1)"
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO match_sources VALUES ('source', 'external-1', 1)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO match_sources VALUES ('source', 'missing', 99)"
        )
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_evaluation_migration_handles_partial_schema_and_legacy_rows() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE model_evaluations (
            id INTEGER PRIMARY KEY, model_name TEXT NOT NULL,
            model_version TEXT NOT NULL, tournament_id INTEGER,
            evaluated_matches INTEGER NOT NULL, log_loss REAL NOT NULL,
            brier_score REAL NOT NULL, accuracy REAL NOT NULL,
            top_two_accuracy REAL NOT NULL, calibration_error REAL,
            evaluated_at TEXT NOT NULL, evaluation_key TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO model_evaluations VALUES
        (1, 'elo', '1.0.0', 1, 1, 0.5, 0.4, 1, 1, 0.1,
         '2026-01-01T00:00:00+00:00', NULL)
        """
    )

    migrate_evaluation_persistence_schema(connection)
    migrate_evaluation_persistence_schema(connection)

    columns = {
        row[1] for row in connection.execute(
            "PRAGMA table_info(model_evaluations)"
        )
    }
    assert {"evaluation_key", "from_round", "to_round"} <= columns
    assert connection.execute(
        "SELECT evaluation_key FROM model_evaluations WHERE id = 1"
    ).fetchone()[0] is None
    connection.execute(
        "UPDATE model_evaluations SET evaluation_key = 'same' WHERE id = 1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO model_evaluations (
                model_name, model_version, tournament_id,
                evaluated_matches, log_loss, brier_score, accuracy,
                top_two_accuracy, calibration_error, evaluated_at,
                evaluation_key
            ) VALUES ('elo', '1.0.0', 1, 1, 0.5, 0.4, 1, 1,
                      0.1, '2026-01-02T00:00:00+00:00', 'same')
            """
        )
