import pytest

from src.prediction.elo_model import EloPredictionModel
from src.prediction.registry import (
    PredictionModelAlreadyRegisteredError,
    PredictionModelNotFoundError,
    PredictionModelRegistry,
)


def test_registers_gets_and_lists_models_in_registration_order() -> None:
    model = EloPredictionModel()
    registry = PredictionModelRegistry([model])

    assert registry.get("elo", "1.0.0") is model
    assert registry.list_active() == [model]


def test_rejects_duplicate_model_identity() -> None:
    registry = PredictionModelRegistry([EloPredictionModel()])

    with pytest.raises(PredictionModelAlreadyRegisteredError):
        registry.register(EloPredictionModel())


def test_reports_missing_model() -> None:
    registry = PredictionModelRegistry()

    with pytest.raises(PredictionModelNotFoundError):
        registry.get("missing", "1.0.0")
