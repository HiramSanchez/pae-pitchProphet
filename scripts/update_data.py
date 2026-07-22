import argparse
from pathlib import Path

from src.data_sources.external_api_source import ExternalApiMatchDataSource
from src.data_sources.manual_source import ManualMatchDataSource
from src.database import database_connection
from src.database.migrations import (
    migrate_evaluation_persistence_schema,
    migrate_prediction_persistence_schema,
    migrate_prediction_revisions_schema,
    migrate_team_statistics_schema,
    migrate_update_pipeline_schema,
)
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
    data_source = (
        ManualMatchDataSource.from_json_file(
            arguments.source_file, arguments.source_name
        )
        if arguments.source_file is not None
        else ExternalApiMatchDataSource(
            arguments.api_url,
            name=arguments.source_name,
            timeout=arguments.timeout,
        )
    )
    with database_connection() as connection:
        migrate_team_statistics_schema(connection)
        migrate_prediction_persistence_schema(connection)
        migrate_prediction_revisions_schema(connection)
        migrate_evaluation_persistence_schema(connection)
        migrate_update_pipeline_schema(connection)
        result = DataUpdateService(connection).run(data_source)
    print(
        f"Actualización {result.run_id}: {result.matches_added} nuevos, "
        f"{result.matches_updated} actualizados, "
        f"{result.predictions_generated} predicciones generadas."
    )


if __name__ == "__main__":
    main()
