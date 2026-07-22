import sqlite3


EVALUATION_COLUMNS = {
    "evaluation_key": "TEXT",
    "from_round": "INTEGER",
    "to_round": "INTEGER",
}


def _column_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            "PRAGMA table_info(model_evaluations)"
        ).fetchall()
    }


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

            DROP INDEX IF EXISTS idx_model_evaluations_ranking;

            CREATE INDEX idx_model_evaluations_ranking
            ON model_evaluations(
                log_loss,
                calibration_error,
                brier_score,
                accuracy
            );

            COMMIT;
            """
        )
        existing = _column_names(connection)
        for name, sql_type in EVALUATION_COLUMNS.items():
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE model_evaluations "
                    f"ADD COLUMN {name} {sql_type}"
                )
        connection.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_model_evaluations_key
            ON model_evaluations(evaluation_key)
            WHERE evaluation_key IS NOT NULL;

            CREATE INDEX IF NOT EXISTS
            idx_model_evaluations_latest
            ON model_evaluations(
                model_name,
                model_version,
                tournament_id,
                evaluated_at DESC,
                id DESC
            );
            """
        )
    except Exception:
        connection.rollback()
        raise
