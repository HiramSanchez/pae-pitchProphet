import sqlite3

import pytest

from src.database.migrations import (
    migrate_prediction_persistence_schema,
    migrate_prediction_revisions_schema,
)


def test_revision_migration_is_idempotent_and_rows_are_immutable() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "CREATE TABLE matches (id INTEGER PRIMARY KEY)"
    )
    migrate_prediction_persistence_schema(connection)
    migrate_prediction_revisions_schema(connection)
    migrate_prediction_revisions_schema(connection)
    connection.execute("INSERT INTO matches VALUES (1)")
    connection.execute(
        """
        INSERT INTO predictions (
            id, match_id, model_name, model_version, home_probability,
            draw_probability, away_probability, predicted_result,
            confidence, input_snapshot_json, created_at
        ) VALUES (1, 1, 'elo', '1.0.0', .5, .3, .2, 'HOME', .5,
                  '{}', '2026-01-01T00:00:00+00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO prediction_revisions (
            prediction_id, match_id, model_name, model_version,
            home_probability, draw_probability, away_probability,
            predicted_result, confidence, input_snapshot_json,
            created_at, replaced_at
        ) VALUES (1, 1, 'elo', '1.0.0', .5, .3, .2, 'HOME', .5,
                  '{}', '2026-01-01T00:00:00+00:00',
                  '2026-01-02T00:00:00+00:00')
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            "UPDATE prediction_revisions SET confidence = .6"
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute("DELETE FROM prediction_revisions")

