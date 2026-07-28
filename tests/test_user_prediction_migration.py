import sqlite3

from src.database.migrations import (
    migrate_prediction_persistence_schema,
    migrate_user_prediction_journal_schema,
)


def _legacy_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            season TEXT NOT NULL
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL
        );

        INSERT INTO tournaments VALUES (1, 'Liga MX', 'Apertura 2026');
        INSERT INTO matches VALUES (1, 1, 1);
        """
    )
    migrate_prediction_persistence_schema(connection)
    connection.execute(
        """
        INSERT INTO user_predictions (
            match_id, predictor, predicted_outcome, points_awarded,
            created_at
        )
        VALUES (1, 'Hiram', 'home', 1, '2026-07-21T20:10:07+00:00')
        """
    )
    return connection


def test_journal_migration_preserves_and_backfills_legacy_pick() -> None:
    connection = _legacy_database()

    migrate_user_prediction_journal_schema(connection)

    row = connection.execute(
        """
        SELECT predictor, predicted_outcome, points_awarded,
               created_at, updated_at, evaluated_at
        FROM user_predictions
        """
    ).fetchone()
    assert dict(row) == {
        "predictor": "Hiram",
        "predicted_outcome": "home",
        "points_awarded": 1,
        "created_at": "2026-07-21T20:10:07+00:00",
        "updated_at": "2026-07-21T20:10:07+00:00",
        "evaluated_at": None,
    }
    assert connection.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type = 'table' AND name = 'user_prediction_rounds'
        """
    ).fetchone()[0] == 1


def test_journal_migration_is_idempotent() -> None:
    connection = _legacy_database()

    migrate_user_prediction_journal_schema(connection)
    migrate_user_prediction_journal_schema(connection)

    columns = {
        str(row[1])
        for row in connection.execute(
            "PRAGMA table_info(user_predictions)"
        )
    }
    assert {"updated_at", "evaluated_at"}.issubset(columns)
    assert connection.execute(
        "SELECT COUNT(*) FROM user_predictions"
    ).fetchone()[0] == 1
