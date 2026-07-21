import sqlite3

import pytest

from src.database.migrations import (
    migrate_prediction_persistence_schema,
)
from src.models.prediction import (
    PredictedResult,
    Prediction,
    VersionedPrediction,
)
from src.repositories.prediction_repository import (
    ModelConfigurationMismatchError,
    PredictionAlreadyExistsError,
    PredictionRepository,
)


def create_test_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            tournament_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL
        );

        INSERT INTO matches (id, tournament_id, round_number)
        VALUES
            (1, 1, 2),
            (2, 1, 3);
        """
    )
    migrate_prediction_persistence_schema(connection)
    return connection


def versioned_prediction(
    match_id: int = 1,
    configuration: dict[str, float] | None = None,
) -> VersionedPrediction:
    return VersionedPrediction(
        match_id=match_id,
        model_name="elo",
        model_version="1.0.0",
        configuration=(
            configuration
            if configuration is not None
            else {"home_advantage": 80.0}
        ),
        prediction=Prediction(
            home_team_id=10,
            away_team_id=20,
            home_probability=0.5,
            draw_probability=0.3,
            away_probability=0.2,
            predicted_result=PredictedResult.HOME,
        ),
        input_snapshot={
            "home_team": {"team_id": 10, "elo": 1550.0},
            "away_team": {"team_id": 20, "elo": 1450.0},
            "model_configuration": {"home_advantage": 80.0},
            "generated_at": "2026-07-21T12:00:00+00:00",
        },
        created_at="2026-07-21T12:00:00+00:00",
        explanation={
            "main_factors": [],
            "uncertainty": "low",
            "alternative_result": "draw",
        },
    )


def test_save_and_find_reproduces_prediction() -> None:
    connection = create_test_database()
    repository = PredictionRepository(connection)

    saved = repository.save(versioned_prediction())
    recovered = repository.find_by_match_and_model(
        match_id=1,
        model_name="elo",
        model_version="1.0.0",
    )

    assert saved.prediction_id is not None
    assert recovered == saved
    assert recovered is not None
    assert recovered.confidence == 0.5

    connection.close()


def test_save_rejects_duplicate_prediction() -> None:
    connection = create_test_database()
    repository = PredictionRepository(connection)
    prediction = versioned_prediction()
    repository.save(prediction)

    with pytest.raises(PredictionAlreadyExistsError):
        repository.save(prediction)

    assert connection.execute(
        "SELECT COUNT(1) FROM predictions"
    ).fetchone()[0] == 1

    connection.close()


def test_save_requires_explanation() -> None:
    connection = create_test_database()
    repository = PredictionRepository(connection)
    prediction = versioned_prediction()
    prediction_without_explanation = VersionedPrediction(
        match_id=prediction.match_id,
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        configuration=prediction.configuration,
        prediction=prediction.prediction,
        input_snapshot=prediction.input_snapshot,
        created_at=prediction.created_at,
    )

    with pytest.raises(ValueError, match="requires an explanation"):
        repository.save(prediction_without_explanation)

    connection.close()


def test_save_rejects_configuration_change_for_same_version() -> None:
    connection = create_test_database()
    repository = PredictionRepository(connection)
    repository.save(versioned_prediction(match_id=1))

    with pytest.raises(ModelConfigurationMismatchError):
        repository.save(
            versioned_prediction(
                match_id=2,
                configuration={"home_advantage": 65.0},
            )
        )

    connection.close()


def test_find_by_round_filters_tournament_and_round() -> None:
    connection = create_test_database()
    repository = PredictionRepository(connection)
    expected = repository.save(versioned_prediction(match_id=1))

    predictions = repository.find_by_round(1, 2)

    assert predictions == [expected]
    assert repository.find_by_round(1, 99) == []

    connection.close()


def test_update_explanation_preserves_prediction_data() -> None:
    connection = create_test_database()
    repository = PredictionRepository(connection)
    saved = repository.save(versioned_prediction())
    explanation = {
        "main_factors": [],
        "uncertainty": "low",
        "alternative_result": "draw",
    }

    updated = repository.update_explanation(
        saved,
        explanation,
    )
    recovered = repository.find_by_match_and_model(
        1,
        "elo",
        "1.0.0",
    )

    assert updated.explanation == explanation
    assert recovered == updated
    assert updated.prediction == saved.prediction
    assert updated.input_snapshot == saved.input_snapshot

    connection.close()
