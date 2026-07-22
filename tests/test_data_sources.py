import io
import json

import pytest

from src.data_sources.external_api_source import (
    ExternalApiMatchDataSource,
    ExternalDataSourceError,
)


class Response(io.BytesIO):
    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_http_source_uses_timeout_and_normalizes_json() -> None:
    calls = []
    payload = [{
        "external_match_id": "m1", "tournament_name": "Liga MX",
        "season": "2026", "round_number": 1,
        "home_team_name": "A", "away_team_name": "B",
        "status": "scheduled",
    }]

    def opener(url: str, *, timeout: float) -> Response:
        calls.append((url, timeout))
        return Response(json.dumps(payload).encode())

    matches = ExternalApiMatchDataSource(
        "https://example.test/matches", timeout=3.0, opener=opener
    ).fetch_matches()

    assert calls == [("https://example.test/matches", 3.0)]
    assert matches[0].external_match_id == "m1"


def test_http_source_wraps_invalid_responses_without_leaking_body() -> None:
    source = ExternalApiMatchDataSource(
        "https://example.test", opener=lambda *args, **kwargs: Response(b"bad")
    )
    with pytest.raises(ExternalDataSourceError) as captured:
        source.fetch_matches()
    assert "bad" not in str(captured.value)
