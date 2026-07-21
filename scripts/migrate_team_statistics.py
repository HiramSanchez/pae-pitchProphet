import sqlite3
from dataclasses import dataclass

from src.database import database_connection


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    sql_type: str
    default_value: str


TEAM_STAT_COLUMNS = [
    ColumnDefinition("matches_played", "INTEGER", "0"),
    ColumnDefinition("wins", "INTEGER", "0"),
    ColumnDefinition("draws", "INTEGER", "0"),
    ColumnDefinition("losses", "INTEGER", "0"),
    ColumnDefinition("goals_for", "INTEGER", "0"),
    ColumnDefinition("goals_against", "INTEGER", "0"),
    ColumnDefinition("goal_difference", "INTEGER", "0"),
    ColumnDefinition("points", "INTEGER", "0"),
    ColumnDefinition("home_matches", "INTEGER", "0"),
    ColumnDefinition("home_wins", "INTEGER", "0"),
    ColumnDefinition("home_draws", "INTEGER", "0"),
    ColumnDefinition("home_losses", "INTEGER", "0"),
    ColumnDefinition("away_matches", "INTEGER", "0"),
    ColumnDefinition("away_wins", "INTEGER", "0"),
    ColumnDefinition("away_draws", "INTEGER", "0"),
    ColumnDefinition("away_losses", "INTEGER", "0"),
]


def get_existing_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        str(row["name"])
        for row in rows
    }


def add_missing_team_columns(
    connection: sqlite3.Connection,
) -> list[str]:
    existing_columns = get_existing_columns(
        connection=connection,
        table_name="teams",
    )

    added_columns: list[str] = []

    for column in TEAM_STAT_COLUMNS:
        if column.name in existing_columns:
            continue

        connection.execute(
            f"""
            ALTER TABLE teams
            ADD COLUMN {column.name}
            {column.sql_type}
            NOT NULL
            DEFAULT {column.default_value}
            """
        )

        added_columns.append(column.name)

    return added_columns


def migrate_team_statistics() -> None:
    with database_connection() as connection:
        added_columns = add_missing_team_columns(connection)

    if not added_columns:
        print("La migración ya había sido aplicada.")
        return

    print("Migración aplicada correctamente.")
    print(f"Columnas agregadas: {len(added_columns)}")

    for column_name in added_columns:
        print(f"  - {column_name}")


if __name__ == "__main__":
    migrate_team_statistics()