import sqlite3
from itertools import groupby

from src.config import DEFAULT_ELO
from src.models.evaluation import BacktestPrediction
from src.models.match import CompletedMatch
from src.models.prediction import PredictedResult, TeamRating
from src.prediction.base import PredictionModel
from src.repositories.match_repository import MatchRepository
from src.services.elo_service import update_elo


class BacktestingService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        initial_elo: float = DEFAULT_ELO,
    ) -> None:
        self.match_repository = MatchRepository(connection)
        self.initial_elo = initial_elo

    def run(
        self,
        model: PredictionModel,
        tournament_id: int,
    ) -> list[BacktestPrediction]:
        matches = self.match_repository.find_completed_by_tournament(
            tournament_id
        )
        ratings: dict[int, float] = {}
        backtest_predictions: list[BacktestPrediction] = []

        for _, round_matches_iterator in groupby(
            matches,
            key=lambda match: match.round_number,
        ):
            round_matches = list(round_matches_iterator)

            for match in round_matches:
                home_elo = ratings.get(
                    match.home_team_id,
                    self.initial_elo,
                )
                away_elo = ratings.get(
                    match.away_team_id,
                    self.initial_elo,
                )
                prediction = model.predict(
                    TeamRating(
                        match.home_team_id,
                        match.home_team_name,
                        home_elo,
                    ),
                    TeamRating(
                        match.away_team_id,
                        match.away_team_name,
                        away_elo,
                    ),
                )
                backtest_predictions.append(
                    BacktestPrediction(
                        match_id=match.match_id,
                        tournament_id=match.tournament_id,
                        round_number=match.round_number,
                        prediction=prediction,
                        actual_result=self._actual_result(match),
                        home_elo_before=home_elo,
                        away_elo_before=away_elo,
                    )
                )

            for match in round_matches:
                home_elo = ratings.get(
                    match.home_team_id,
                    self.initial_elo,
                )
                away_elo = ratings.get(
                    match.away_team_id,
                    self.initial_elo,
                )
                update = update_elo(
                    home_elo=home_elo,
                    away_elo=away_elo,
                    home_goals=match.home_goals,
                    away_goals=match.away_goals,
                )
                ratings[match.home_team_id] = update.home_elo_after
                ratings[match.away_team_id] = update.away_elo_after

        return backtest_predictions

    @staticmethod
    def _actual_result(
        match: CompletedMatch,
    ) -> PredictedResult:
        if match.home_goals > match.away_goals:
            return PredictedResult.HOME
        if match.home_goals < match.away_goals:
            return PredictedResult.AWAY
        return PredictedResult.DRAW
