from src.database import database_connection
from src.database.migrations import (
    migrate_prediction_persistence_schema,
)


def migrate_prediction_persistence() -> None:
    with database_connection() as connection:
        migrate_prediction_persistence_schema(connection)

    print("Migración de predicciones aplicada correctamente.")


if __name__ == "__main__":
    migrate_prediction_persistence()
