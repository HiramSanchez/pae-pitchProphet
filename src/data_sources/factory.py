from pathlib import Path

from src.data_sources.base import MatchDataSource
from src.data_sources.external_api_source import ExternalApiMatchDataSource
from src.data_sources.manual_source import ManualMatchDataSource


def create_match_data_source(
    source_file: Path | None,
    api_url: str | None,
    source_name: str,
    timeout: float,
) -> MatchDataSource:
    if source_file is not None:
        return ManualMatchDataSource.from_json_file(
            source_file, source_name
        )
    if api_url is not None:
        return ExternalApiMatchDataSource(
            api_url, name=source_name, timeout=timeout
        )
    raise ValueError("A match source is required")
