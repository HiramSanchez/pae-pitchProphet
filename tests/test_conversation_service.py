import pytest

from src.query.interpreter import (
    QueryIntent,
    SpanishQueryInterpreter,
    UnsupportedQueryError,
)


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        (
            "¿Cuáles son las mejores predicciones para la siguiente jornada?",
            QueryIntent.BEST_PREDICTIONS,
        ),
        ("¿Dónde hay más probabilidad de empate?", QueryIntent.HIGHEST_DRAWS),
        ("¿Cuál es el mejor modelo?", QueryIntent.MODEL_PERFORMANCE),
        ("¿Qué predicciones cambiaron?", QueryIntent.CHANGED_PREDICTIONS),
        ("Compara los modelos", QueryIntent.COMPARE_MODELS),
        ("¿Cuál es la siguiente jornada?", QueryIntent.NEXT_ROUND),
        ("¿Cuáles fueron mis pronósticos?", QueryIntent.PERSONAL_PICKS),
        ("¿Cómo me fue en la jornada 8?", QueryIntent.ROUND_RESULTS),
        ("¿Cuál es mi efectividad?", QueryIntent.PERSONAL_PERFORMANCE),
        (
            "¿Cómo voy contra los modelos?",
            QueryIntent.PERSONAL_MODEL_COMPARISON,
        ),
    ],
)
def test_spanish_interpreter_maps_supported_questions(
    question: str, intent: QueryIntent
) -> None:
    assert SpanishQueryInterpreter().interpret(question) == intent


def test_spanish_interpreter_rejects_unknown_intent() -> None:
    with pytest.raises(UnsupportedQueryError):
        SpanishQueryInterpreter().interpret("Hola")


@pytest.mark.parametrize(
    ("question", "round_number"),
    [
        ("¿Cómo me fue en la jornada 8?", 8),
        ("Resultados de la jornada número 12", 12),
        ("¿Cuál es la siguiente jornada?", None),
    ],
)
def test_spanish_interpreter_extracts_explicit_round(
    question: str,
    round_number: int | None,
) -> None:
    assert (
        SpanishQueryInterpreter().extract_round_number(question)
        == round_number
    )
