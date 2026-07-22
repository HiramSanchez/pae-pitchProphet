import json
import logging
import sqlite3

import pytest

from src.data_sources.external_api_source import ExternalDataSourceError
from src.data_sources.manual_source import ManualMatchDataSource
from src.database.migrations import migrate_runtime_schema
from src.services.automation_service import AutomationService
from src.services.data_update_service import DataUpdateResult, DataUpdateService
from src.services.prediction_service import (
    InvalidPredictionError,
    TeamNotFoundError,
)
from tests.test_data_update_service import database, matches


def result(run_id: int = 1) -> DataUpdateResult:
    return DataUpdateResult(run_id, 2, 1, 4)


def test_automation_succeeds_without_retry(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="pitchprophet.automation")
    sleeps: list[float] = []

    outcome = AutomationService(
        retry_delay=2,
        sleeper=sleeps.append,
    ).run(result)

    assert outcome.attempts == 1
    assert outcome.update == result()
    assert sleeps == []
    events = [json.loads(record.message) for record in caplog.records]
    assert [event["event"] for event in events] == [
        "attempt_started",
        "workflow_succeeded",
    ]
    assert all(event["timestamp"].endswith("+00:00") for event in events)


def test_retry_is_idempotent_and_audits_each_attempt() -> None:
    connection = database()

    class FlakySource:
        name = "remote"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_matches(self):
            self.calls += 1
            if self.calls == 1:
                raise ExternalDataSourceError("temporary outage")
            return matches()

    source = FlakySource()
    sleeps: list[float] = []
    outcome = AutomationService(
        max_attempts=2,
        retry_delay=1,
        sleeper=sleeps.append,
    ).run(lambda: DataUpdateService(connection).run(source))

    assert outcome.attempts == 2
    assert sleeps == [1]
    assert connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 4
    statuses = connection.execute(
        "SELECT status FROM update_runs ORDER BY id"
    ).fetchall()
    assert [row["status"] for row in statuses] == ["failed", "succeeded"]


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ExternalDataSourceError("secret"), "source_unavailable"),
        (sqlite3.DatabaseError("secret"), "database_or_migration_failure"),
        (ValueError("secret"), "incomplete_or_invalid_data"),
        (InvalidPredictionError("secret"), "invalid_probabilities"),
        (TeamNotFoundError("secret"), "unknown_team"),
        (RuntimeError("secret"), "pipeline_incomplete"),
    ],
)
def test_failure_logs_safe_alert_category(
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    category: str,
) -> None:
    caplog.set_level(logging.INFO, logger="pitchprophet.automation")

    def fail() -> DataUpdateResult:
        raise error

    with pytest.raises(type(error)):
        AutomationService(max_attempts=1).run(fail)

    events = [json.loads(record.message) for record in caplog.records]
    assert events[-1]["event"] == "workflow_failed"
    assert events[-1]["category"] == category
    assert "secret" not in "".join(record.message for record in caplog.records)


@pytest.mark.parametrize(
    "arguments",
    [
        {"max_attempts": 0},
        {"retry_delay": -1},
        {"retry_delay": 61},
    ],
)
def test_automation_rejects_invalid_retry_configuration(arguments) -> None:
    with pytest.raises(ValueError):
        AutomationService(**arguments)


def test_runtime_migration_is_repeatable() -> None:
    connection = sqlite3.connect(":memory:")
    from scripts.initialize_database import SCHEMA

    connection.executescript(SCHEMA)
    migrate_runtime_schema(connection)
    migrate_runtime_schema(connection)

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {
        "predictions",
        "prediction_revisions",
        "model_evaluations",
        "match_sources",
        "update_runs",
    } <= tables
