import sqlite3


def migrate_evaluation_persistence_schema(
    connection: sqlite3.Connection,
) -> None:
    try:
        connection.executescript(
            """
            BEGIN IMMEDIATE;

            CREATE TABLE IF NOT EXISTS model_evaluations (
                id INTEGER PRIMARY KEY,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                tournament_id INTEGER,
                evaluated_matches INTEGER NOT NULL,
                log_loss REAL NOT NULL,
                brier_score REAL NOT NULL,
                accuracy REAL NOT NULL,
                top_two_accuracy REAL NOT NULL,
                calibration_error REAL,
                evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_model_evaluations_ranking
            ON model_evaluations(log_loss, brier_score, accuracy);

            COMMIT;
            """
        )
    except Exception:
        connection.rollback()
        raise
