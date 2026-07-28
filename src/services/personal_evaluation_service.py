import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from src.config import SINGLE_USER_PREDICTOR
from src.models.match import CompletedMatch
from src.models.prediction import PredictedResult
from src.repositories.match_repository import MatchRepository
from src.repositories.user_prediction_repository import (
    UserPredictionRepository,
)


@dataclass(frozen=True)
class PersonalEvaluationResult:
    rounds_completed: int
    picks_evaluated: int
    picks_changed: int


class PersonalEvaluationService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        predictor: str = SINGLE_USER_PREDICTOR,
    ) -> None:
        self.matches = MatchRepository(connection)
        self.predictions = UserPredictionRepository(connection)
        self.predictor = predictor

    def evaluate(
        self,
        tournament_ids: set[int] | None = None,
        evaluated_at: str | None = None,
    ) -> PersonalEvaluationResult:
        timestamp = evaluated_at or datetime.now(
            timezone.utc
        ).isoformat()
        rounds_completed = 0
        picks_evaluated = 0
        picks_changed = 0
        completed_by_tournament: dict[int, dict[int, CompletedMatch]] = {}

        for journal_round in self.predictions.find_rounds_for_evaluation(
            self.predictor, tournament_ids
        ):
            if journal_round.tournament_id not in completed_by_tournament:
                completed_by_tournament[journal_round.tournament_id] = {
                    match.match_id: match
                    for match in self.matches.find_completed_by_tournament(
                        journal_round.tournament_id
                    )
                }
            completed = completed_by_tournament[
                journal_round.tournament_id
            ]
            for prediction in self.predictions.find_by_round(
                journal_round.tournament_id,
                journal_round.round_number,
                self.predictor,
            ):
                match = completed.get(prediction.match_id)
                if (
                    match is None
                    or match.round_number != journal_round.round_number
                ):
                    continue
                picks_evaluated += 1
                points = int(
                    prediction.predicted_result
                    == self._actual_result(match)
                )
                picks_changed += self.predictions.set_prediction_evaluation(
                    prediction.prediction_id,
                    points,
                    timestamp,
                )

            if (
                self.matches.count_pending_results_by_round(
                    journal_round.tournament_id,
                    journal_round.round_number,
                )
                == 0
            ):
                rounds_completed += self.predictions.mark_round_evaluated(
                    journal_round.round_id, timestamp
                )

        return PersonalEvaluationResult(
            rounds_completed=rounds_completed,
            picks_evaluated=picks_evaluated,
            picks_changed=picks_changed,
        )

    @staticmethod
    def _actual_result(match: CompletedMatch) -> PredictedResult:
        if match.home_goals > match.away_goals:
            return PredictedResult.HOME
        if match.home_goals < match.away_goals:
            return PredictedResult.AWAY
        return PredictedResult.DRAW
