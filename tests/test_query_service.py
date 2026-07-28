from src.data_sources.manual_source import ManualMatchDataSource
from src.services.data_update_service import DataUpdateService
from src.services.query_service import QueryService
from tests.test_data_update_service import database, matches
from src.models.prediction import PredictedResult
from src.models.user_prediction import UserPickSelection
from src.services.personal_prediction_service import (
    PersonalPredictionService,
)


def test_query_service_answers_prediction_and_performance_queries() -> None:
    connection = database()
    DataUpdateService(connection).run(ManualMatchDataSource(matches()))
    service = QueryService(connection)

    best = service.get_best_predictions_for_next_round(1)
    draws = service.get_highest_draw_probabilities(1, limit=2)
    comparison = service.compare_models_for_match(best[0].prediction.match_id)
    explanation = service.get_prediction_explanation(
        best[0].prediction.match_id, "ensemble", "1.0.0"
    )
    best_model = service.get_best_performing_model(1)

    assert len(best) == 1
    assert best[0].prediction.model_name == "ensemble"
    assert 0 < best[0].agreement_ratio <= 1
    assert len(draws) == 2
    assert draws[0].prediction.draw_probability >= (
        draws[1].prediction.draw_probability
    )
    assert comparison is not None
    assert len(comparison.predictions) == 4
    assert set(comparison.probability_ranges) == {"home", "draw", "away"}
    assert explanation is not None
    assert explanation.explanation["main_factors"]
    assert best_model is not None


def test_changed_predictions_compare_latest_revision_without_recalculation() -> None:
    connection = database()
    updater = DataUpdateService(connection)
    updater.run(ManualMatchDataSource(matches(home_goals=2)))
    updater.run(ManualMatchDataSource(matches(home_goals=1)))
    service = QueryService(connection)

    changes = service.get_changed_predictions(tournament_id=1)
    recent = service.get_recent_model_performance(
        "elo", "1.0.0", 1, limit=10
    )

    assert len(changes) == 4
    assert all(change.previous.prediction_id == change.current.prediction_id
               for change in changes)
    assert all(set(change.probability_deltas) == {"home", "draw", "away"}
               for change in changes)
    assert len(recent) == 2
    assert recent[0].evaluated_at >= recent[1].evaluated_at


def test_query_service_returns_empty_results_without_data() -> None:
    service = QueryService(database())

    assert service.get_best_predictions_for_next_round(999) == []
    assert service.get_highest_draw_probabilities(999) == []
    assert service.compare_models_for_match(999) is None
    assert service.get_best_performing_model(999) is None
    assert service.get_changed_predictions(999) == []


def test_query_service_returns_personal_journal_data() -> None:
    connection = database()
    DataUpdateService(connection).run(ManualMatchDataSource(matches()))
    personal = PersonalPredictionService(connection)
    personal.open_round(1, 2)
    match_id = connection.execute(
        "SELECT id FROM matches WHERE status = 'scheduled'"
    ).fetchone()[0]
    personal.save_picks(
        1,
        2,
        [UserPickSelection(match_id, PredictedResult.HOME)],
    )

    service = QueryService(connection)

    assert service.get_personal_prediction_round(1, 2) is not None
    assert len(service.get_personal_predictions_for_round(1, 2)) == 1
