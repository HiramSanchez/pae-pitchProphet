import sqlite3
from pathlib import Path

import pytest

from scripts.initialize_database import initialize_database
from src.config import SQLITE_TIMEOUT_SECONDS
from src.database.backup import (
    create_backup,
    restore_backup,
    verify_database,
)
from src.database.connection import get_connection


def test_connection_enables_foreign_keys_and_busy_timeout(
    tmp_path: Path,
) -> None:
    with get_connection(tmp_path / "database.db") as connection:
        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        busy_timeout = connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]

    assert foreign_keys == 1
    assert busy_timeout == int(SQLITE_TIMEOUT_SECONDS * 1000)


def test_backup_and_restore_preserve_data_and_current_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pitchprophet.db"
    backup_dir = tmp_path / "backups"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('original')")

    backup = create_backup(database_path, backup_dir)
    assert backup is not None
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE sample SET value = 'changed'")

    safety_backup = restore_backup(backup, database_path, backup_dir)

    assert safety_backup is not None
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT value FROM sample"
        ).fetchone()[0] == "original"
    with sqlite3.connect(safety_backup) as connection:
        assert connection.execute(
            "SELECT value FROM sample"
        ).fetchone()[0] == "changed"


def test_backup_rejects_invalid_sqlite_file(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.db"
    invalid.write_text("not a database", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError):
        verify_database(invalid)


def test_initialize_existing_database_creates_pre_migration_backup(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.db"
    backup_dir = tmp_path / "backups"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE legacy_predictions (value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO legacy_predictions VALUES ('preserve me')"
        )

    initialize_database(database_path, backup_dir)

    backups = list(backup_dir.glob("*-before-migration-*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute(
            "SELECT value FROM legacy_predictions"
        ).fetchone()[0] == "preserve me"
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"user_prediction_rounds", "predictions"} <= tables
