from contextlib import contextmanager
from collections.abc import Iterator
import sqlite3

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.data_sources.manual_source import ManualMatchDataSource
from src.services.data_update_service import DataUpdateService
from tests.test_data_update_service import database, matches


def client_with_data() -> tuple[TestClient, sqlite3.Connection]:
    connection = database()
    DataUpdateService(connection).run(ManualMatchDataSource(matches()))

    @contextmanager
    def provider() -> Iterator[sqlite3.Connection]:
        yield connection

    return TestClient(create_app(provider)), connection


def test_prediction_and_performance_endpoints() -> None:
    client, connection = client_with_data()
    match_id = connection.execute(
        "SELECT id FROM matches WHERE status = 'scheduled'"
    ).fetchone()[0]

    round_response = client.get("/tournaments/1/rounds/2/predictions")
    match_response = client.get(f"/matches/{match_id}/predictions")
    explanation = client.get(f"/matches/{match_id}/explanation")
    performance = client.get("/models/performance?tournament_id=1")

    assert round_response.status_code == 200
    assert len(round_response.json()) == 4
    assert match_response.status_code == 200
    assert len(match_response.json()["predictions"]) == 4
    assert explanation.status_code == 200
    assert explanation.json()["prediction"]["model_name"] == "ensemble"
    assert performance.status_code == 200
    assert len(performance.json()) == 4


def test_primary_spanish_query_returns_required_prediction_context() -> None:
    client, _ = client_with_data()

    response = client.post(
        "/queries",
        json={
            "question": (
                "¿Cuáles son las mejores predicciones para la "
                "siguiente jornada y por qué?"
            ),
            "tournament_id": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "best_predictions"
    item = payload["data"][0]
    view = item["prediction"]
    assert view["round_number"] == 2
    assert view["model_name"] == "ensemble"
    assert view["model_version"] == "1.0.0"
    assert view["prediction"]["home_probability"] >= 0
    assert view["explanation"]["uncertainty"]


def test_query_validation_and_missing_resources_are_http_errors() -> None:
    client, _ = client_with_data()

    unknown = client.post(
        "/queries",
        json={"question": "Hola", "tournament_id": 1},
    )
    missing = client.get("/matches/999/predictions")
    invalid = client.get("/models/performance?tournament_id=0")

    assert unknown.status_code == 422
    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_update_endpoint_calls_pipeline_with_canonical_matches() -> None:
    connection = database()

    @contextmanager
    def provider() -> Iterator[sqlite3.Connection]:
        yield connection

    client = TestClient(create_app(provider))
    response = client.post(
        "/updates/run",
        json={
            "source_name": "api-test",
            "matches": [
                {
                    "external_match_id": "scheduled-1",
                    "tournament_name": "Liga MX",
                    "season": "2026",
                    "round_number": 1,
                    "home_team_name": "A",
                    "away_team_name": "B",
                    "status": "scheduled",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["matches_added"] == 1
    assert response.json()["predictions_generated"] == 4


def test_personal_journal_api_supports_open_save_finalize_and_get() -> None:
    client, connection = client_with_data()
    match_id = connection.execute(
        "SELECT id FROM matches WHERE status = 'scheduled'"
    ).fetchone()[0]

    opened = client.post("/tournaments/1/rounds/2/journal")
    saved = client.put(
        "/tournaments/1/rounds/2/picks",
        json={
            "picks": [
                {
                    "match_id": match_id,
                    "predicted_outcome": "home",
                }
            ]
        },
    )
    pick_id = saved.json()["picks"][0]["prediction_id"]
    changed = client.patch(
        f"/picks/{pick_id}",
        json={"predicted_outcome": "draw"},
    )
    finalized = client.post("/tournaments/1/rounds/2/finalize")
    retrieved = client.get("/tournaments/1/rounds/2/picks")
    locked = client.patch(
        f"/picks/{pick_id}",
        json={"predicted_outcome": "away"},
    )

    assert opened.status_code == 200
    assert opened.json()["journal"]["status"] == "open"
    assert saved.status_code == 200
    assert changed.status_code == 200
    assert changed.json()["predicted_result"] == "DRAW"
    assert finalized.status_code == 200
    assert finalized.json()["journal"]["status"] == "finalized"
    assert retrieved.json()["picks"][0]["predicted_result"] == "DRAW"
    assert locked.status_code == 409


def test_personal_journal_api_reports_incomplete_and_missing_rounds() -> None:
    client, _ = client_with_data()

    missing = client.post("/tournaments/999/rounds/2/journal")
    unopened = client.put(
        "/tournaments/1/rounds/2/picks",
        json={"picks": []},
    )
    client.post("/tournaments/1/rounds/2/journal")
    incomplete = client.post("/tournaments/1/rounds/2/finalize")
    invalid_outcome = client.put(
        "/tournaments/1/rounds/2/picks",
        json={"picks": [{"match_id": 1, "predicted_outcome": "win"}]},
    )

    assert missing.status_code == 404
    assert unopened.status_code == 409
    assert incomplete.status_code == 400
    assert invalid_outcome.status_code == 422
