import math

import pytest

from src.models.evaluation import BacktestPrediction
from src.models.prediction import (
    PredictedResult,
    Prediction,
)
from src.prediction.elo_model import EloPredictionModel
from src.services.evaluation_service import EvaluationService


def backtest_predictions() -> list[BacktestPrediction]:
    return [
        BacktestPrediction(
            match_id=1,
            tournament_id=1,
            round_number=1,
            prediction=Prediction(
                home_team_id=1,
                away_team_id=2,
                home_probability=0.7,
                draw_probability=0.2,
                away_probability=0.1,
                predicted_result=PredictedResult.HOME,
            ),
            actual_result=PredictedResult.HOME,
            home_elo_before=1500.0,
            away_elo_before=1500.0,
        ),
        BacktestPrediction(
            match_id=2,
            tournament_id=1,
            round_number=1,
            prediction=Prediction(
                home_team_id=3,
                away_team_id=4,
                home_probability=0.1,
                draw_probability=0.6,
                away_probability=0.3,
                predicted_result=PredictedResult.DRAW,
            ),
            actual_result=PredictedResult.DRAW,
            home_elo_before=1500.0,
            away_elo_before=1500.0,
        ),
    ]


def test_metrics_match_known_values() -> None:
    evaluation = EvaluationService().evaluate(
        model=EloPredictionModel(),
        tournament_id=1,
        backtest_predictions=backtest_predictions(),
        evaluated_at="2026-07-21T12:00:00+00:00",
    )

    assert evaluation.log_loss == pytest.approx(
        (-math.log(0.7) - math.log(0.6)) / 2
    )
    assert evaluation.brier_score == pytest.approx(0.2)
    assert evaluation.accuracy == 1.0
    assert evaluation.top_two_accuracy == 1.0
    assert evaluation.calibration_error == pytest.approx(0.35)
    assert evaluation.confusion_matrix == {
        "HOME": {"HOME": 1, "DRAW": 0, "AWAY": 0},
        "DRAW": {"HOME": 0, "DRAW": 1, "AWAY": 0},
        "AWAY": {"HOME": 0, "DRAW": 0, "AWAY": 0},
    }


def test_top_two_accuracy_excludes_lowest_probability() -> None:
    item = backtest_predictions()[0]
    missed = BacktestPrediction(
        match_id=item.match_id,
        tournament_id=item.tournament_id,
        round_number=item.round_number,
        prediction=item.prediction,
        actual_result=PredictedResult.AWAY,
        home_elo_before=item.home_elo_before,
        away_elo_before=item.away_elo_before,
    )

    assert EvaluationService.top_two_accuracy([missed]) == 0.0


def test_evaluation_rejects_empty_predictions() -> None:
    with pytest.raises(ValueError, match="At least one"):
        EvaluationService().evaluate(
            EloPredictionModel(),
            1,
            [],
        )
