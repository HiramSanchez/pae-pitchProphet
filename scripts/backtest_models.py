import argparse
import sqlite3

from src.database import database_connection
from src.models.evaluation import ModelEvaluation
from src.prediction.elo_form_model import EloFormPredictionModel
from src.prediction.elo_model import EloPredictionModel
from src.services.backtesting_service import BacktestingService
from src.services.evaluation_service import EvaluationService


def backtest_models(
    connection: sqlite3.Connection,
    tournament_id: int,
) -> list[ModelEvaluation]:
    models = [EloPredictionModel(), EloFormPredictionModel()]
    backtesting_service = BacktestingService(connection)
    evaluation_service = EvaluationService()
    evaluations: list[ModelEvaluation] = []

    for model in models:
        predictions = backtesting_service.run(
            model=model,
            tournament_id=tournament_id,
        )
        if not predictions:
            continue
        evaluations.append(
            evaluation_service.evaluate(
                model=model,
                tournament_id=tournament_id,
                backtest_predictions=predictions,
            )
        )

    return sorted(
        evaluations,
        key=lambda item: (
            item.log_loss,
            item.calibration_error,
            item.brier_score,
            -item.accuracy,
        ),
    )


def display_ranking(evaluations: list[ModelEvaluation]) -> None:
    if not evaluations:
        print("No hay partidos completados para evaluar.")
        return

    print("RANKING DE MODELOS")
    for position, evaluation in enumerate(evaluations, start=1):
        print(
            f"{position}. {evaluation.model_name} "
            f"{evaluation.model_version} | "
            f"Log Loss {evaluation.log_loss:.4f} | "
            "Calibración "
            f"{evaluation.calibration_error:.4f} | "
            f"Brier {evaluation.brier_score:.4f} | "
            f"Accuracy {evaluation.accuracy:.1%}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta backtesting temporal de modelos."
    )
    parser.add_argument("tournament_id", type=int)
    arguments = parser.parse_args()

    with database_connection() as connection:
        evaluations = backtest_models(
            connection,
            arguments.tournament_id,
        )

    display_ranking(evaluations)


if __name__ == "__main__":
    main()
