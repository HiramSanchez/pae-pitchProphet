import re
import sqlite3
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UpdateRunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def start(self) -> int:
        cursor = self.connection.execute(
            "INSERT INTO update_runs (started_at, status) VALUES (?, 'running')",
            (utc_now(),),
        )
        return int(cursor.lastrowid)

    def succeed(
        self,
        run_id: int,
        added: int,
        updated: int,
        predictions: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE update_runs SET finished_at = ?, status = 'succeeded',
                matches_added = ?, matches_updated = ?,
                predictions_generated = ?, message = ?
            WHERE id = ?
            """,
            (utc_now(), added, updated, predictions, "Update completed", run_id),
        )

    def fail(self, run_id: int, error: Exception) -> None:
        self.connection.execute(
            """
            UPDATE update_runs SET finished_at = ?, status = 'failed',
                message = ?, error_message = ? WHERE id = ?
            """,
            (utc_now(), "Update failed", self._sanitize(error), run_id),
        )

    @staticmethod
    def _sanitize(error: Exception) -> str:
        message = f"{type(error).__name__}: {error}"
        message = re.sub(
            r"([?&](?:token|key|secret|password)=)[^&\s]+",
            r"\1[REDACTED]",
            message,
            flags=re.IGNORECASE,
        )
        return message.replace("\n", " ").replace("\r", " ")[:500]
