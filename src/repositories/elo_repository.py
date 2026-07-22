import sqlite3

from src.models.elo import EloUpdate


class EloRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def clear_history(self) -> None:
        self.connection.execute("DELETE FROM elo_history")

    def save_match_update(
        self,
        match_id: int,
        round_number: int,
        home_team_id: int,
        away_team_id: int,
        update: EloUpdate,
    ) -> None:
        self.connection.executemany(
            """
            INSERT INTO elo_history (
                team_id, match_id, round_number, elo_before,
                elo_after, change_amount
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    home_team_id, match_id, round_number,
                    update.home_elo_before, update.home_elo_after,
                    update.home_change,
                ),
                (
                    away_team_id, match_id, round_number,
                    update.away_elo_before, update.away_elo_after,
                    update.away_change,
                ),
            ],
        )
