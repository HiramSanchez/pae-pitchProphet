import sqlite3

from src.database import database_connection
from src.services.elo_service import update_elo


def get_completed_unprocessed_matches(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            m.id,
            m.round_number,
            m.home_goals,
            m.away_goals,
            home.id AS home_team_id,
            home.name AS home_team_name,
            home.current_elo AS home_elo,
            away.id AS away_team_id,
            away.name AS away_team_name,
            away.current_elo AS away_elo
        FROM matches m
        INNER JOIN teams home
            ON home.id = m.home_team_id
        INNER JOIN teams away
            ON away.id = m.away_team_id
        WHERE m.status = 'completed'
          AND m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM elo_history history
              WHERE history.match_id = m.id
          )
        ORDER BY
            m.round_number,
            m.id
        """
    ).fetchall()


def update_team_rating(
    connection: sqlite3.Connection,
    team_id: int,
    new_elo: float,
) -> None:
    connection.execute(
        """
        UPDATE teams
        SET current_elo = ?
        WHERE id = ?
        """,
        (
            new_elo,
            team_id,
        ),
    )


def insert_elo_history(
    connection: sqlite3.Connection,
    team_id: int,
    match_id: int,
    round_number: int,
    elo_before: float,
    elo_after: float,
) -> None:
    connection.execute(
        """
        INSERT INTO elo_history (
            team_id,
            match_id,
            round_number,
            elo_before,
            elo_after,
            change_amount
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            team_id,
            match_id,
            round_number,
            elo_before,
            elo_after,
            elo_after - elo_before,
        ),
    )


def process_match(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
) -> None:
    home_elo = float(match["home_elo"])
    away_elo = float(match["away_elo"])

    result = update_elo(
        home_elo=home_elo,
        away_elo=away_elo,
        home_goals=int(match["home_goals"]),
        away_goals=int(match["away_goals"]),
    )

    update_team_rating(
        connection=connection,
        team_id=int(match["home_team_id"]),
        new_elo=result.home_elo_after,
    )

    update_team_rating(
        connection=connection,
        team_id=int(match["away_team_id"]),
        new_elo=result.away_elo_after,
    )

    insert_elo_history(
        connection=connection,
        team_id=int(match["home_team_id"]),
        match_id=int(match["id"]),
        round_number=int(match["round_number"]),
        elo_before=result.home_elo_before,
        elo_after=result.home_elo_after,
    )

    insert_elo_history(
        connection=connection,
        team_id=int(match["away_team_id"]),
        match_id=int(match["id"]),
        round_number=int(match["round_number"]),
        elo_before=result.away_elo_before,
        elo_after=result.away_elo_after,
    )

    print(
        f"{match['home_team_name']} "
        f"{match['home_goals']}-{match['away_goals']} "
        f"{match['away_team_name']}"
    )

    print(
        f"  {match['home_team_name']}: "
        f"{result.home_elo_before:.2f} → "
        f"{result.home_elo_after:.2f} "
        f"({result.home_change:+.2f})"
    )

    print(
        f"  {match['away_team_name']}: "
        f"{result.away_elo_before:.2f} → "
        f"{result.away_elo_after:.2f} "
        f"({result.away_change:+.2f})"
    )


def process_results() -> None:
    with database_connection() as connection:
        matches = get_completed_unprocessed_matches(connection)

        if not matches:
            print("No existen partidos pendientes de procesar.")
            return

        for match in matches:
            process_match(connection, match)

    print()
    print(f"Partidos procesados correctamente: {len(matches)}")


if __name__ == "__main__":
    process_results()