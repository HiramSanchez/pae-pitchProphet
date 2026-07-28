from contextlib import contextmanager
from collections.abc import Iterator
import sqlite3

from fastapi.testclient import TestClient

from src.api.app import create_app
from tests.test_data_update_service import database


def test_complete_v2_product_workflow() -> None:
    connection = database()

    @contextmanager
    def provider() -> Iterator[sqlite3.Connection]:
        yield connection

    client = TestClient(create_app(provider))
    initial_update = client.post(
        "/updates/run",
        json={
            "source_name": "v2-smoke",
            "matches": [
                {
                    "external_match_id": "previous",
                    "tournament_name": "Liga MX",
                    "season": "2026",
                    "round_number": 1,
                    "home_team_name": "A",
                    "away_team_name": "B",
                    "status": "completed",
                    "home_goals": 2,
                    "away_goals": 0,
                },
                {
                    "external_match_id": "next",
                    "tournament_name": "Liga MX",
                    "season": "2026",
                    "round_number": 2,
                    "home_team_name": "B",
                    "away_team_name": "A",
                    "status": "scheduled",
                },
            ],
        },
    )
    assert initial_update.status_code == 200
    assert initial_update.json()["predictions_generated"] == 4

    next_round = client.get("/tournaments/1/rounds/next")
    assert next_round.status_code == 200
    match_id = next_round.json()["matches"][0]["match_id"]
    assert len(next_round.json()["matches"][0]["predictions"]) == 4

    assert client.post(
        "/tournaments/1/rounds/2/journal"
    ).status_code == 200
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
    assert saved.status_code == 200
    finalized = client.post("/tournaments/1/rounds/2/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["journal"]["status"] == "finalized"

    result_update = client.post(
        "/updates/run",
        json={
            "source_name": "v2-smoke",
            "matches": [
                {
                    "external_match_id": "next",
                    "tournament_name": "Liga MX",
                    "season": "2026",
                    "round_number": 2,
                    "home_team_name": "B",
                    "away_team_name": "A",
                    "status": "completed",
                    "home_goals": 1,
                    "away_goals": 0,
                }
            ],
        },
    )
    assert result_update.status_code == 200
    assert result_update.json()["matches_updated"] == 1

    results = client.get("/tournaments/1/rounds/2/results")
    performance = client.get("/tournaments/1/performance/personal")
    comparison = client.get(
        "/tournaments/1/performance/comparison"
    )
    question = client.post(
        "/queries",
        json={
            "question": "¿Cómo me fue en la jornada 2?",
            "tournament_id": 1,
        },
    )

    assert results.json()["journal"]["status"] == "evaluated"
    assert results.json()["matches"][0]["actual_result"] == "HOME"
    assert performance.json()["evaluated_matches"] == 1
    assert performance.json()["correct"] == 1
    assert comparison.json()["evaluated_matches"] == 1
    assert question.status_code == 200
    assert question.json()["intent"] == "round_results"
