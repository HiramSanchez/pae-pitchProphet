import sqlite3
from collections import defaultdict

from src.models.evaluation import ModelEvaluation
from src.models.query import (
    BestPrediction,
    ModelComparison,
    PredictionChange,
    PredictionExplanation,
    PredictionRevision,
    PredictionView,
)
from src.repositories.evaluation_repository import EvaluationRepository
from src.repositories.match_repository import MatchRepository
from src.repositories.prediction_repository import PredictionRepository
from src.repositories.user_prediction_repository import (
    UserPredictionRepository,
)
from src.config import SINGLE_USER_PREDICTOR
from src.models.user_prediction import (
    UserPrediction,
    UserPredictionRound,
)


class QueryService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.matches = MatchRepository(connection)
        self.predictions = PredictionRepository(connection)
        self.evaluations = EvaluationRepository(connection)
        self.user_predictions = UserPredictionRepository(connection)

    def get_best_predictions_for_next_round(
        self, tournament_id: int
    ) -> list[BestPrediction]:
        round_number = self.matches.find_next_scheduled_round(tournament_id)
        if round_number is None:
            return []
        views = self.predictions.find_views_by_round(
            tournament_id, round_number
        )
        evaluations = self.evaluations.find_latest_for_tournament(
            tournament_id
        )
        evaluation_by_model = {
            (item.model_name, item.model_version): item
            for item in evaluations
        }
        grouped: dict[int, list[PredictionView]] = defaultdict(list)
        for view in views:
            grouped[view.match_id].append(view)
        results = [
            self._best_for_match(items, evaluation_by_model)
            for items in grouped.values()
        ]
        return sorted(
            results,
            key=lambda item: (
                -item.prediction.confidence,
                -item.agreement_ratio,
                (
                    item.calibration_error
                    if item.calibration_error is not None
                    else float("inf")
                ),
                -item.evaluated_matches,
                item.prediction.match_id,
            ),
        )

    def get_predictions_for_round(
        self, tournament_id: int, round_number: int
    ) -> list[PredictionView]:
        return self.predictions.find_views_by_round(
            tournament_id, round_number
        )

    def get_model_performance(
        self, tournament_id: int
    ) -> list[ModelEvaluation]:
        return self.evaluations.find_latest_for_tournament(tournament_id)

    def get_personal_prediction_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> UserPredictionRound | None:
        return self.user_predictions.find_round(
            tournament_id,
            round_number,
            SINGLE_USER_PREDICTOR,
        )

    def get_personal_predictions_for_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[UserPrediction]:
        return self.user_predictions.find_by_round(
            tournament_id,
            round_number,
            SINGLE_USER_PREDICTOR,
        )

    def get_prediction_explanation(
        self,
        match_id: int,
        model_name: str,
        model_version: str,
    ) -> PredictionExplanation | None:
        view = next(
            (
                item
                for item in self.predictions.find_views_by_match(match_id)
                if item.model_name == model_name
                and item.model_version == model_version
            ),
            None,
        )
        if view is None or view.explanation is None:
            return None
        return PredictionExplanation(view, view.explanation)

    def get_highest_draw_probabilities(
        self,
        tournament_id: int,
        round_number: int | None = None,
        limit: int = 10,
    ) -> list[PredictionView]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        selected_round = (
            round_number
            if round_number is not None
            else self.matches.find_next_scheduled_round(tournament_id)
        )
        if selected_round is None:
            return []
        views = self.predictions.find_views_by_round(
            tournament_id, selected_round
        )
        return sorted(
            views,
            key=lambda item: (
                -item.prediction.draw_probability,
                item.match_id,
                item.model_name,
            ),
        )[:limit]

    def compare_models_for_match(
        self, match_id: int
    ) -> ModelComparison | None:
        views = self.predictions.find_views_by_match(match_id)
        if not views:
            return None
        favorites = {
            self._identity(view): view.prediction.predicted_result.value.lower()
            for view in views
        }
        unique_results = set(favorites.values())
        ranges = {
            result: (
                min(self._probability(view, result) for view in views),
                max(self._probability(view, result) for view in views),
            )
            for result in ("home", "draw", "away")
        }
        return ModelComparison(
            match_id=match_id,
            predictions=tuple(views),
            favorites=favorites,
            agreed_result=(
                next(iter(unique_results))
                if len(unique_results) == 1
                else None
            ),
            probability_ranges=ranges,
        )

    def get_best_performing_model(
        self, tournament_id: int
    ) -> ModelEvaluation | None:
        evaluations = self.evaluations.find_latest_for_tournament(
            tournament_id
        )
        return evaluations[0] if evaluations else None

    def get_recent_model_performance(
        self,
        model_name: str,
        model_version: str,
        tournament_id: int,
        limit: int = 10,
    ) -> list[ModelEvaluation]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return self.evaluations.find_recent_by_model(
            model_name, model_version, tournament_id, limit
        )

    def get_changed_predictions(
        self,
        tournament_id: int | None = None,
        limit: int = 50,
    ) -> list[PredictionChange]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        changes = []
        for previous in self.predictions.find_latest_revisions(
            tournament_id, limit
        ):
            current = self.predictions.find_view_by_prediction_id(
                previous.prediction_id
            )
            if current is None:
                continue
            changes.append(
                PredictionChange(
                    previous=previous,
                    current=current,
                    result_changed=(
                        previous.prediction.predicted_result
                        != current.prediction.predicted_result
                    ),
                    probability_deltas={
                        result: self._probability(current, result)
                        - self._probability(previous, result)
                        for result in ("home", "draw", "away")
                    },
                )
            )
        return changes

    @staticmethod
    def _best_for_match(
        views: list[PredictionView],
        evaluations: dict[tuple[str, str], ModelEvaluation],
    ) -> BestPrediction:
        representative = next(
            (view for view in views if view.model_name == "ensemble"),
            min(
                views,
                key=lambda view: (
                    evaluations.get(
                        (view.model_name, view.model_version)
                    ).log_loss
                    if (view.model_name, view.model_version) in evaluations
                    else float("inf"),
                    view.model_name,
                ),
            ),
        )
        result = representative.prediction.predicted_result
        agreeing = tuple(
            QueryService._identity(view)
            for view in views
            if view.prediction.predicted_result == result
        )
        evaluation = evaluations.get(
            (representative.model_name, representative.model_version)
        )
        return BestPrediction(
            prediction=representative,
            agreement_ratio=len(agreeing) / len(views),
            agreeing_models=agreeing,
            calibration_error=(
                evaluation.calibration_error if evaluation else None
            ),
            evaluated_matches=(evaluation.evaluated_matches if evaluation else 0),
        )

    @staticmethod
    def _identity(view: PredictionView) -> str:
        return f"{view.model_name}:{view.model_version}"

    @staticmethod
    def _probability(
        view: PredictionView | PredictionRevision,
        result: str,
    ) -> float:
        prediction = view.prediction
        return {
            "home": prediction.home_probability,
            "draw": prediction.draw_probability,
            "away": prediction.away_probability,
        }[result]
