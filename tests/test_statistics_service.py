import sqlite3

from src.repositories.team_repository import TeamRepository
from src.services.statistics_service import StatisticsService


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.executescript(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            current_elo REAL NOT NULL DEFAULT 1500,
            matches_played INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            goals_for INTEGER NOT NULL DEFAULT 0,
            goals_against INTEGER NOT NULL DEFAULT 0,
            goal_difference INTEGER NOT NULL DEFAULT 0,
            points INTEGER NOT NULL DEFAULT 0,
            home_matches INTEGER NOT NULL DEFAULT 0,
            home_wins INTEGER NOT NULL DEFAULT 0,
            home_draws INTEGER NOT NULL DEFAULT 0,
            home_losses INTEGER NOT NULL DEFAULT 0,
            away_matches INTEGER NOT NULL DEFAULT 0,
            away_wins INTEGER NOT NULL DEFAULT 0,
            away_draws INTEGER NOT NULL DEFAULT 0,
            away_losses INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            status TEXT NOT NULL
        );
        """
    )

    connection.executemany(
        """
        INSERT INTO teams (id, name)
        VALUES (?, ?)
        """,
        [
            (1, "Equipo A"),
            (2, "Equipo B"),
            (3, "Equipo C"),
        ],
    )

    return connection


def test_home_win_updates_statistics() -> None:
    connection = create_test_database()

    connection.execute(
        """
        INSERT INTO matches (
            id,
            tournament_id,
            round_number,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals,
            status
        )
        VALUES (1, 1, 1, 1, 2, 2, 0, 'completed')
        """
    )

    service = StatisticsService(connection)
    service.recalculate_all()

    repository = TeamRepository(connection)
    teams = repository.find_all_ordered_by_standings()

    teams_by_name = {
        str(team["name"]): team
        for team in teams
    }

    winner = teams_by_name["Equipo A"]
    loser = teams_by_name["Equipo B"]
    inactive_team = teams_by_name["Equipo C"]

    assert winner["matches_played"] == 1
    assert winner["wins"] == 1
    assert winner["points"] == 3
    assert winner["goal_difference"] == 2

    assert loser["matches_played"] == 1
    assert loser["losses"] == 1
    assert loser["points"] == 0
    assert loser["goal_difference"] == -2

    assert inactive_team["matches_played"] == 0
    assert inactive_team["points"] == 0
    assert inactive_team["goal_difference"] == 0

    connection.close()


def test_draw_awards_one_point_to_each_team() -> None:
    connection = create_test_database()

    connection.execute(
        """
        INSERT INTO matches (
            id,
            tournament_id,
            round_number,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals,
            status
        )
        VALUES (1, 1, 1, 1, 2, 1, 1, 'completed')
        """
    )

    service = StatisticsService(connection)
    service.recalculate_all()

    rows = connection.execute(
        """
        SELECT name, draws, points
        FROM teams
        WHERE id IN (1, 2)
        ORDER BY id
        """
    ).fetchall()

    assert rows[0]["draws"] == 1
    assert rows[0]["points"] == 1

    assert rows[1]["draws"] == 1
    assert rows[1]["points"] == 1

    connection.close()


def test_recalculation_does_not_duplicate_statistics() -> None:
    connection = create_test_database()

    connection.execute(
        """
        INSERT INTO matches (
            id,
            tournament_id,
            round_number,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals,
            status
        )
        VALUES (1, 1, 1, 1, 2, 3, 1, 'completed')
        """
    )

    service = StatisticsService(connection)

    service.recalculate_all()
    service.recalculate_all()

    row = connection.execute(
        """
        SELECT matches_played, wins, goals_for, points
        FROM teams
        WHERE id = 1
        """
    ).fetchone()

    assert row["matches_played"] == 1
    assert row["wins"] == 1
    assert row["goals_for"] == 3
    assert row["points"] == 3

    connection.close()