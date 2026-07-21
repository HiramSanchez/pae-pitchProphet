import sqlite3

import pytest

from src.models.prediction import (
    PredictedResult,
    Prediction,
    PredictionInput,
    TeamRating,
)
from src.services.prediction_service import (
    PredictionService,
    TeamNotFoundError,
)


class StubPredictionModel:
    name = "stub"
    version = "1.0.0"

    def __init__(self) -> None:
        self.received_teams: tuple[
            TeamRating,
            TeamRating,
        ] | None = None

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        self.received_teams = (home_team, away_team)

        return Prediction(
            home_team_id=home_team.team_id,
            away_team_id=away_team.team_id,
            home_probability=0.2,
            draw_probability=0.3,
            away_probability=0.5,
            predicted_result=PredictedResult.AWAY,
        )


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

    connection.executemany(
        """
        INSERT INTO teams (
            id,
            name,
            current_elo
        )
        VALUES (?, ?, ?)
        """,
        [
            (1, "Local", 1500.0),
            (2, "Visitante", 1500.0),
            (3, "Favorito", 1800.0),
            (4, "Débil", 1300.0),
        ],
    )

    return connection


def test_probabilities_sum_to_one() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    prediction = service.predict(
        PredictionInput(
            home_team_id=1,
            away_team_id=2,
        )
    )

    assert prediction.total_probability == pytest.approx(
        1.0
    )

    connection.close()


def test_equal_elo_favors_home_team() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    prediction = service.predict(
        PredictionInput(
            home_team_id=1,
            away_team_id=2,
        )
    )

    assert (
        prediction.home_probability
        > prediction.away_probability
    )

    assert (
        prediction.predicted_result
        == PredictedResult.HOME
    )

    connection.close()


def test_stronger_away_team_can_be_favorite() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    prediction = service.predict(
        PredictionInput(
            home_team_id=4,
            away_team_id=3,
        )
    )

    assert (
        prediction.away_probability
        > prediction.home_probability
    )

    assert (
        prediction.predicted_result
        == PredictedResult.AWAY
    )

    connection.close()


def test_balanced_teams_have_more_draw_probability() -> None:
    connection = create_test_database()
    service = PredictionService(
        connection,
        home_advantage=0.0,
    )

    balanced_prediction = service.predict_from_ratings(
        home_team=TeamRating(
            team_id=1,
            name="Equipo A",
            elo=1500.0,
        ),
        away_team=TeamRating(
            team_id=2,
            name="Equipo B",
            elo=1500.0,
        ),
    )

    unbalanced_prediction = service.predict_from_ratings(
        home_team=TeamRating(
            team_id=3,
            name="Equipo C",
            elo=1800.0,
        ),
        away_team=TeamRating(
            team_id=4,
            name="Equipo D",
            elo=1300.0,
        ),
    )

    assert (
        balanced_prediction.draw_probability
        > unbalanced_prediction.draw_probability
    )

    connection.close()


def test_missing_team_raises_error() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    with pytest.raises(
        TeamNotFoundError,
        match="999",
    ):
        service.predict(
            PredictionInput(
                home_team_id=1,
                away_team_id=999,
            )
        )

    connection.close()


def test_probabilities_are_valid() -> None:
    connection = create_test_database()
    service = PredictionService(connection)

    prediction = service.predict(
        PredictionInput(
            home_team_id=3,
            away_team_id=4,
        )
    )

    assert 0 <= prediction.home_probability <= 1
    assert 0 <= prediction.draw_probability <= 1
    assert 0 <= prediction.away_probability <= 1

    connection.close()


def test_service_delegates_prediction_to_injected_model() -> None:
    connection = create_test_database()
    model = StubPredictionModel()
    service = PredictionService(
        connection,
        model=model,
    )

    prediction = service.predict(
        PredictionInput(
            home_team_id=1,
            away_team_id=2,
        )
    )

    assert model.received_teams == (
        TeamRating(
            team_id=1,
            name="Local",
            elo=1500.0,
        ),
        TeamRating(
            team_id=2,
            name="Visitante",
            elo=1500.0,
        ),
    )
    assert prediction.predicted_result == PredictedResult.AWAY

    connection.close()
