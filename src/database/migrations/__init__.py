from src.database.migrations.evaluation_persistence import (
    migrate_evaluation_persistence_schema,
)
from src.database.migrations.prediction_persistence import (
    migrate_prediction_persistence_schema,
)

__all__ = [
    "migrate_evaluation_persistence_schema",
    "migrate_prediction_persistence_schema",
]
