import sqlite3

from src.database.migrations import (
    migrate_prediction_persistence_schema,
)


def create_legacy_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL
        );

        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            predictor TEXT NOT NULL,
            predicted_outcome TEXT NOT NULL,
            home_probability REAL,
            draw_probability REAL,
            away_probability REAL,
            is_final INTEGER NOT NULL DEFAULT 1,
            points_awarded INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(match_id, predictor, is_final),
            FOREIGN KEY(match_id) REFERENCES matches(id)
        );

        CREATE INDEX idx_predictions_predictor
        ON predictions(predictor);

        INSERT INTO matches (id, tournament_id, round_number)
        VALUES (1, 1, 1);

        INSERT INTO predictions (
            match_id,
            predictor,
            predicted_outcome,
            points_awarded
        )
        VALUES (1, 'Hiram', 'home', 1);
        """
    )
    return connection


def test_migration_preserves_human_predictions() -> None:
    connection = create_legacy_database()

    migrate_prediction_persistence_schema(connection)

    human_prediction = connection.execute(
        """
        SELECT match_id, predictor, predicted_outcome, points_awarded
        FROM user_predictions
        """
    ).fetchone()
    model_prediction_columns = {
        str(row[1])
        for row in connection.execute(
            "PRAGMA table_info(predictions)"
        ).fetchall()
    }

    assert dict(human_prediction) == {
        "match_id": 1,
        "predictor": "Hiram",
        "predicted_outcome": "home",
        "points_awarded": 1,
    }
    assert {
        "model_name",
        "model_version",
        "confidence",
        "input_snapshot_json",
    }.issubset(model_prediction_columns)

    connection.close()


def test_migration_is_idempotent() -> None:
    connection = create_legacy_database()

    migrate_prediction_persistence_schema(connection)
    migrate_prediction_persistence_schema(connection)

    human_count = connection.execute(
        "SELECT COUNT(1) FROM user_predictions"
    ).fetchone()[0]
    model_version_table_count = connection.execute(
        """
        SELECT COUNT(1)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'model_versions'
        """
    ).fetchone()[0]

    assert human_count == 1
    assert model_version_table_count == 1

    connection.close()
