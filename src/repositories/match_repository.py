import sqlite3


class MatchRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

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