import sqlite3

import pytest

from scripts.initialize_database import SCHEMA
from src.database.migrations import (
    migrate_prediction_persistence_schema,
    migrate_user_prediction_journal_schema,
    migrate_user_prediction_model_snapshots_schema,
)


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    migrate_prediction_persistence_schema(connection)
    migrate_user_prediction_journal_schema(connection)
    return connection


def test_snapshot_migration_is_idempotent() -> None:
    connection = _database()

    migrate_user_prediction_model_snapshots_schema(connection)
    migrate_user_prediction_model_snapshots_schema(connection)

    assert connection.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type = 'table'
          AND name = 'user_prediction_model_snapshots'
        """
    ).fetchone()[0] == 1
    indexes = {
        str(row["name"])
        for row in connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'index'
              AND tbl_name = 'user_prediction_model_snapshots'
            """
        )
    }
    assert {
        "idx_user_prediction_snapshots_pick",
        "idx_user_prediction_snapshots_model",
    }.issubset(indexes)


def test_snapshot_schema_enforces_foreign_keys() -> None:
    connection = _database()
    migrate_user_prediction_model_snapshots_schema(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO user_prediction_model_snapshots (
                user_prediction_id, prediction_id,
                model_name, model_version, predicted_result,
                home_probability, draw_probability, away_probability,
                captured_at
            ) VALUES (999, 999, 'elo', '1.0.0', 'HOME',
                      0.5, 0.25, 0.25, '2026-07-27T12:00:00+00:00')
            """
        )
