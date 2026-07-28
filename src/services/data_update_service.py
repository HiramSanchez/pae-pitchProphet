import sqlite3
from dataclasses import dataclass

from src.data_sources.base import MatchDataSource
from src.prediction.default_models import default_model_registry
from src.repositories.match_repository import MatchRepository
from src.repositories.update_run_repository import UpdateRunRepository
from src.services.elo_processing_service import DerivedStateService
from src.services.evaluation_history_service import EvaluationHistoryService
from src.services.prediction_service import PredictionService
from src.services.personal_evaluation_service import (
    PersonalEvaluationService,
)


@dataclass(frozen=True)
class DataUpdateResult:
    run_id: int
    matches_added: int
    matches_updated: int
    predictions_generated: int


class DataUpdateService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.matches = MatchRepository(connection)
        self.runs = UpdateRunRepository(connection)

    def run(self, source: MatchDataSource) -> DataUpdateResult:
        run_id = self.runs.start()
        self.connection.commit()
        self.connection.execute("SAVEPOINT functional_update")
        try:
            sync = self.matches.synchronize(
                source.name, source.fetch_matches()
            )
            DerivedStateService(self.connection).rebuild()
            PersonalEvaluationService(self.connection).evaluate(
                set(sync.tournament_ids)
            )
            registry = default_model_registry()
            prediction_count_before = int(
                self.connection.execute(
                    "SELECT COUNT(1) FROM predictions"
                ).fetchone()[0]
            )
            for tournament_id in sorted(sync.tournament_ids):
                for model in registry.list_active():
                    EvaluationHistoryService(self.connection).evaluate(
                        model, tournament_id
                    )
                round_number = self.matches.find_next_scheduled_round(
                    tournament_id
                )
                if round_number is not None:
                    for model in registry.list_active():
                        PredictionService(
                            self.connection, model=model
                        ).predict_round(
                            tournament_id,
                            round_number,
                            refresh_scheduled=True,
                        )
            predictions_generated = int(
                self.connection.execute(
                    "SELECT COUNT(1) FROM predictions"
                ).fetchone()[0]
            ) - prediction_count_before
            self.connection.execute("RELEASE functional_update")
            self.runs.succeed(
                run_id, sync.added, sync.updated, predictions_generated
            )
            self.connection.commit()
            return DataUpdateResult(
                run_id, sync.added, sync.updated, predictions_generated
            )
        except Exception as error:
            self.connection.execute("ROLLBACK TO functional_update")
            self.connection.execute("RELEASE functional_update")
            self.runs.fail(run_id, error)
            self.connection.commit()
            raise
