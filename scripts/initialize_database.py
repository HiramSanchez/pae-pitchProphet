from pathlib import Path

from src.config import BACKUP_DIR, DATABASE_PATH
from src.database import database_connection
from src.database.backup import create_backup
from src.database.migrations import (
    migrate_evaluation_persistence_schema,
    migrate_prediction_persistence_schema,
    migrate_prediction_revisions_schema,
    migrate_team_statistics_schema,
    migrate_update_pipeline_schema,
    migrate_user_prediction_journal_schema,
    migrate_user_prediction_model_snapshots_schema,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    season TEXT NOT NULL,
    current_round INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, season)
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    short_name TEXT,
    current_elo REAL NOT NULL DEFAULT 1500,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    importance_rating REAL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, name),
    FOREIGN KEY(team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    match_date TEXT,
    home_goals INTEGER,
    away_goals INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK(status IN ('scheduled', 'completed', 'postponed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(
        tournament_id,
        round_number,
        home_team_id,
        away_team_id
    ),
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(home_team_id) REFERENCES teams(id),
    FOREIGN KEY(away_team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    player_id INTEGER,
    team_id INTEGER NOT NULL,
    minute INTEGER,
    is_penalty INTEGER NOT NULL DEFAULT 0,
    is_own_goal INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id),
    FOREIGN KEY(player_id) REFERENCES players(id),
    FOREIGN KEY(team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS disciplinary_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    player_id INTEGER,
    team_id INTEGER NOT NULL,
    card_type TEXT NOT NULL
        CHECK(card_type IN ('yellow', 'second_yellow', 'red')),
    minute INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id),
    FOREIGN KEY(player_id) REFERENCES players(id),
    FOREIGN KEY(team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS absences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    team_id INTEGER NOT NULL,
    absence_type TEXT NOT NULL
        CHECK(absence_type IN (
            'suspension',
            'injury',
            'personal',
            'other'
        )),
    start_round INTEGER NOT NULL,
    end_round INTEGER,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'completed', 'unconfirmed')),
    impact_rating REAL,
    source_name TEXT,
    source_reliability TEXT
        CHECK(source_reliability IN ('A', 'B', 'C')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(player_id) REFERENCES players(id),
    FOREIGN KEY(team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS elo_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    match_id INTEGER,
    round_number INTEGER NOT NULL,
    elo_before REAL NOT NULL,
    elo_after REAL NOT NULL,
    change_amount REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(team_id) REFERENCES teams(id),
    FOREIGN KEY(match_id) REFERENCES matches(id)
);

CREATE INDEX IF NOT EXISTS idx_matches_round
ON matches(tournament_id, round_number);

CREATE INDEX IF NOT EXISTS idx_players_team
ON players(team_id);

CREATE INDEX IF NOT EXISTS idx_absences_team_status
ON absences(team_id, status);

CREATE INDEX IF NOT EXISTS idx_elo_history_team
ON elo_history(team_id, round_number);
"""


def initialize_database(
    database_path: Path = DATABASE_PATH,
    backup_dir: Path = BACKUP_DIR,
) -> None:
    backup = create_backup(
        database_path,
        backup_dir,
        label="before-migration",
    )
    with database_connection(database_path) as connection:
        connection.executescript(SCHEMA)
        migrate_team_statistics_schema(connection)
        migrate_prediction_persistence_schema(connection)
        migrate_user_prediction_journal_schema(connection)
        migrate_user_prediction_model_snapshots_schema(connection)
        migrate_prediction_revisions_schema(connection)
        migrate_evaluation_persistence_schema(connection)
        migrate_update_pipeline_schema(connection)

    if backup is not None:
        print(f"Respaldo previo guardado en {backup}")
    print("Base de datos inicializada correctamente.")


if __name__ == "__main__":
    initialize_database()
