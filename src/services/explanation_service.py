from src.models.prediction import VersionedPrediction
from src.prediction.explanations import (
    alternative_result,
    build_elo_factors,
    build_elo_form_factors,
    build_poisson_factors,
    calculate_uncertainty,
)


class UnsupportedPredictionModelError(ValueError):
    """Raised when no explanation strategy exists for a model."""


class ExplanationService:
    def generate(
        self,
        versioned_prediction: VersionedPrediction,
    ) -> dict[str, object]:
        if versioned_prediction.model_name == "elo":
            factors = build_elo_factors(
                versioned_prediction.input_snapshot
            )
        elif versioned_prediction.model_name == "elo_form":
            factors = build_elo_form_factors(
                versioned_prediction.input_snapshot
            )
        elif versioned_prediction.model_name == "poisson":
            factors = build_poisson_factors(
                versioned_prediction.input_snapshot
            )
        else:
            raise UnsupportedPredictionModelError(
                "No explanation strategy for model "
                f"{versioned_prediction.model_name}"
            )

        return {
            "main_factors": factors,
            "uncertainty": calculate_uncertainty(
                versioned_prediction.prediction
            ),
            "alternative_result": alternative_result(
                versioned_prediction.prediction
            ),
        }

    @staticmethod
    def to_spanish(explanation: dict[str, object]) -> str:
        factors = explanation["main_factors"]
        if not isinstance(factors, list):
            raise ValueError("Invalid explanation factors")

        descriptions = [
            str(factor["description"])
            for factor in factors
            if isinstance(factor, dict)
        ]
        uncertainty = str(explanation["uncertainty"])
        alternative = str(explanation["alternative_result"])

        uncertainty_labels = {
            "low": "baja",
            "medium": "media",
            "high": "alta",
        }
        result_labels = {
            "home": "victoria local",
            "draw": "empate",
            "away": "victoria visitante",
        }

        return (
            f"{'. '.join(descriptions)}. "
            "Incertidumbre "
            f"{uncertainty_labels[uncertainty]}. "
            "Resultado alternativo: "
            f"{result_labels[alternative]}."
        )
