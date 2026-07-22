import sqlite3


def migrate_update_pipeline_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS match_sources (
            source_name TEXT NOT NULL,
            external_match_id TEXT NOT NULL,
            match_id INTEGER NOT NULL,
            PRIMARY KEY(source_name, external_match_id),
            FOREIGN KEY(match_id) REFERENCES matches(id)
        );

        CREATE INDEX IF NOT EXISTS idx_match_sources_match
        ON match_sources(match_id);

        CREATE TABLE IF NOT EXISTS update_runs (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL
                CHECK(status IN ('running', 'succeeded', 'failed')),
            matches_added INTEGER NOT NULL DEFAULT 0,
            matches_updated INTEGER NOT NULL DEFAULT 0,
            predictions_generated INTEGER NOT NULL DEFAULT 0,
            message TEXT,
            error_message TEXT
        );
        """
    )
