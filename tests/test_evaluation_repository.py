import sqlite3

from src.database.migrations import (
    migrate_evaluation_persistence_schema,
)
from src.models.evaluation import ModelEvaluation
from src.repositories.evaluation_repository import EvaluationRepository


def evaluation(
    model_name: str,
    log_loss: float,
) -> ModelEvaluation:
    return ModelEvaluation(
        model_name=model_name,
        model_version="1.0.0",
        tournament_id=1,
        evaluated_matches=10,
        log_loss=log_loss,
        brier_score=0.4,
        accuracy=0.5,
        top_two_accuracy=0.8,
        calibration_error=0.1,
        confusion_matrix={},
        evaluated_at="2026-07-21T12:00:00+00:00",
    )


def test_migration_is_idempotent() -> None:
    connection = sqlite3.connect(":memory:")

    migrate_evaluation_persistence_schema(connection)
    migrate_evaluation_persistence_schema(connection)

    table_count = connection.execute(
        """
        SELECT COUNT(1)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'model_evaluations'
        """
    ).fetchone()[0]
    assert table_count == 1

    connection.close()


def test_save_and_ranking_order_by_lowest_log_loss() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate_evaluation_persistence_schema(connection)
    repository = EvaluationRepository(connection)

    repository.save(evaluation("worse", 0.9))
    best = repository.save(evaluation("best", 0.5))

    ranking = repository.find_ranking(tournament_id=1)

    assert best.evaluation_id is not None
    assert [item.model_name for item in ranking] == [
        "best",
        "worse",
    ]

    connection.close()
