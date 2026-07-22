import sqlite3


TEAM_STAT_COLUMNS = {
    "matches_played": "INTEGER NOT NULL DEFAULT 0",
    "wins": "INTEGER NOT NULL DEFAULT 0",
    "draws": "INTEGER NOT NULL DEFAULT 0",
    "losses": "INTEGER NOT NULL DEFAULT 0",
    "goals_for": "INTEGER NOT NULL DEFAULT 0",
    "goals_against": "INTEGER NOT NULL DEFAULT 0",
    "goal_difference": "INTEGER NOT NULL DEFAULT 0",
    "points": "INTEGER NOT NULL DEFAULT 0",
    "home_matches": "INTEGER NOT NULL DEFAULT 0",
    "home_wins": "INTEGER NOT NULL DEFAULT 0",
    "home_draws": "INTEGER NOT NULL DEFAULT 0",
    "home_losses": "INTEGER NOT NULL DEFAULT 0",
    "away_matches": "INTEGER NOT NULL DEFAULT 0",
    "away_wins": "INTEGER NOT NULL DEFAULT 0",
    "away_draws": "INTEGER NOT NULL DEFAULT 0",
    "away_losses": "INTEGER NOT NULL DEFAULT 0",
}


def migrate_team_statistics_schema(
    connection: sqlite3.Connection,
) -> list[str]:
    existing = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(teams)")
    }
    added = []
    for name, definition in TEAM_STAT_COLUMNS.items():
        if name not in existing:
            connection.execute(
                f"ALTER TABLE teams ADD COLUMN {name} {definition}"
            )
            added.append(name)
    return added
