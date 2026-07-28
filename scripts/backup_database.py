import argparse
from pathlib import Path

from src.config import BACKUP_DIR, DATABASE_PATH
from src.database.backup import create_backup


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crea un respaldo consistente de PitchProphet."
    )
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    arguments = parser.parse_args()
    backup = create_backup(arguments.database, arguments.backup_dir)
    if backup is None:
        parser.error("La base de datos no existe o está vacía.")
    print(backup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
