import json
from collections.abc import Iterable
from pathlib import Path

from src.models.match import ExternalMatch


class ManualMatchDataSource:
    def __init__(
        self,
        matches: Iterable[ExternalMatch],
        name: str = "manual",
    ) -> None:
        self.name = name
        self._matches = list(matches)

    @classmethod
    def from_json_file(
        cls,
        path: Path,
        name: str = "manual",
    ) -> "ManualMatchDataSource":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Manual source JSON must contain a list")
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("Every manual match must be an object")
        return cls(
            [ExternalMatch(**item) for item in payload],
            name=name,
        )

    def fetch_matches(self) -> list[ExternalMatch]:
        return list(self._matches)
