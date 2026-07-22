from src.database import database_connection
from src.database.migrations import migrate_team_statistics_schema


def migrate_team_statistics() -> None:
    with database_connection() as connection:
        added_columns = migrate_team_statistics_schema(connection)

    if not added_columns:
        print("La migración ya había sido aplicada.")
        return

    print("Migración aplicada correctamente.")
    print(f"Columnas agregadas: {len(added_columns)}")
    for column_name in added_columns:
        print(f"  - {column_name}")


if __name__ == "__main__":
    migrate_team_statistics()
