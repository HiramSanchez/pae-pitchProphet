import sqlite3
from collections import deque
from dataclasses import dataclass, field
from itertools import groupby

from src.config import DEFAULT_ELO
from src.models.evaluation import BacktestPrediction
from src.models.match import CompletedMatch
from src.models.prediction import PredictedResult, TeamRating
from src.prediction.base import PredictionModel
from src.repositories.match_repository import MatchRepository
from src.services.elo_service import update_elo


@dataclass
class _TeamFormState:
    elo: float
    recent_results: deque[tuple[int, int]] = field(
        default_factory=lambda: deque(maxlen=5)
    )
    home_points: int = 0
    home_matches: int = 0
    away_points: int = 0
    away_matches: int = 0

    def rating(
        self,
        team_id: int,
        name: str,
    ) -> TeamRating:
        return TeamRating(
            team_id=team_id,
            name=name,
            elo=self.elo,
            recent_points=float(
                sum(points for points, _ in self.recent_results)
            ),
            recent_goal_difference=float(
                sum(
                    goal_difference
                    for _, goal_difference in self.recent_results
                )
            ),
            home_points_per_match=(
                self.home_points / self.home_matches
                if self.home_matches
                else 0.0
            ),
            away_points_per_match=(
                self.away_points / self.away_matches
                if self.away_matches
                else 0.0
            ),
        )


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
        states: dict[int, _TeamFormState] = {}
        backtest_predictions: list[BacktestPrediction] = []

        for _, round_matches_iterator in groupby(
            matches,
            key=lambda match: match.round_number,
        ):
            round_matches = list(round_matches_iterator)

            for match in round_matches:
                home_state = self._state_for(
                    states,
                    match.home_team_id,
                )
                away_state = self._state_for(
                    states,
                    match.away_team_id,
                )
                home_rating = home_state.rating(
                    match.home_team_id,
                    match.home_team_name,
                )
                away_rating = away_state.rating(
                    match.away_team_id,
                    match.away_team_name,
                )
                prediction = model.predict(
                    home_rating,
                    away_rating,
                )
                backtest_predictions.append(
                    BacktestPrediction(
                        match_id=match.match_id,
                        tournament_id=match.tournament_id,
                        round_number=match.round_number,
                        prediction=prediction,
                        actual_result=self._actual_result(match),
                        home_elo_before=home_rating.elo,
                        away_elo_before=away_rating.elo,
                    )
                )

            for match in round_matches:
                home_state = self._state_for(
                    states,
                    match.home_team_id,
                )
                away_state = self._state_for(
                    states,
                    match.away_team_id,
                )
                update = update_elo(
                    home_elo=home_state.elo,
                    away_elo=away_state.elo,
                    home_goals=match.home_goals,
                    away_goals=match.away_goals,
                )
                home_state.elo = update.home_elo_after
                away_state.elo = update.away_elo_after
                self._apply_form_result(
                    home_state=home_state,
                    away_state=away_state,
                    home_goals=match.home_goals,
                    away_goals=match.away_goals,
                )

        return backtest_predictions

    def _state_for(
        self,
        states: dict[int, _TeamFormState],
        team_id: int,
    ) -> _TeamFormState:
        if team_id not in states:
            states[team_id] = _TeamFormState(
                elo=self.initial_elo
            )
        return states[team_id]

    @staticmethod
    def _apply_form_result(
        home_state: _TeamFormState,
        away_state: _TeamFormState,
        home_goals: int,
        away_goals: int,
    ) -> None:
        if home_goals > away_goals:
            home_points, away_points = 3, 0
        elif home_goals < away_goals:
            home_points, away_points = 0, 3
        else:
            home_points, away_points = 1, 1

        goal_difference = home_goals - away_goals
        home_state.recent_results.append(
            (home_points, goal_difference)
        )
        away_state.recent_results.append(
            (away_points, -goal_difference)
        )
        home_state.home_points += home_points
        home_state.home_matches += 1
        away_state.away_points += away_points
        away_state.away_matches += 1

    @staticmethod
    def _actual_result(
        match: CompletedMatch,
    ) -> PredictedResult:
        if match.home_goals > match.away_goals:
            return PredictedResult.HOME
        if match.home_goals < match.away_goals:
            return PredictedResult.AWAY
        return PredictedResult.DRAW
