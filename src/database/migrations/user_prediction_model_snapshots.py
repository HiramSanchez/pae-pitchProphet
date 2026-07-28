import sqlite3


def migrate_user_prediction_model_snapshots_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_prediction_model_snapshots (
            id INTEGER PRIMARY KEY,
            user_prediction_id INTEGER NOT NULL,
            prediction_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            predicted_result TEXT NOT NULL
                CHECK(predicted_result IN ('HOME', 'DRAW', 'AWAY')),
            home_probability REAL NOT NULL,
            draw_probability REAL NOT NULL,
            away_probability REAL NOT NULL,
            captured_at TEXT NOT NULL,
            FOREIGN KEY(user_prediction_id) REFERENCES user_predictions(id),
            FOREIGN KEY(prediction_id) REFERENCES predictions(id),
            UNIQUE(user_prediction_id, model_name, model_version)
        );

        CREATE INDEX IF NOT EXISTS idx_user_prediction_snapshots_pick
        ON user_prediction_model_snapshots(user_prediction_id);

        CREATE INDEX IF NOT EXISTS idx_user_prediction_snapshots_model
        ON user_prediction_model_snapshots(model_name, model_version);
        """
    )
