import math
from datetime import datetime, timezone

from src.models.evaluation import (
    BacktestPrediction,
    ModelEvaluation,
)
from src.models.prediction import PredictedResult, Prediction
from src.prediction.base import PredictionModel


PROBABILITY_FLOOR = 1e-15
CALIBRATION_BINS = 10
RESULTS = (
    PredictedResult.HOME,
    PredictedResult.DRAW,
    PredictedResult.AWAY,
)


class EvaluationService:
    def evaluate(
        self,
        model: PredictionModel,
        tournament_id: int | None,
        backtest_predictions: list[BacktestPrediction],
        evaluated_at: str | None = None,
    ) -> ModelEvaluation:
        if not backtest_predictions:
            raise ValueError("At least one prediction is required")

        return ModelEvaluation(
            model_name=model.name,
            model_version=model.version,
            tournament_id=tournament_id,
            evaluated_matches=len(backtest_predictions),
            log_loss=self.log_loss(backtest_predictions),
            brier_score=self.brier_score(backtest_predictions),
            accuracy=self.accuracy(backtest_predictions),
            top_two_accuracy=self.top_two_accuracy(
                backtest_predictions
            ),
            calibration_error=self.calibration_error(
                backtest_predictions
            ),
            confusion_matrix=self.confusion_matrix(
                backtest_predictions
            ),
            evaluated_at=(
                evaluated_at
                if evaluated_at is not None
                else datetime.now(timezone.utc).isoformat()
            ),
        )

    @staticmethod
    def log_loss(
        backtest_predictions: list[BacktestPrediction],
    ) -> float:
        losses = [
            -math.log(
                max(
                    EvaluationService._probability_for_result(
                        item.prediction,
                        item.actual_result,
                    ),
                    PROBABILITY_FLOOR,
                )
            )
            for item in backtest_predictions
        ]
        return sum(losses) / len(losses)

    @staticmethod
    def brier_score(
        backtest_predictions: list[BacktestPrediction],
    ) -> float:
        total = 0.0
        for item in backtest_predictions:
            for result in RESULTS:
                probability = (
                    EvaluationService._probability_for_result(
                        item.prediction,
                        result,
                    )
                )
                observed = float(item.actual_result == result)
                total += (probability - observed) ** 2
        return total / len(backtest_predictions)

    @staticmethod
    def accuracy(
        backtest_predictions: list[BacktestPrediction],
    ) -> float:
        correct = sum(
            item.prediction.predicted_result == item.actual_result
            for item in backtest_predictions
        )
        return correct / len(backtest_predictions)

    @staticmethod
    def top_two_accuracy(
        backtest_predictions: list[BacktestPrediction],
    ) -> float:
        correct = 0
        for item in backtest_predictions:
            ranked = EvaluationService._ranked_results(
                item.prediction
            )
            correct += item.actual_result in ranked[:2]
        return correct / len(backtest_predictions)

    @staticmethod
    def confusion_matrix(
        backtest_predictions: list[BacktestPrediction],
    ) -> dict[str, dict[str, int]]:
        matrix = {
            actual.value: {
                predicted.value: 0
                for predicted in RESULTS
            }
            for actual in RESULTS
        }
        for item in backtest_predictions:
            matrix[item.actual_result.value][
                item.prediction.predicted_result.value
            ] += 1
        return matrix

    @staticmethod
    def calibration_error(
        backtest_predictions: list[BacktestPrediction],
    ) -> float:
        bins: list[list[tuple[float, float]]] = [
            [] for _ in range(CALIBRATION_BINS)
        ]
        for item in backtest_predictions:
            confidence = max(
                item.prediction.home_probability,
                item.prediction.draw_probability,
                item.prediction.away_probability,
            )
            accuracy = float(
                item.prediction.predicted_result
                == item.actual_result
            )
            bin_index = min(
                int(confidence * CALIBRATION_BINS),
                CALIBRATION_BINS - 1,
            )
            bins[bin_index].append((confidence, accuracy))

        total_predictions = len(backtest_predictions)
        error = 0.0
        for calibration_bin in bins:
            if not calibration_bin:
                continue
            average_confidence = sum(
                confidence
                for confidence, _ in calibration_bin
            ) / len(calibration_bin)
            average_accuracy = sum(
                accuracy
                for _, accuracy in calibration_bin
            ) / len(calibration_bin)
            error += (
                len(calibration_bin)
                / total_predictions
                * abs(average_confidence - average_accuracy)
            )
        return error

    @staticmethod
    def _ranked_results(
        prediction: Prediction,
    ) -> list[PredictedResult]:
        probabilities = {
            PredictedResult.HOME: prediction.home_probability,
            PredictedResult.DRAW: prediction.draw_probability,
            PredictedResult.AWAY: prediction.away_probability,
        }
        return sorted(
            RESULTS,
            key=probabilities.__getitem__,
            reverse=True,
        )

    @staticmethod
    def _probability_for_result(
        prediction: Prediction,
        result: PredictedResult,
    ) -> float:
        return {
            PredictedResult.HOME: prediction.home_probability,
            PredictedResult.DRAW: prediction.draw_probability,
            PredictedResult.AWAY: prediction.away_probability,
        }[result]
