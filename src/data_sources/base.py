from typing import Protocol

from src.models.match import ExternalMatch


class MatchDataSource(Protocol):
    name: str

    def fetch_matches(self) -> list[ExternalMatch]: ...
