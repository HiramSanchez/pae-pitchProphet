import hashlib
import json
import sqlite3
from dataclasses import replace

from src.models.evaluation import ModelEvaluation
from src.models.match import CompletedMatch
from src.config import DEFAULT_ELO, ELO_K_FACTOR, HOME_ADVANTAGE_ELO
from src.prediction.base import PredictionModel
from src.repositories.evaluation_repository import EvaluationRepository
from src.repositories.match_repository import MatchRepository
from src.services.backtesting_service import BacktestingService
from src.services.evaluation_service import EvaluationService


EVALUATION_KEY_FORMAT = "pitchprophet-evaluation-v1"


class EvaluationHistoryService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.matches = MatchRepository(connection)
        self.backtesting = BacktestingService(connection)
        self.evaluations = EvaluationRepository(connection)
        self.metrics = EvaluationService()

    def evaluate(
        self,
        model: PredictionModel,
        tournament_id: int,
    ) -> ModelEvaluation | None:
        matches = self.matches.find_completed_by_tournament(tournament_id)
        if not matches:
            return None
        key = self._key(model, tournament_id, matches)
        existing = self.evaluations.find_by_key(key)
        if existing is not None:
            return existing
        predictions = self.backtesting.run(model, tournament_id)
        evaluation = self.metrics.evaluate(
            model, tournament_id, predictions
        )
        rounds = [match.round_number for match in matches]
        return self.evaluations.save(
            replace(
                evaluation,
                evaluation_key=key,
                from_round=min(rounds),
                to_round=max(rounds),
            )
        )

    @staticmethod
    def _key(
        model: PredictionModel,
        tournament_id: int,
        matches: list[CompletedMatch],
    ) -> str:
        payload = {
            "format": EVALUATION_KEY_FORMAT,
            "model": {
                "name": model.name,
                "version": model.version,
                "configuration": model.configuration,
            },
            "tournament_id": tournament_id,
            "walk_forward": {
                "initial_elo": DEFAULT_ELO,
                "elo_k_factor": ELO_K_FACTOR,
                "elo_home_advantage": HOME_ADVANTAGE_ELO,
                "recent_results_window": 5,
            },
            "matches": [
                {
                    "match_id": match.match_id,
                    "match_date": match.match_date,
                    "round_number": match.round_number,
                    "home_team_id": match.home_team_id,
                    "away_team_id": match.away_team_id,
                    "home_goals": match.home_goals,
                    "away_goals": match.away_goals,
                }
                for match in sorted(
                    matches,
                    key=lambda item: (
                        item.match_date is None,
                        item.match_date or "",
                        item.round_number,
                        item.home_team_id,
                        item.away_team_id,
                        item.match_id,
                    ),
                )
            ],
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
