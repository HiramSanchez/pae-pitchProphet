import sqlite3

from src.repositories.team_repository import TeamRepository


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            current_elo REAL NOT NULL
        )
        """
    )

    connection.execute(
        """
        INSERT INTO teams (
            id,
            name,
            current_elo
        )
        VALUES (?, ?, ?)
        """,
        (1, "América", 1575.5),
    )

    return connection


def test_find_rating_by_id_returns_team() -> None:
    connection = create_test_database()
    repository = TeamRepository(connection)

    team = repository.find_rating_by_id(1)

    assert team is not None
    assert team.team_id == 1
    assert team.name == "América"
    assert team.elo == 1575.5

    connection.close()


def test_find_rating_by_id_returns_none_when_missing() -> None:
    connection = create_test_database()
    repository = TeamRepository(connection)

    team = repository.find_rating_by_id(999)

    assert team is None

    connection.close()