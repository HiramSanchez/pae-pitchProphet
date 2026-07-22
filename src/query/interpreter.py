import unicodedata
from enum import StrEnum


class QueryIntent(StrEnum):
    BEST_PREDICTIONS = "best_predictions"
    HIGHEST_DRAWS = "highest_draws"
    MODEL_PERFORMANCE = "model_performance"
    CHANGED_PREDICTIONS = "changed_predictions"
    COMPARE_MODELS = "compare_models"


class UnsupportedQueryError(ValueError):
    """Raised when the deterministic interpreter cannot map a question."""


class SpanishQueryInterpreter:
    def interpret(self, question: str) -> QueryIntent:
        normalized = self._normalize(question)
        if "cambi" in normalized:
            return QueryIntent.CHANGED_PREDICTIONS
        if "empate" in normalized:
            return QueryIntent.HIGHEST_DRAWS
        if "rendimiento" in normalized or "mejor modelo" in normalized:
            return QueryIntent.MODEL_PERFORMANCE
        if "compar" in normalized and "modelo" in normalized:
            return QueryIntent.COMPARE_MODELS
        if (
            "mejor" in normalized
            or "prediccion" in normalized
            or "pronostico" in normalized
        ):
            return QueryIntent.BEST_PREDICTIONS
        raise UnsupportedQueryError("No se pudo interpretar la consulta")

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.casefold())
        return "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
