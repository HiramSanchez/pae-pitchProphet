import sqlite3

from src.models.prediction import PredictedResult
from src.models.user_prediction import (
    UserPickSelection,
    UserPredictionRoundStatus,
)
from src.services.personal_evaluation_service import (
    PersonalEvaluationService,
)
from src.services.personal_prediction_service import (
    PersonalPredictionService,
)
from tests.test_data_update_service import database


def _completed_round() -> sqlite3.Connection:
    connection = database()
    connection.executescript(
        """
        INSERT INTO tournaments (id, name, season)
        VALUES (1, 'Liga MX', 'Apertura 2026');
        INSERT INTO teams (id, name) VALUES (1, 'A');
        INSERT INTO teams (id, name) VALUES (2, 'B');
        INSERT INTO teams (id, name) VALUES (3, 'C');
        INSERT INTO teams (id, name) VALUES (4, 'D');
        INSERT INTO teams (id, name) VALUES (5, 'E');
        INSERT INTO teams (id, name) VALUES (6, 'F');
        INSERT INTO matches (
            id, tournament_id, round_number, home_team_id,
            away_team_id, status
        ) VALUES (1, 1, 2, 1, 2, 'scheduled');
        INSERT INTO matches (
            id, tournament_id, round_number, home_team_id,
            away_team_id, status
        ) VALUES (2, 1, 2, 3, 4, 'scheduled');
        INSERT INTO matches (
            id, tournament_id, round_number, home_team_id,
            away_team_id, status
        ) VALUES (3, 1, 2, 5, 6, 'scheduled');
        """
    )
    personal = PersonalPredictionService(connection)
    personal.open_round(1, 2)
    personal.save_picks(
        1,
        2,
        [
            UserPickSelection(1, PredictedResult.HOME),
            UserPickSelection(2, PredictedResult.DRAW),
            UserPickSelection(3, PredictedResult.HOME),
        ],
    )
    personal.finalize_round(1, 2)
    connection.executescript(
        """
        UPDATE matches
        SET status = 'completed', home_goals = 2, away_goals = 0
        WHERE id = 1;
        UPDATE matches
        SET status = 'completed', home_goals = 1, away_goals = 1
        WHERE id = 2;
        UPDATE matches
        SET status = 'completed', home_goals = 0, away_goals = 3
        WHERE id = 3;
        """
    )
    return connection


def test_evaluation_scores_home_draw_and_away_idempotently() -> None:
    connection = _completed_round()
    service = PersonalEvaluationService(connection)

    first = service.evaluate(
        {1}, "2026-08-01T12:00:00+00:00"
    )
    second = service.evaluate(
        {1}, "2026-08-01T13:00:00+00:00"
    )

    assert first.rounds_completed == 1
    assert first.picks_evaluated == 3
    assert first.picks_changed == 3
    assert second.rounds_completed == 0
    assert second.picks_evaluated == 3
    assert second.picks_changed == 0
    assert [
        tuple(row)
        for row in connection.execute(
            """
            SELECT points_awarded, evaluated_at
            FROM user_predictions ORDER BY match_id
            """
        )
    ] == [
        (1, "2026-08-01T12:00:00+00:00"),
        (1, "2026-08-01T12:00:00+00:00"),
        (0, "2026-08-01T12:00:00+00:00"),
    ]
    journal = connection.execute(
        "SELECT status, evaluated_at FROM user_prediction_rounds"
    ).fetchone()
    assert tuple(journal) == (
        UserPredictionRoundStatus.EVALUATED.value,
        "2026-08-01T12:00:00+00:00",
    )


def test_evaluation_corrects_points_after_score_correction() -> None:
    connection = _completed_round()
    service = PersonalEvaluationService(connection)
    service.evaluate({1}, "2026-08-01T12:00:00+00:00")
    connection.execute(
        "UPDATE matches SET home_goals = 0, away_goals = 1 WHERE id = 1"
    )

    corrected = service.evaluate(
        {1}, "2026-08-01T14:00:00+00:00"
    )

    row = connection.execute(
        """
        SELECT points_awarded, evaluated_at
        FROM user_predictions WHERE match_id = 1
        """
    ).fetchone()
    assert corrected.picks_changed == 1
    assert tuple(row) == (0, "2026-08-01T14:00:00+00:00")


def test_postponed_match_keeps_round_finalized() -> None:
    connection = _completed_round()
    connection.execute(
        """
        UPDATE matches
        SET status = 'postponed', home_goals = NULL, away_goals = NULL
        WHERE id = 3
        """
    )

    result = PersonalEvaluationService(connection).evaluate(
        {1}, "2026-08-01T12:00:00+00:00"
    )

    assert result.picks_evaluated == 2
    assert result.rounds_completed == 0
    assert connection.execute(
        "SELECT status FROM user_prediction_rounds"
    ).fetchone()[0] == UserPredictionRoundStatus.FINALIZED.value
