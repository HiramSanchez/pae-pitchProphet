from src.database import database_connection
from src.database.migrations import (
    migrate_evaluation_persistence_schema,
)


def migrate_evaluation_persistence() -> None:
    with database_connection() as connection:
        migrate_evaluation_persistence_schema(connection)

    print("Migración de evaluaciones aplicada correctamente.")


if __name__ == "__main__":
    migrate_evaluation_persistence()
