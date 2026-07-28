import sqlite3

import pytest

from src.models.prediction import PredictedResult
from src.models.user_prediction import (
    UserPickSelection,
    UserPredictionRoundStatus,
)
from src.repositories.user_prediction_repository import (
    UserPredictionRoundStateError,
)
from src.services.personal_prediction_service import (
    PersonalPredictionService,
)
from src.data_sources.manual_source import ManualMatchDataSource
from src.services.data_update_service import DataUpdateService
from tests.test_data_update_service import matches
from tests.test_data_update_service import database


def _database_with_round() -> sqlite3.Connection:
    connection = database()
    connection.executescript(
        """
        INSERT INTO tournaments (id, name, season)
        VALUES (1, 'Liga MX', 'Apertura 2026');
        INSERT INTO teams (id, name) VALUES (1, 'A');
        INSERT INTO teams (id, name) VALUES (2, 'B');
        INSERT INTO teams (id, name) VALUES (3, 'C');
        INSERT INTO teams (id, name) VALUES (4, 'D');
        INSERT INTO matches (
            id, tournament_id, round_number, home_team_id,
            away_team_id, status
        ) VALUES (1, 1, 2, 1, 2, 'scheduled');
        INSERT INTO matches (
            id, tournament_id, round_number, home_team_id,
            away_team_id, status
        ) VALUES (2, 1, 2, 3, 4, 'scheduled');
        """
    )
    return connection


def test_service_saves_partial_picks_and_finalizes_complete_round() -> None:
    service = PersonalPredictionService(_database_with_round())
    service.open_round(1, 2)

    partial = service.save_picks(
        1, 2, [UserPickSelection(1, PredictedResult.HOME)]
    )
    with pytest.raises(ValueError, match="1 active match picks"):
        service.finalize_round(1, 2)
    complete = service.save_picks(
        1, 2, [UserPickSelection(2, PredictedResult.DRAW)]
    )
    finalized = service.finalize_round(1, 2)

    assert len(partial) == 1
    assert len(complete) == 2
    assert finalized.status == UserPredictionRoundStatus.FINALIZED
    with pytest.raises(UserPredictionRoundStateError):
        service.update_pick(
            complete[0].prediction_id, PredictedResult.AWAY
        )


def test_service_rolls_back_batch_when_one_write_fails() -> None:
    connection = _database_with_round()
    service = PersonalPredictionService(connection)
    service.open_round(1, 2)
    connection.executescript(
        """
        CREATE TRIGGER reject_second_personal_pick
        BEFORE INSERT ON user_predictions
        WHEN NEW.match_id = 2
        BEGIN
            SELECT RAISE(ABORT, 'forced personal pick failure');
        END;
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        service.save_picks(
            1,
            2,
            [
                UserPickSelection(1, PredictedResult.HOME),
                UserPickSelection(2, PredictedResult.AWAY),
            ],
        )

    assert connection.execute(
        "SELECT COUNT(*) FROM user_predictions"
    ).fetchone()[0] == 0


def test_cancelled_match_is_excluded_from_finalization() -> None:
    connection = _database_with_round()
    connection.execute(
        "UPDATE matches SET status = 'cancelled' WHERE id = 2"
    )
    service = PersonalPredictionService(connection)
    service.open_round(1, 2)
    service.save_picks(
        1, 2, [UserPickSelection(1, PredictedResult.HOME)]
    )

    finalized = service.finalize_round(1, 2)

    assert finalized.status == UserPredictionRoundStatus.FINALIZED


def test_finalization_captures_available_models_idempotently() -> None:
    connection = database()
    DataUpdateService(connection).run(
        ManualMatchDataSource(matches())
    )
    match_id = connection.execute(
        "SELECT id FROM matches WHERE status = 'scheduled'"
    ).fetchone()[0]
    service = PersonalPredictionService(connection)
    service.open_round(1, 2)
    service.save_picks(
        1, 2, [UserPickSelection(match_id, PredictedResult.HOME)]
    )

    service.finalize_round(1, 2)
    service.finalize_round(1, 2)

    rows = connection.execute(
        """
        SELECT model_name, model_version
        FROM user_prediction_model_snapshots
        ORDER BY model_name
        """
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("elo", "1.0.0"),
        ("elo_form", "1.0.0"),
        ("ensemble", "1.0.0"),
        ("poisson", "1.0.0"),
    ]
