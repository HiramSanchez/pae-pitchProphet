import unicodedata
import re
from enum import StrEnum


class QueryIntent(StrEnum):
    BEST_PREDICTIONS = "best_predictions"
    HIGHEST_DRAWS = "highest_draws"
    MODEL_PERFORMANCE = "model_performance"
    CHANGED_PREDICTIONS = "changed_predictions"
    COMPARE_MODELS = "compare_models"
    NEXT_ROUND = "next_round"
    PERSONAL_PICKS = "personal_picks"
    ROUND_RESULTS = "round_results"
    PERSONAL_PERFORMANCE = "personal_performance"
    PERSONAL_MODEL_COMPARISON = "personal_model_comparison"


class UnsupportedQueryError(ValueError):
    """Raised when the deterministic interpreter cannot map a question."""


class SpanishQueryInterpreter:
    def interpret(self, question: str) -> QueryIntent:
        normalized = self._normalize(question)
        if "contra" in normalized and "modelo" in normalized:
            return QueryIntent.PERSONAL_MODEL_COMPARISON
        if (
            "mi efectividad" in normalized
            or "mi rendimiento" in normalized
            or "mis aciertos" in normalized
        ):
            return QueryIntent.PERSONAL_PERFORMANCE
        if (
            "como me fue" in normalized
            or (
                "resultado" in normalized
                and "jornada" in normalized
            )
        ):
            return QueryIntent.ROUND_RESULTS
        if (
            "mi quiniela" in normalized
            or "mis pronostico" in normalized
            or "mis prediccion" in normalized
        ):
            return QueryIntent.PERSONAL_PICKS
        if (
            "siguiente jornada" in normalized
            or "proxima jornada" in normalized
        ) and not any(
            term in normalized
            for term in ("prediccion", "pronostico", "mejor")
        ):
            return QueryIntent.NEXT_ROUND
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

    def extract_round_number(self, question: str) -> int | None:
        normalized = self._normalize(question)
        match = re.search(
            r"\bjornada\s+(?:(?:numero|no)\s+)?(\d+)\b",
            normalized,
        )
        return int(match.group(1)) if match is not None else None

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.casefold())
        return "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
