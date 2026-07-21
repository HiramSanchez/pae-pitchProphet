from src.database import database_connection
from src.services.statistics_service import StatisticsService


def recalculate_statistics() -> None:
    with database_connection() as connection:
        service = StatisticsService(connection)
        processed_matches = service.recalculate_all()

    print("Estadísticas recalculadas correctamente.")
    print(f"Partidos considerados: {processed_matches}")


if __name__ == "__main__":
    recalculate_statistics()