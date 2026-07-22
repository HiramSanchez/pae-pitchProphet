import sqlite3

from scripts.backtest_models import backtest_models
from src.models.prediction import (
    PredictedResult,
    Prediction,
    TeamRating,
)
from src.prediction.elo_model import EloPredictionModel
from src.services.backtesting_service import BacktestingService


class RecordingModel:
    name = "recording"
    version = "1.0.0"
    configuration: dict[str, float] = {}

    def __init__(self) -> None:
        self.inputs: list[tuple[TeamRating, TeamRating]] = []

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        self.inputs.append((home_team, away_team))
        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=0.4,
            draw_probability=0.3,
            away_probability=0.3,
            predicted_result=PredictedResult.HOME,
        )


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


def test_form_state_uses_only_previous_rounds() -> None:
    connection = create_test_database()
    model = RecordingModel()

    BacktestingService(connection).run(model, 1)

    first_round_home, first_round_away = model.inputs[0]
    second_round_home, second_round_away = model.inputs[2]

    assert first_round_home.recent_points == 0.0
    assert first_round_away.recent_points == 0.0
    assert second_round_home.recent_points == 3.0
    assert second_round_home.recent_goal_difference == 3.0
    assert second_round_home.home_points_per_match == 3.0
    assert second_round_away.recent_points == 0.0
    assert second_round_away.home_points_per_match == 0.0

    connection.close()


def test_backtest_compares_elo_and_elo_form() -> None:
    connection = create_test_database()

    evaluations = backtest_models(connection, 1)

    assert {item.model_name for item in evaluations} == {
        "elo",
        "elo_form",
    }
    assert evaluations == sorted(
        evaluations,
        key=lambda item: (
            item.log_loss,
            item.calibration_error,
            item.brier_score,
            -item.accuracy,
        ),
    )

    connection.close()
