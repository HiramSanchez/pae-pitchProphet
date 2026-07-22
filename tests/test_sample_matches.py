import json
from dataclasses import replace
from pathlib import Path

from src.data_sources.manual_source import ManualMatchDataSource
from src.services.data_update_service import DataUpdateService
from tests.test_data_update_service import database


SAMPLE_PATH = Path("examples/sample_matches.json")


def test_sample_file_exercises_complete_local_update() -> None:
    source = ManualMatchDataSource.from_json_file(SAMPLE_PATH, "sample")
    connection = database()

    first = DataUpdateService(connection).run(source)
    second = DataUpdateService(connection).run(source)

    assert first.matches_added == 4
    assert first.matches_updated == 0
    assert first.predictions_generated == 8
    assert second.matches_added == 0
    assert second.matches_updated == 0
    assert second.predictions_generated == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM model_evaluations"
    ).fetchone()[0] == 4


def test_sample_identity_supports_a_completed_match_update() -> None:
    source = ManualMatchDataSource.from_json_file(SAMPLE_PATH, "sample")
    connection = database()
    DataUpdateService(connection).run(source)
    items = source.fetch_matches()
    updated_match = replace(
        items[2], status="completed", home_goals=1, away_goals=2
    )

    result = DataUpdateService(connection).run(
        ManualMatchDataSource([*items[:2], updated_match, items[3]], "sample")
    )

    assert result.matches_added == 0
    assert result.matches_updated == 1
    row = connection.execute(
        """
        SELECT m.status, m.home_goals, m.away_goals
        FROM matches m
        JOIN match_sources s ON s.match_id = m.id
        WHERE s.source_name = 'sample'
          AND s.external_match_id = ?
        """,
        (updated_match.external_match_id,),
    ).fetchone()
    assert tuple(row) == ("completed", 1, 2)


def test_sample_json_uses_only_external_match_fields() -> None:
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    expected_fields = {
        "external_match_id",
        "tournament_name",
        "season",
        "round_number",
        "home_team_name",
        "away_team_name",
        "status",
        "match_date",
        "home_goals",
        "away_goals",
    }

    assert all(set(item) == expected_fields for item in payload)
