from collections.abc import Iterable

from src.prediction.base import PredictionModel


class PredictionModelAlreadyRegisteredError(ValueError):
    """Raised when the same model identity is registered twice."""


class PredictionModelNotFoundError(LookupError):
    """Raised when a requested model identity is not registered."""


class PredictionModelRegistry:
    def __init__(
        self,
        models: Iterable[PredictionModel] = (),
    ) -> None:
        self._models: dict[tuple[str, str], PredictionModel] = {}
        for model in models:
            self.register(model)

    def register(self, model: PredictionModel) -> None:
        identity = (model.name, model.version)
        if identity in self._models:
            raise PredictionModelAlreadyRegisteredError(
                f"Model {model.name} {model.version} is already registered"
            )
        self._models[identity] = model

    def get(self, name: str, version: str) -> PredictionModel:
        try:
            return self._models[(name, version)]
        except KeyError as error:
            raise PredictionModelNotFoundError(
                f"Model {name} {version} is not registered"
            ) from error

    def list_active(self) -> list[PredictionModel]:
        return list(self._models.values())
