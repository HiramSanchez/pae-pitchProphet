import argparse
from pathlib import Path

from src.data_sources.factory import create_match_data_source
from src.database import database_connection
from src.database.migrations import migrate_runtime_schema
from src.services.data_update_service import DataUpdateService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Actualiza datos y predicciones de forma idempotente."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-file", type=Path)
    source.add_argument("--api-url")
    parser.add_argument("--source-name", default="manual")
    parser.add_argument("--timeout", type=float, default=10.0)
    arguments = parser.parse_args()
    data_source = create_match_data_source(
        arguments.source_file,
        arguments.api_url,
        arguments.source_name,
        arguments.timeout,
    )
    with database_connection() as connection:
        migrate_runtime_schema(connection)
        result = DataUpdateService(connection).run(data_source)
    print(
        f"Actualización {result.run_id}: {result.matches_added} nuevos, "
        f"{result.matches_updated} actualizados, "
        f"{result.predictions_generated} predicciones generadas."
    )


if __name__ == "__main__":
    main()
