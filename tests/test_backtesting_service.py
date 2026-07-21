import sqlite3

from src.models.prediction import PredictedResult
from src.prediction.elo_model import EloPredictionModel
from src.services.backtesting_service import BacktestingService


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            current_elo REAL NOT NULL
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

        INSERT INTO teams (id, name, current_elo)
        VALUES
            (1, 'A', 1900.0),
            (2, 'B', 1200.0),
            (3, 'C', 1800.0),
            (4, 'D', 1300.0);

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
            (1, 1, 1, 1, 2, 3, 0, 'completed'),
            (2, 1, 1, 3, 4, 0, 2, 'completed'),
            (3, 1, 2, 1, 3, 1, 1, 'completed'),
            (4, 2, 1, 2, 4, 1, 0, 'completed'),
            (5, 1, 3, 2, 4, NULL, NULL, 'scheduled');
        """
    )
    return connection


def test_walk_forward_uses_only_previous_rounds() -> None:
    connection = create_test_database()
    service = BacktestingService(connection)

    predictions = service.run(EloPredictionModel(), 1)

    assert len(predictions) == 3
    assert predictions[0].home_elo_before == 1500.0
    assert predictions[0].away_elo_before == 1500.0
    assert predictions[1].home_elo_before == 1500.0
    assert predictions[1].away_elo_before == 1500.0
    assert predictions[2].home_elo_before > 1500.0
    assert predictions[2].away_elo_before < 1500.0
    assert predictions[2].actual_result == PredictedResult.DRAW

    connection.close()


def test_backtesting_is_reproducible_and_does_not_write() -> None:
    connection = create_test_database()
    service = BacktestingService(connection)
    model = EloPredictionModel()

    first = service.run(model, 1)
    second = service.run(model, 1)
    stored_ratings = [
        float(row[0])
        for row in connection.execute(
            "SELECT current_elo FROM teams ORDER BY id"
        ).fetchall()
    ]

    assert second == first
    assert stored_ratings == [1900.0, 1200.0, 1800.0, 1300.0]

    connection.close()


def test_empty_tournament_returns_empty_list() -> None:
    connection = create_test_database()

    predictions = BacktestingService(connection).run(
        EloPredictionModel(),
        999,
    )

    assert predictions == []

    connection.close()
