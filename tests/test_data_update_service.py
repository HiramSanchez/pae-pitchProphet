import sqlite3

import pytest

from scripts.initialize_database import SCHEMA
from src.data_sources.manual_source import ManualMatchDataSource
from src.database.migrations import (
    migrate_evaluation_persistence_schema,
    migrate_prediction_persistence_schema,
    migrate_team_statistics_schema,
    migrate_update_pipeline_schema,
)
from src.models.match import ExternalMatch
from src.services.data_update_service import DataUpdateService


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    migrate_team_statistics_schema(connection)
    migrate_prediction_persistence_schema(connection)
    migrate_evaluation_persistence_schema(connection)
    migrate_update_pipeline_schema(connection)
    return connection


def matches(home_goals: int = 2) -> list[ExternalMatch]:
    return [
        ExternalMatch(
            "completed-1", "Liga MX", "2026", 1, " A ", "B",
            "completed", "2026-01-01T12:00:00+00:00", home_goals, 0,
        ),
        ExternalMatch(
            "scheduled-2", "Liga MX", "2026", 2, "B", "A",
            "scheduled", "2026-01-08T12:00:00+00:00",
        ),
    ]


def test_pipeline_is_idempotent_and_keeps_evaluation_history() -> None:
    connection = database()
    service = DataUpdateService(connection)

    first = service.run(ManualMatchDataSource(matches()))
    ratings_after_first = connection.execute(
        "SELECT id, current_elo FROM teams ORDER BY id"
    ).fetchall()
    second = service.run(ManualMatchDataSource(matches()))
    ratings_after_second = connection.execute(
        "SELECT id, current_elo FROM teams ORDER BY id"
    ).fetchall()

    assert first.matches_added == 2
    assert first.predictions_generated == 4
    assert second.matches_added == 0
    assert second.matches_updated == 0
    assert second.predictions_generated == 0
    assert [tuple(row) for row in ratings_after_second] == [
        tuple(row) for row in ratings_after_first
    ]
    assert connection.execute(
        "SELECT COUNT(1) FROM matches"
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(1) FROM elo_history"
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(1) FROM predictions"
    ).fetchone()[0] == 4
    assert connection.execute(
        "SELECT COUNT(1) FROM model_evaluations"
    ).fetchone()[0] == 4
    assert connection.execute(
        "SELECT COUNT(1) FROM update_runs WHERE status = 'succeeded'"
    ).fetchone()[0] == 2

    snapshot_before = connection.execute(
        "SELECT input_snapshot_json FROM predictions ORDER BY id LIMIT 1"
    ).fetchone()[0]
    service.run(ManualMatchDataSource(matches(home_goals=1)))
    assert connection.execute(
        "SELECT COUNT(1) FROM model_evaluations"
    ).fetchone()[0] == 8
    assert connection.execute(
        "SELECT COUNT(1) FROM predictions"
    ).fetchone()[0] == 4
    snapshot_after = connection.execute(
        "SELECT input_snapshot_json FROM predictions ORDER BY id LIMIT 1"
    ).fetchone()[0]
    assert snapshot_after != snapshot_before


def test_completed_match_prediction_is_not_refreshed() -> None:
    connection = database()
    service = DataUpdateService(connection)
    scheduled = ExternalMatch(
        "m1", "Liga MX", "2026", 1, "A", "B", "scheduled"
    )
    service.run(ManualMatchDataSource([scheduled]))
    stored = connection.execute(
        "SELECT input_snapshot_json FROM predictions ORDER BY id"
    ).fetchall()

    completed = ExternalMatch(
        "m1", "Liga MX", "2026", 1, "A", "B", "completed",
        home_goals=2, away_goals=0,
    )
    service.run(ManualMatchDataSource([completed]))

    assert connection.execute(
        "SELECT input_snapshot_json FROM predictions ORDER BY id"
    ).fetchall() == stored


def test_failed_pipeline_rolls_back_data_but_keeps_sanitized_audit() -> None:
    connection = database()

    class FailingSource:
        name = "remote"

        def fetch_matches(self) -> list[ExternalMatch]:
            raise RuntimeError("https://api.test?token=secret\nprivate")

    with pytest.raises(RuntimeError):
        DataUpdateService(connection).run(FailingSource())

    row = connection.execute("SELECT * FROM update_runs").fetchone()
    assert row["status"] == "failed"
    assert row["finished_at"] is not None
    assert "secret" not in row["error_message"]
    assert "\n" not in row["error_message"]
    assert connection.execute("SELECT COUNT(1) FROM matches").fetchone()[0] == 0


def test_failure_after_sync_rolls_back_matches_and_keeps_audit() -> None:
    connection = database()
    connection.execute(
        """
        CREATE TRIGGER reject_elo_history BEFORE INSERT ON elo_history
        BEGIN SELECT RAISE(ABORT, 'forced failure'); END
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        DataUpdateService(connection).run(
            ManualMatchDataSource(matches())
        )

    assert connection.execute("SELECT COUNT(1) FROM matches").fetchone()[0] == 0
    row = connection.execute("SELECT * FROM update_runs").fetchone()
    assert row["status"] == "failed"
    assert row["finished_at"] is not None
