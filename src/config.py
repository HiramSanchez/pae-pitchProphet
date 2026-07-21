from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = PROJECT_ROOT / "backups"

DATABASE_PATH = DATA_DIR / "liga_mx.db"

DEFAULT_ELO = 1500.0
HOME_ADVANTAGE_ELO = 65.0
ELO_K_FACTOR = 30.0