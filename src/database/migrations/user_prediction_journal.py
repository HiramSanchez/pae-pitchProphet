import sqlite3


USER_PREDICTION_COLUMNS = {
    "updated_at": "TEXT",
    "evaluated_at": "TEXT",
}


def _column_names(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def migrate_user_prediction_journal_schema(
    connection: sqlite3.Connection,
) -> None:
    existing = _column_names(connection, "user_predictions")
    if not existing:
        raise RuntimeError(
            "user_predictions must exist before journal migration"
        )

    try:
        for name, sql_type in USER_PREDICTION_COLUMNS.items():
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE user_predictions "
                    f"ADD COLUMN {name} {sql_type}"
                )

        connection.execute(
            """
            UPDATE user_predictions
            SET updated_at = created_at
            WHERE updated_at IS NULL
            """
        )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_prediction_rounds (
                id INTEGER PRIMARY KEY,
                tournament_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                predictor TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('open', 'finalized', 'evaluated')),
                opened_at TEXT NOT NULL,
                finalized_at TEXT,
                evaluated_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
                UNIQUE(tournament_id, round_number, predictor)
            );

            CREATE INDEX IF NOT EXISTS
            idx_user_prediction_rounds_status
            ON user_prediction_rounds(
                predictor, status, tournament_id, round_number
            );

            CREATE INDEX IF NOT EXISTS
            idx_user_predictions_owner_match
            ON user_predictions(predictor, match_id);
            """
        )
    except Exception:
        connection.rollback()
        raise
