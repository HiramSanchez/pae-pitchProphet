import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.config import BACKUP_DIR, DATABASE_PATH


def create_backup(
    database_path: Path = DATABASE_PATH,
    backup_dir: Path = BACKUP_DIR,
    *,
    label: str = "manual",
) -> Path | None:
    """Create a consistent SQLite backup, or return None for a new database."""
    if not database_path.exists() or database_path.stat().st_size == 0:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    destination = backup_dir / (
        f"{database_path.stem}-{label}-{timestamp}.db"
    )
    with sqlite3.connect(
        f"file:{database_path.as_posix()}?mode=ro",
        uri=True,
    ) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    verify_database(destination)
    return destination


def restore_backup(
    backup_path: Path,
    database_path: Path = DATABASE_PATH,
    backup_dir: Path = BACKUP_DIR,
) -> Path | None:
    """Restore a verified backup after preserving the current database."""
    resolved_backup = backup_path.resolve()
    if not resolved_backup.is_file():
        raise FileNotFoundError(f"Backup does not exist: {backup_path}")
    if resolved_backup == database_path.resolve():
        raise ValueError("Backup and destination database must differ")
    verify_database(resolved_backup)
    safety_backup = create_backup(
        database_path,
        backup_dir,
        label="before-restore",
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(
        f"file:{resolved_backup.as_posix()}?mode=ro",
        uri=True,
    ) as source, sqlite3.connect(database_path) as target:
        source.backup(target)
    verify_database(database_path)
    return safety_backup


def verify_database(database_path: Path) -> None:
    with sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro",
        uri=True,
    ) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise sqlite3.DatabaseError(
            f"SQLite integrity check failed for {database_path}"
        )
