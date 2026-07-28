from dataclasses import dataclass

from src.query.interpreter import QueryIntent, SpanishQueryInterpreter
from src.services.query_service import QueryService


@dataclass(frozen=True)
class QueryAnswer:
    intent: QueryIntent
    message: str
    data: object


class ConversationService:
    def __init__(
        self,
        query_service: QueryService,
        interpreter: SpanishQueryInterpreter | None = None,
    ) -> None:
        self.queries = query_service
        self.interpreter = interpreter or SpanishQueryInterpreter()

    def answer(
        self,
        question: str,
        tournament_id: int,
        match_id: int | None = None,
    ) -> QueryAnswer:
        intent = self.interpreter.interpret(question)
        if intent == QueryIntent.BEST_PREDICTIONS:
            data = self.queries.get_best_predictions_for_next_round(
                tournament_id
            )
            message = (
                "Estas son las mejores predicciones para la siguiente jornada."
                if data
                else "No hay predicciones para la siguiente jornada."
            )
        elif intent == QueryIntent.HIGHEST_DRAWS:
            data = self.queries.get_highest_draw_probabilities(tournament_id)
            message = "Predicciones con mayor probabilidad de empate."
        elif intent == QueryIntent.MODEL_PERFORMANCE:
            data = self.queries.get_model_performance(tournament_id)
            message = "Rendimiento vigente de los modelos."
        elif intent == QueryIntent.CHANGED_PREDICTIONS:
            data = self.queries.get_changed_predictions(tournament_id)
            message = "Predicciones que cambiaron desde su última revisión."
        elif intent == QueryIntent.COMPARE_MODELS:
            if match_id is None:
                raise ValueError("match_id is required to compare models")
            data = self.queries.compare_models_for_match(match_id)
            message = "Comparación de modelos para el partido solicitado."
        elif intent == QueryIntent.NEXT_ROUND:
            data = self.queries.get_next_round(tournament_id)
            message = (
                "Esta es la siguiente jornada programada."
                if data is not None
                else "No hay una siguiente jornada programada."
            )
        elif intent == QueryIntent.PERSONAL_PICKS:
            round_number = self.interpreter.extract_round_number(question)
            if round_number is None:
                data = self.queries.get_latest_personal_journal(
                    tournament_id
                )
                has_journal = data.journal is not None
            else:
                journal = self.queries.get_personal_prediction_round(
                    tournament_id, round_number
                )
                data = {
                    "journal": journal,
                    "picks": (
                        self.queries.get_personal_predictions_for_round(
                            tournament_id, round_number
                        )
                        if journal is not None
                        else []
                    ),
                }
                has_journal = journal is not None
            message = (
                "Estos son tus pronósticos registrados."
                if has_journal
                else "No hay pronósticos personales registrados."
            )
        elif intent == QueryIntent.ROUND_RESULTS:
            round_number = self.interpreter.extract_round_number(question)
            if round_number is None:
                raise ValueError(
                    "La consulta de resultados requiere una jornada"
                )
            data = self.queries.get_round_results(
                tournament_id, round_number
            )
            message = (
                f"Estos son los resultados de la jornada {round_number}."
                if data is not None
                else f"No hay datos para la jornada {round_number}."
            )
        elif intent == QueryIntent.PERSONAL_PERFORMANCE:
            data = self.queries.get_personal_performance(tournament_id)
            message = "Este es tu rendimiento personal acumulado."
        else:
            data = self.queries.compare_personal_performance(tournament_id)
            message = "Esta es tu comparación contra los modelos."
        return QueryAnswer(intent, message, data)
