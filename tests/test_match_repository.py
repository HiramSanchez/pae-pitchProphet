import sqlite3

from src.repositories.match_repository import MatchRepository


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.executescript(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
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

        INSERT INTO teams (id, name)
        VALUES
            (1, 'Equipo A'),
            (2, 'Equipo B'),
            (3, 'Equipo C');

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
        VALUES
            (1, 1, 2, 1, 2, NULL, NULL, 'scheduled'),
            (2, 1, 2, 2, 3, 2, 1, 'completed'),
            (3, 1, 3, 3, 1, NULL, NULL, 'scheduled'),
            (4, 2, 2, 3, 2, NULL, NULL, 'scheduled'),
            (5, 1, 2, 3, 1, NULL, NULL, 'postponed');
        """
    )

    return connection


def test_find_scheduled_by_round_filters_tournament_round_and_status() -> None:
    connection = create_test_database()
    repository = MatchRepository(connection)

    matches = repository.find_scheduled_by_round(
        tournament_id=1,
        round_number=2,
    )

    assert len(matches) == 1

    match = matches[0]
    assert match.match_id == 1
    assert match.tournament_id == 1
    assert match.round_number == 2
    assert match.home_team_id == 1
    assert match.home_team_name == "Equipo A"
    assert match.away_team_id == 2
    assert match.away_team_name == "Equipo B"

    connection.close()


def test_find_completed_matches_returns_only_completed_matches() -> None:
    connection = create_test_database()
    repository = MatchRepository(connection)

    matches = repository.find_completed_matches()

    assert len(matches) == 1
    assert matches[0]["id"] == 2
    assert matches[0]["round_number"] == 2
    assert matches[0]["home_goals"] == 2
    assert matches[0]["away_goals"] == 1

    connection.close()
