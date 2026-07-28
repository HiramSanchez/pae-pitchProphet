import sqlite3
from collections import defaultdict

from src.models.evaluation import ModelEvaluation
from src.models.prediction import PredictedResult
from src.models.product import (
    NextRound,
    ProductMatch,
    RoundResult,
    RoundResults,
)
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
    PerformanceParticipant,
    PersonalModelComparison,
    PersonalPerformance,
    UserPrediction,
    UserPredictionModelSnapshot,
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

    def get_next_round(
        self,
        tournament_id: int,
    ) -> NextRound | None:
        round_number = self.matches.find_next_scheduled_round(tournament_id)
        if round_number is None:
            return None
        matches = self.matches.find_by_round(tournament_id, round_number)
        predictions_by_match: dict[int, list[PredictionView]] = defaultdict(
            list
        )
        for prediction in self.predictions.find_views_by_round(
            tournament_id, round_number
        ):
            predictions_by_match[prediction.match_id].append(prediction)
        personal_by_match = {
            item.match_id: item
            for item in self.user_predictions.find_by_round(
                tournament_id,
                round_number,
                SINGLE_USER_PREDICTOR,
            )
        }
        return NextRound(
            tournament_id=tournament_id,
            round_number=round_number,
            journal=self.get_personal_prediction_round(
                tournament_id, round_number
            ),
            matches=tuple(
                ProductMatch(
                    match_id=match.match_id,
                    home_team_name=match.home_team_name,
                    away_team_name=match.away_team_name,
                    status=match.status,
                    match_date=match.match_date,
                    personal_pick=personal_by_match.get(match.match_id),
                    predictions=tuple(
                        predictions_by_match[match.match_id]
                    ),
                )
                for match in matches
            ),
        )

    def get_round_results(
        self,
        tournament_id: int,
        round_number: int,
    ) -> RoundResults | None:
        matches = self.matches.find_by_round(tournament_id, round_number)
        if not matches:
            return None
        personal_by_match = {
            item.match_id: item
            for item in self.user_predictions.find_by_round(
                tournament_id,
                round_number,
                SINGLE_USER_PREDICTOR,
            )
        }
        return RoundResults(
            tournament_id=tournament_id,
            round_number=round_number,
            journal=self.get_personal_prediction_round(
                tournament_id, round_number
            ),
            matches=tuple(
                RoundResult(
                    match_id=match.match_id,
                    home_team_name=match.home_team_name,
                    away_team_name=match.away_team_name,
                    status=match.status,
                    home_goals=match.home_goals,
                    away_goals=match.away_goals,
                    actual_result=self._actual_result(
                        match.home_goals,
                        match.away_goals,
                        match.status,
                    ),
                    personal_pick=personal_by_match.get(match.match_id),
                )
                for match in matches
            ),
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

    def get_personal_performance(
        self,
        tournament_id: int,
    ) -> PersonalPerformance:
        predictions = self.user_predictions.find_evaluated_by_tournament(
            tournament_id, SINGLE_USER_PREDICTOR
        )
        correct = sum(item.points_awarded or 0 for item in predictions)
        return PersonalPerformance(
            tournament_id=tournament_id,
            evaluated_matches=len(predictions),
            correct=correct,
            accuracy=(correct / len(predictions) if predictions else 0.0),
        )

    def compare_personal_performance(
        self,
        tournament_id: int,
    ) -> PersonalModelComparison:
        personal = self.user_predictions.find_evaluated_by_tournament(
            tournament_id, SINGLE_USER_PREDICTOR
        )
        if not personal:
            return PersonalModelComparison(tournament_id, 0, ())
        prediction_ids = {
            item.prediction_id for item in personal
        }
        snapshots = self.user_predictions.find_snapshots_for_predictions(
            prediction_ids
        )
        snapshots_by_pick: dict[
            int,
            dict[tuple[str, str], UserPredictionModelSnapshot],
        ] = defaultdict(dict)
        for snapshot in snapshots:
            snapshots_by_pick[snapshot.user_prediction_id][
                (snapshot.model_name, snapshot.model_version)
            ] = snapshot
        comparable = [
            item
            for item in personal
            if snapshots_by_pick[item.prediction_id]
        ]
        if not comparable:
            return PersonalModelComparison(tournament_id, 0, ())
        identity_sets = [
            set(snapshots_by_pick[item.prediction_id])
            for item in comparable
        ]
        common_identities = (
            set.intersection(*identity_sets) if identity_sets else set()
        )
        completed = {
            match.match_id: match
            for match in self.matches.find_completed_by_tournament(
                tournament_id
            )
        }
        participants = [
            PerformanceParticipant(
                name="personal",
                correct=sum(
                    item.points_awarded or 0 for item in comparable
                ),
                accuracy=sum(
                    item.points_awarded or 0 for item in comparable
                )
                / len(comparable),
            )
        ]
        for model_name, model_version in sorted(common_identities):
            correct = 0
            for item in comparable:
                match = completed[item.match_id]
                snapshot = snapshots_by_pick[item.prediction_id][
                    (model_name, model_version)
                ]
                actual = (
                    PredictedResult.HOME
                    if match.home_goals > match.away_goals
                    else PredictedResult.AWAY
                    if match.home_goals < match.away_goals
                    else PredictedResult.DRAW
                )
                correct += snapshot.predicted_result == actual
            participants.append(
                PerformanceParticipant(
                    name=f"{model_name}:{model_version}",
                    correct=correct,
                    accuracy=correct / len(comparable),
                )
            )
        return PersonalModelComparison(
            tournament_id=tournament_id,
            evaluated_matches=len(comparable),
            participants=tuple(participants),
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

    @staticmethod
    def _actual_result(
        home_goals: int | None,
        away_goals: int | None,
        status: str,
    ) -> PredictedResult | None:
        if (
            status != "completed"
            or home_goals is None
            or away_goals is None
        ):
            return None
        if home_goals > away_goals:
            return PredictedResult.HOME
        if home_goals < away_goals:
            return PredictedResult.AWAY
        return PredictedResult.DRAW
