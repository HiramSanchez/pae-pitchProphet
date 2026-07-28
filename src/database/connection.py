import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.config import DATABASE_PATH, SQLITE_TIMEOUT_SECONDS


def create_database_directory(database_path: Path = DATABASE_PATH) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(database_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    create_database_directory(database_path)

    connection = sqlite3.connect(
        database_path,
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        f"PRAGMA busy_timeout = {int(SQLITE_TIMEOUT_SECONDS * 1000)}"
    )

    return connection


@contextmanager
def database_connection(
    database_path: Path = DATABASE_PATH,
) -> Iterator[sqlite3.Connection]:
    connection = get_connection(database_path)

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
