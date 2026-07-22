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
    ],
)
def test_spanish_interpreter_maps_supported_questions(
    question: str, intent: QueryIntent
) -> None:
    assert SpanishQueryInterpreter().interpret(question) == intent


def test_spanish_interpreter_rejects_unknown_intent() -> None:
    with pytest.raises(UnsupportedQueryError):
        SpanishQueryInterpreter().interpret("Hola")
