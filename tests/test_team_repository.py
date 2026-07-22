import sqlite3

import pytest

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


def test_find_rating_with_form_uses_only_prior_rounds() -> None:
    connection = create_test_database()
    connection.execute(
        """
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            status TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO teams (id, name, current_elo)
        VALUES (?, ?, ?)
        """,
        [
            (2, "Visitante", 1500.0),
            (3, "Tercero", 1500.0),
        ],
    )
    connection.executemany(
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
        VALUES (?, 1, ?, ?, ?, ?, ?, 'completed')
        """,
        [
            (1, 1, 1, 2, 2, 0),
            (2, 2, 3, 1, 1, 1),
            (3, 3, 1, 2, 0, 4),
        ],
    )
    repository = TeamRepository(connection)

    rating = repository.find_rating_with_form(
        team_id=1,
        tournament_id=1,
        before_round=3,
    )

    assert rating is not None
    assert rating.recent_points == 4.0
    assert rating.recent_goal_difference == 2.0
    assert rating.home_points_per_match == 3.0
    assert rating.away_points_per_match == 1.0

    connection.close()


def test_prediction_features_include_smoothed_poisson_rates() -> None:
    connection = create_test_database()
    connection.executescript(
        """
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
        INSERT INTO teams (id, name, current_elo)
        VALUES (2, 'B', 1500.0), (3, 'C', 1500.0);
        INSERT INTO matches VALUES
            (1, 1, 1, 1, 2, 2, 0, 'completed'),
            (2, 1, 2, 3, 1, 1, 1, 'completed'),
            (3, 1, 3, 1, 3, 9, 9, 'completed');
        """
    )

    rating = TeamRepository(connection).find_prediction_features(
        team_id=1,
        tournament_id=1,
        before_round=3,
    )

    assert rating is not None
    assert rating.league_home_goals_average == pytest.approx(10 / 7)
    assert rating.league_away_goals_average == pytest.approx(6.5 / 7)
    expected_home_rate = (2 + 5 * (10 / 7)) / 6
    expected_away_rate = (1 + 5 * (6.5 / 7)) / 6
    assert rating.home_attack_strength == pytest.approx(
        expected_home_rate / (10 / 7)
    )
    assert rating.away_attack_strength == pytest.approx(
        expected_away_rate / (6.5 / 7)
    )

    connection.close()


def test_prediction_features_use_neutral_priors_without_history() -> None:
    connection = create_test_database()
    connection.execute(
        """
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            status TEXT NOT NULL
        )
        """
    )

    rating = TeamRepository(connection).find_prediction_features(1, 1, 1)

    assert rating is not None
    assert rating.home_attack_strength == 1.0
    assert rating.home_defense_strength == 1.0
    assert rating.away_attack_strength == 1.0
    assert rating.away_defense_strength == 1.0
    assert rating.league_home_goals_average == 1.4
    assert rating.league_away_goals_average == 1.1

    connection.close()
