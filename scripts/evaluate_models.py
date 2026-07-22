import argparse

from scripts.backtest_models import backtest_models, display_ranking
from src.database import database_connection
from src.repositories.evaluation_repository import EvaluationRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalúa, persiste y ordena modelos predictivos."
    )
    parser.add_argument("tournament_id", type=int)
    arguments = parser.parse_args()

    with database_connection() as connection:
        evaluations = backtest_models(
            connection,
            arguments.tournament_id,
        )
        repository = EvaluationRepository(connection)
        saved_evaluations = [
            repository.save(evaluation)
            for evaluation in evaluations
        ]

    display_ranking(saved_evaluations)


if __name__ == "__main__":
    main()
