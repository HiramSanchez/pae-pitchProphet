import sqlite3


LEGACY_PREDICTION_COLUMNS = {
    "predictor",
    "predicted_outcome",
    "is_final",
    "points_awarded",
}


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


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


def _legacy_predictions_need_rename(
    connection: sqlite3.Connection,
) -> bool:
    predictions_exists = _table_exists(
        connection,
        "predictions",
    )
    user_predictions_exists = _table_exists(
        connection,
        "user_predictions",
    )

    if not predictions_exists:
        return False

    columns = _column_names(connection, "predictions")
    is_legacy_table = LEGACY_PREDICTION_COLUMNS.issubset(
        columns
    )

    if not is_legacy_table:
        return False

    if user_predictions_exists:
        raise RuntimeError(
            "Cannot migrate legacy predictions because "
            "user_predictions already exists"
        )

    return True


def migrate_prediction_persistence_schema(
    connection: sqlite3.Connection,
) -> None:
    """Preserve human picks and add versioned model predictions.

    Reverting is only safe before model predictions are stored. Once
    populated, restoring a backup is required to avoid data loss.
    """
    rename_legacy_table = _legacy_predictions_need_rename(
        connection
    )
    rename_sql = (
        """
        ALTER TABLE predictions RENAME TO user_predictions;
        DROP INDEX IF EXISTS idx_predictions_predictor;
        """
        if rename_legacy_table
        else ""
    )

    try:
        connection.executescript(
            f"""
        BEGIN IMMEDIATE;
        {rename_sql}

        CREATE TABLE IF NOT EXISTS user_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            predictor TEXT NOT NULL,
            predicted_outcome TEXT NOT NULL
                CHECK(predicted_outcome IN ('home', 'draw', 'away')),
            home_probability REAL,
            draw_probability REAL,
            away_probability REAL,
            is_final INTEGER NOT NULL DEFAULT 1,
            points_awarded INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(match_id, predictor, is_final),
            FOREIGN KEY(match_id) REFERENCES matches(id)
        );

        CREATE TABLE IF NOT EXISTS model_versions (
            id INTEGER PRIMARY KEY,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            configuration_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(model_name, model_version)
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY,
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id),
            UNIQUE(match_id, model_name, model_version)
        );

        CREATE INDEX IF NOT EXISTS idx_user_predictions_predictor
        ON user_predictions(predictor);

        CREATE INDEX IF NOT EXISTS idx_predictions_match_model
        ON predictions(match_id, model_name, model_version);

        COMMIT;
        """
        )
    except Exception:
        connection.rollback()
        raise
