import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from src.data_sources.external_api_source import ExternalDataSourceError
from src.services.data_update_service import DataUpdateResult
from src.services.prediction_service import (
    InvalidPredictionError,
    TeamNotFoundError,
)


@dataclass(frozen=True)
class AutomationResult:
    attempts: int
    update: DataUpdateResult


class AutomationService:
    def __init__(
        self,
        max_attempts: int = 3,
        retry_delay: float = 5.0,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if not 0 <= retry_delay <= 60:
            raise ValueError("retry_delay must be between 0 and 60 seconds")
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.sleeper = sleeper
        self.logger = logger or logging.getLogger("pitchprophet.automation")

    def run(
        self,
        operation: Callable[[], DataUpdateResult],
    ) -> AutomationResult:
        for attempt in range(1, self.max_attempts + 1):
            self._log(logging.INFO, "attempt_started", attempt)
            try:
                update = operation()
            except Exception as error:
                category = self._category(error)
                self._log(
                    logging.ERROR,
                    "attempt_failed",
                    attempt,
                    category=category,
                    error_type=type(error).__name__,
                )
                if attempt == self.max_attempts:
                    self._log(
                        logging.CRITICAL,
                        "workflow_failed",
                        attempt,
                        category=category,
                    )
                    raise
                if self.retry_delay:
                    self.sleeper(self.retry_delay)
            else:
                self._log(
                    logging.INFO,
                    "workflow_succeeded",
                    attempt,
                    run_id=update.run_id,
                    matches_added=update.matches_added,
                    matches_updated=update.matches_updated,
                    predictions_generated=update.predictions_generated,
                )
                return AutomationResult(attempt, update)
        raise RuntimeError("Automation attempts were exhausted")

    def _log(
        self,
        level: int,
        event: str,
        attempt: int,
        **context: object,
    ) -> None:
        self.logger.log(
            level,
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": event,
                    "attempt": attempt,
                    **context,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    @staticmethod
    def _category(error: Exception) -> str:
        if isinstance(error, InvalidPredictionError):
            return "invalid_probabilities"
        if isinstance(error, TeamNotFoundError):
            return "unknown_team"
        if isinstance(error, ExternalDataSourceError):
            return "source_unavailable"
        if isinstance(error, sqlite3.DatabaseError):
            return "database_or_migration_failure"
        if isinstance(error, ValueError):
            return "incomplete_or_invalid_data"
        return "pipeline_incomplete"
