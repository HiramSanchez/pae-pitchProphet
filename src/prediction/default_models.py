from src.prediction.base import PredictionModel
from src.prediction.elo_form_model import EloFormPredictionModel
from src.prediction.elo_model import EloPredictionModel
from src.prediction.ensemble_model import EnsemblePredictionModel
from src.prediction.poisson_model import PoissonPredictionModel
from src.prediction.registry import PredictionModelRegistry


def default_model_registry() -> PredictionModelRegistry:
    components: list[PredictionModel] = [
        EloPredictionModel(), EloFormPredictionModel(), PoissonPredictionModel()
    ]
    return PredictionModelRegistry(
        [*components, EnsemblePredictionModel(components)]
    )
