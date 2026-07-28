import sqlite3

import pytest

from scripts.initialize_database import SCHEMA
from src.database.migrations import (
    migrate_prediction_persistence_schema,
    migrate_user_prediction_journal_schema,
)
from src.models.prediction import PredictedResult
from src.models.user_prediction import UserPredictionRoundStatus
from src.repositories.user_prediction_repository import (
    UserPredictionRepository,
    UserPredictionRoundStateError,
)


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    migrate_prediction_persistence_schema(connection)
    migrate_user_prediction_journal_schema(connection)
    connection.executescript(
        """
        INSERT INTO tournaments (id, name, season)
        VALUES (1, 'Liga MX', 'Apertura 2026');
        INSERT INTO teams (id, name) VALUES (1, 'Necaxa');
        INSERT INTO teams (id, name) VALUES (2, 'Atlante');
        INSERT INTO matches (
            id, tournament_id, round_number, home_team_id,
            away_team_id, status
        )
        VALUES (1, 1, 2, 1, 2, 'scheduled');
        """
    )
    return connection


def test_repository_opens_round_and_upserts_prediction() -> None:
    repository = UserPredictionRepository(_database())

    opened = repository.open_round(
        1, 2, "Hiram", "2026-07-27T12:00:00+00:00"
    )
    repeated = repository.open_round(
        1, 2, "Hiram", "2026-07-27T13:00:00+00:00"
    )
    first = repository.save_open_prediction(
        1,
        2,
        "Hiram",
        1,
        PredictedResult.HOME,
        "2026-07-27T12:05:00+00:00",
    )
    updated = repository.save_open_prediction(
        1,
        2,
        "Hiram",
        1,
        PredictedResult.DRAW,
        "2026-07-27T12:10:00+00:00",
    )

    assert opened == repeated
    assert first.prediction_id == updated.prediction_id
    assert updated.predicted_result == PredictedResult.DRAW
    assert updated.updated_at == "2026-07-27T12:10:00+00:00"
    assert repository.find_by_round(1, 2, "Hiram") == [updated]


def test_repository_finalizes_idempotently_and_blocks_writes() -> None:
    repository = UserPredictionRepository(_database())
    repository.open_round(1, 2, "Hiram")
    repository.save_open_prediction(
        1, 2, "Hiram", 1, PredictedResult.HOME
    )

    finalized = repository.finalize_round(
        1, 2, "Hiram", "2026-07-27T14:00:00+00:00"
    )
    repeated = repository.finalize_round(
        1, 2, "Hiram", "2026-07-27T15:00:00+00:00"
    )

    assert finalized == repeated
    assert finalized.status == UserPredictionRoundStatus.FINALIZED
    with pytest.raises(UserPredictionRoundStateError):
        repository.save_open_prediction(
            1, 2, "Hiram", 1, PredictedResult.AWAY
        )


def test_repository_rejects_match_outside_round() -> None:
    repository = UserPredictionRepository(_database())
    repository.open_round(1, 3, "Hiram")

    with pytest.raises(
        ValueError, match="does not belong to the prediction round"
    ):
        repository.save_open_prediction(
            1, 3, "Hiram", 1, PredictedResult.HOME
        )
