import sqlite3

from src.config import DEFAULT_ELO
from src.repositories.elo_repository import EloRepository
from src.repositories.match_repository import MatchRepository
from src.repositories.team_repository import TeamRepository
from src.services.elo_service import update_elo
from src.services.statistics_service import StatisticsService


class DerivedStateService:
    """Atomically rebuilds all state derived from completed matches."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.matches = MatchRepository(connection)
        self.teams = TeamRepository(connection)
        self.elo_history = EloRepository(connection)
        self.statistics = StatisticsService(connection)

    def rebuild(self) -> int:
        matches = self.matches.find_completed_matches()
        self.teams.reset_ratings(DEFAULT_ELO)
        self.elo_history.clear_history()
        ratings = {
            int(row["id"]): DEFAULT_ELO
            for row in self.connection.execute("SELECT id FROM teams")
        }
        for match in matches:
            home_id = int(match["home_team_id"])
            away_id = int(match["away_team_id"])
            update = update_elo(
                ratings[home_id],
                ratings[away_id],
                int(match["home_goals"]),
                int(match["away_goals"]),
            )
            ratings[home_id] = update.home_elo_after
            ratings[away_id] = update.away_elo_after
            self.teams.update_rating(home_id, update.home_elo_after)
            self.teams.update_rating(away_id, update.away_elo_after)
            self.elo_history.save_match_update(
                int(match["id"]), int(match["round_number"]),
                home_id, away_id, update,
            )
        self.statistics.recalculate_all()
        return len(matches)
