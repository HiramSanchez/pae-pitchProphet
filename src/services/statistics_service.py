import sqlite3
from dataclasses import dataclass

from src.repositories.match_repository import MatchRepository
from src.repositories.team_repository import (
    TeamRepository,
    TeamStatistics,
)


@dataclass
class MutableTeamStatistics:
    team_id: int
    matches_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    home_matches: int = 0
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0
    away_matches: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    def freeze(self) -> TeamStatistics:
        return TeamStatistics(
            team_id=self.team_id,
            matches_played=self.matches_played,
            wins=self.wins,
            draws=self.draws,
            losses=self.losses,
            goals_for=self.goals_for,
            goals_against=self.goals_against,
            goal_difference=(
                self.goals_for - self.goals_against
            ),
            points=self.points,
            home_matches=self.home_matches,
            home_wins=self.home_wins,
            home_draws=self.home_draws,
            home_losses=self.home_losses,
            away_matches=self.away_matches,
            away_wins=self.away_wins,
            away_draws=self.away_draws,
            away_losses=self.away_losses,
        )


class StatisticsService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.team_repository = TeamRepository(connection)
        self.match_repository = MatchRepository(connection)
        self.connection = connection

    def recalculate_all(self) -> int:
        matches = self.match_repository.find_completed_matches()
        team_statistics = self._initialize_team_statistics()

        for match in matches:
            self._apply_match(
                statistics_by_team=team_statistics,
                home_team_id=int(match["home_team_id"]),
                away_team_id=int(match["away_team_id"]),
                home_goals=int(match["home_goals"]),
                away_goals=int(match["away_goals"]),
            )

        self.team_repository.reset_statistics()

        for statistics in team_statistics.values():
            self.team_repository.update_statistics(
                statistics.freeze()
            )

        return len(matches)

    def _initialize_team_statistics(
        self,
    ) -> dict[int, MutableTeamStatistics]:
        rows = self.connection.execute(
            """
            SELECT id
            FROM teams
            """
        ).fetchall()

        return {
            int(row["id"]): MutableTeamStatistics(
                team_id=int(row["id"])
            )
            for row in rows
        }

    @staticmethod
    def _apply_match(
        statistics_by_team: dict[int, MutableTeamStatistics],
        home_team_id: int,
        away_team_id: int,
        home_goals: int,
        away_goals: int,
    ) -> None:
        home = statistics_by_team[home_team_id]
        away = statistics_by_team[away_team_id]

        home.matches_played += 1
        away.matches_played += 1

        home.home_matches += 1
        away.away_matches += 1

        home.goals_for += home_goals
        home.goals_against += away_goals

        away.goals_for += away_goals
        away.goals_against += home_goals

        if home_goals > away_goals:
            home.wins += 1
            home.home_wins += 1
            home.points += 3

            away.losses += 1
            away.away_losses += 1

        elif home_goals < away_goals:
            away.wins += 1
            away.away_wins += 1
            away.points += 3

            home.losses += 1
            home.home_losses += 1

        else:
            home.draws += 1
            away.draws += 1

            home.home_draws += 1
            away.away_draws += 1

            home.points += 1
            away.points += 1