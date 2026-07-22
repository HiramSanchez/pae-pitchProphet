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
        else:
            if match_id is None:
                raise ValueError("match_id is required to compare models")
            data = self.queries.compare_models_for_match(match_id)
            message = "Comparación de modelos para el partido solicitado."
        return QueryAnswer(intent, message, data)
