import argparse

from src.database import database_connection
from src.models.match import MatchPrediction
from src.services.explanation_service import ExplanationService
from src.services.prediction_service import PredictionService


def display_predictions(
    predictions: list[MatchPrediction],
) -> None:
    if not predictions:
        print("No hay partidos programados para esa jornada.")
        return

    for match in predictions:
        prediction = match.prediction
        print(
            f"{match.home_team_name} vs "
            f"{match.away_team_name}: "
            f"{prediction.predicted_result.value} "
            f"(local {prediction.home_probability:.1%}, "
            f"empate {prediction.draw_probability:.1%}, "
            f"visitante {prediction.away_probability:.1%})"
        )
        if match.explanation is not None:
            print(
                "  "
                + ExplanationService.to_spanish(
                    match.explanation
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Genera predicciones para una jornada programada."
        )
    )
    parser.add_argument("tournament_id", type=int)
    parser.add_argument("round_number", type=int)
    arguments = parser.parse_args()

    with database_connection() as connection:
        service = PredictionService(connection)
        predictions = service.predict_round(
            tournament_id=arguments.tournament_id,
            round_number=arguments.round_number,
        )

    display_predictions(predictions)


if __name__ == "__main__":
    main()
