import argparse
import logging
import sys
from pathlib import Path

from src.data_sources.factory import create_match_data_source
from src.database import database_connection
from src.database.migrations import migrate_runtime_schema
from src.services.automation_service import AutomationService
from src.services.data_update_service import DataUpdateResult, DataUpdateService


def configure_logging(log_file: Path | None) -> logging.Logger:
    logger = logging.getLogger("pitchprophet.automation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta el workflow automatizado de PitchProphet."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-file", type=Path)
    source.add_argument("--api-url")
    parser.add_argument("--source-name", default="automated")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=5.0)
    parser.add_argument("--log-file", type=Path)
    arguments = parser.parse_args()
    logger = configure_logging(arguments.log_file)

    def update_once() -> DataUpdateResult:
        data_source = create_match_data_source(
            arguments.source_file,
            arguments.api_url,
            arguments.source_name,
            arguments.timeout,
        )
        with database_connection() as connection:
            migrate_runtime_schema(connection)
            return DataUpdateService(connection).run(data_source)

    try:
        AutomationService(
            max_attempts=arguments.max_attempts,
            retry_delay=arguments.retry_delay,
            logger=logger,
        ).run(update_once)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
