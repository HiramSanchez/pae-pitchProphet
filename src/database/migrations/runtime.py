import sqlite3

from src.database.migrations.evaluation_persistence import (
    migrate_evaluation_persistence_schema,
)
from src.database.migrations.prediction_persistence import (
    migrate_prediction_persistence_schema,
)
from src.database.migrations.prediction_revisions import (
    migrate_prediction_revisions_schema,
)
from src.database.migrations.team_statistics import (
    migrate_team_statistics_schema,
)
from src.database.migrations.update_pipeline import (
    migrate_update_pipeline_schema,
)
from src.database.migrations.user_prediction_journal import (
    migrate_user_prediction_journal_schema,
)
from src.database.migrations.user_prediction_model_snapshots import (
    migrate_user_prediction_model_snapshots_schema,
)


def migrate_runtime_schema(connection: sqlite3.Connection) -> None:
    migrate_team_statistics_schema(connection)
    migrate_prediction_persistence_schema(connection)
    migrate_user_prediction_journal_schema(connection)
    migrate_user_prediction_model_snapshots_schema(connection)
    migrate_prediction_revisions_schema(connection)
    migrate_evaluation_persistence_schema(connection)
    migrate_update_pipeline_schema(connection)
