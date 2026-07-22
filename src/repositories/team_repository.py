import sqlite3
from src.models.prediction import TeamRating
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamStatistics:
    team_id: int
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    home_matches: int
    home_wins: int
    home_draws: int
    home_losses: int
    away_matches: int
    away_wins: int
    away_draws: int
    away_losses: int


class TeamRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        
    def find_rating_by_id(
        self,
        team_id: int,
    ) -> TeamRating | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                name,
                current_elo
            FROM teams
            WHERE id = ?
            """,
            (team_id,),
        ).fetchone()

        if row is None:
            return None

        return TeamRating(
            team_id=int(row["id"]),
            name=str(row["name"]),
            elo=float(row["current_elo"]),
        )

    def find_rating_with_form(
        self,
        team_id: int,
        tournament_id: int,
        before_round: int,
    ) -> TeamRating | None:
        team = self.find_rating_by_id(team_id)
        if team is None:
            return None

        rows = self.connection.execute(
            """
            SELECT
                id,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals
            FROM matches
            WHERE tournament_id = ?
              AND round_number < ?
              AND status = 'completed'
              AND home_goals IS NOT NULL
              AND away_goals IS NOT NULL
              AND (home_team_id = ? OR away_team_id = ?)
            ORDER BY round_number DESC, id DESC
            """,
            (
                tournament_id,
                before_round,
                team_id,
                team_id,
            ),
        ).fetchall()

        recent_points = 0
        recent_goal_difference = 0
        home_points = 0
        home_matches = 0
        away_points = 0
        away_matches = 0

        for index, row in enumerate(rows):
            is_home = int(row["home_team_id"]) == team_id
            goals_for = int(
                row["home_goals"] if is_home else row["away_goals"]
            )
            goals_against = int(
                row["away_goals"] if is_home else row["home_goals"]
            )
            points = self._points(goals_for, goals_against)

            if index < 5:
                recent_points += points
                recent_goal_difference += goals_for - goals_against

            if is_home:
                home_points += points
                home_matches += 1
            else:
                away_points += points
                away_matches += 1

        return TeamRating(
            team_id=team.team_id,
            name=team.name,
            elo=team.elo,
            recent_points=float(recent_points),
            recent_goal_difference=float(
                recent_goal_difference
            ),
            home_points_per_match=(
                home_points / home_matches
                if home_matches
                else 0.0
            ),
            away_points_per_match=(
                away_points / away_matches
                if away_matches
                else 0.0
            ),
        )

    @staticmethod
    def _points(goals_for: int, goals_against: int) -> int:
        if goals_for > goals_against:
            return 3
        if goals_for == goals_against:
            return 1
        return 0

    def reset_statistics(self) -> None:
        self.connection.execute(
            """
            UPDATE teams
            SET
                matches_played = 0,
                wins = 0,
                draws = 0,
                losses = 0,
                goals_for = 0,
                goals_against = 0,
                goal_difference = 0,
                points = 0,
                home_matches = 0,
                home_wins = 0,
                home_draws = 0,
                home_losses = 0,
                away_matches = 0,
                away_wins = 0,
                away_draws = 0,
                away_losses = 0
            """
        )

    def update_statistics(
        self,
        statistics: TeamStatistics,
    ) -> None:
        self.connection.execute(
            """
            UPDATE teams
            SET
                matches_played = ?,
                wins = ?,
                draws = ?,
                losses = ?,
                goals_for = ?,
                goals_against = ?,
                goal_difference = ?,
                points = ?,
                home_matches = ?,
                home_wins = ?,
                home_draws = ?,
                home_losses = ?,
                away_matches = ?,
                away_wins = ?,
                away_draws = ?,
                away_losses = ?
            WHERE id = ?
            """,
            (
                statistics.matches_played,
                statistics.wins,
                statistics.draws,
                statistics.losses,
                statistics.goals_for,
                statistics.goals_against,
                statistics.goal_difference,
                statistics.points,
                statistics.home_matches,
                statistics.home_wins,
                statistics.home_draws,
                statistics.home_losses,
                statistics.away_matches,
                statistics.away_wins,
                statistics.away_draws,
                statistics.away_losses,
                statistics.team_id,
            ),
        )

    def find_all_ordered_by_standings(
        self,
    ) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                id,
                name,
                current_elo,
                matches_played,
                wins,
                draws,
                losses,
                goals_for,
                goals_against,
                goal_difference,
                points
            FROM teams
            ORDER BY
                points DESC,
                goal_difference DESC,
                goals_for DESC,
                name ASC
            """
        ).fetchall()
