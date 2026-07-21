import sqlite3

from src.models.match import ScheduledMatch


class MatchRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_scheduled_by_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[ScheduledMatch]:
        rows = self.connection.execute(
            """
            SELECT
                m.id AS match_id,
                m.tournament_id,
                m.round_number,
                m.home_team_id,
                home_team.name AS home_team_name,
                m.away_team_id,
                away_team.name AS away_team_name
            FROM matches m
            INNER JOIN teams home_team
                ON home_team.id = m.home_team_id
            INNER JOIN teams away_team
                ON away_team.id = m.away_team_id
            WHERE m.tournament_id = ?
              AND m.round_number = ?
              AND m.status = 'scheduled'
            ORDER BY m.id
            """,
            (
                tournament_id,
                round_number,
            ),
        ).fetchall()

        return [
            ScheduledMatch(
                match_id=int(row["match_id"]),
                tournament_id=int(row["tournament_id"]),
                round_number=int(row["round_number"]),
                home_team_id=int(row["home_team_id"]),
                home_team_name=str(row["home_team_name"]),
                away_team_id=int(row["away_team_id"]),
                away_team_name=str(row["away_team_name"]),
            )
            for row in rows
        ]

    def find_completed_matches(
        self,
    ) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT
                id,
                tournament_id,
                round_number,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals
            FROM matches
            WHERE status = 'completed'
              AND home_goals IS NOT NULL
              AND away_goals IS NOT NULL
            ORDER BY
                round_number ASC,
                id ASC
            """
        ).fetchall()
