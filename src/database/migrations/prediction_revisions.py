import sqlite3


def migrate_prediction_revisions_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS prediction_revisions (
            id INTEGER PRIMARY KEY,
            prediction_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            home_probability REAL NOT NULL,
            draw_probability REAL NOT NULL,
            away_probability REAL NOT NULL,
            predicted_result TEXT NOT NULL,
            confidence REAL NOT NULL,
            input_snapshot_json TEXT NOT NULL,
            explanation_json TEXT,
            created_at TEXT NOT NULL,
            replaced_at TEXT NOT NULL,
            FOREIGN KEY(prediction_id) REFERENCES predictions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_prediction_revisions_match_model
        ON prediction_revisions(
            match_id, model_name, model_version, replaced_at DESC, id DESC
        );

        CREATE TRIGGER IF NOT EXISTS prediction_revisions_no_update
        BEFORE UPDATE ON prediction_revisions
        BEGIN
            SELECT RAISE(ABORT, 'prediction revisions are immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS prediction_revisions_no_delete
        BEFORE DELETE ON prediction_revisions
        BEGIN
            SELECT RAISE(ABORT, 'prediction revisions are immutable');
        END;
        """
    )
