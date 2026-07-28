import argparse
from pathlib import Path

from src.config import BACKUP_DIR, DATABASE_PATH
from src.database.backup import restore_backup


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Restaura un respaldo verificado y conserva una copia "
            "de seguridad de la base actual."
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    arguments = parser.parse_args()
    safety_backup = restore_backup(
        arguments.backup,
        arguments.database,
        arguments.backup_dir,
    )
    if safety_backup is not None:
        print(f"Respaldo previo a restauración: {safety_backup}")
    print("Base de datos restaurada correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
