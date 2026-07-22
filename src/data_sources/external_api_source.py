import json
from collections.abc import Callable
from urllib.request import urlopen

from src.models.match import ExternalMatch


class ExternalDataSourceError(RuntimeError):
    """Raised when a remote source cannot provide canonical match data."""


class ExternalApiMatchDataSource:
    def __init__(
        self,
        url: str,
        name: str = "http_json",
        timeout: float = 10.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.url = url
        self.name = name
        self.timeout = timeout
        self._opener = opener

    def fetch_matches(self) -> list[ExternalMatch]:
        try:
            response = self._opener(self.url, timeout=self.timeout)
            with response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise ExternalDataSourceError(
                "The external match source could not be read"
            ) from error
        if not isinstance(payload, list):
            raise ExternalDataSourceError(
                "The external match response must be a list"
            )
        if not all(isinstance(item, dict) for item in payload):
            raise ExternalDataSourceError(
                "Every external match must be an object"
            )
        try:
            return [
                ExternalMatch(**item)
                for item in payload
            ]
        except (TypeError, ValueError) as error:
            raise ExternalDataSourceError(
                "The external match response is invalid"
            ) from error
