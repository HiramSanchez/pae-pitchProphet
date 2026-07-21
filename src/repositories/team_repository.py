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