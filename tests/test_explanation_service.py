from src.models.prediction import TeamRating, VersionedPrediction
from src.prediction.elo_form_model import EloFormPredictionModel
from src.prediction.elo_model import EloPredictionModel
from src.prediction.poisson_model import PoissonPredictionModel
from src.services.explanation_service import ExplanationService


def versioned_prediction(
    home_elo: float,
    away_elo: float,
    *,
    home_advantage: float = 80.0,
) -> VersionedPrediction:
    model = EloPredictionModel(
        home_advantage=home_advantage
    )
    home_team = TeamRating(1, "Local", home_elo)
    away_team = TeamRating(2, "Visitante", away_elo)
    prediction = model.predict(home_team, away_team)

    return VersionedPrediction(
        match_id=1,
        model_name=model.name,
        model_version=model.version,
        configuration=model.configuration,
        prediction=prediction,
        input_snapshot={
            "home_team": {"team_id": 1, "elo": home_elo},
            "away_team": {"team_id": 2, "elo": away_elo},
            "model_configuration": model.configuration,
            "generated_at": "2026-07-21T12:00:00+00:00",
        },
        created_at="2026-07-21T12:00:00+00:00",
    )


def factor_by_name(
    explanation: dict[str, object],
    factor_name: str,
) -> dict[str, object]:
    factors = explanation["main_factors"]
    assert isinstance(factors, list)

    return next(
        factor
        for factor in factors
        if isinstance(factor, dict)
        and factor["factor"] == factor_name
    )


def test_explains_home_favorite_from_snapshot() -> None:
    versioned = versioned_prediction(1800.0, 1300.0)

    explanation = ExplanationService().generate(versioned)
    elo_factor = factor_by_name(
        explanation,
        "elo_difference",
    )
    home_factor = factor_by_name(
        explanation,
        "home_advantage",
    )

    assert elo_factor["impact"] == "home"
    assert elo_factor["value"] == 500.0
    assert home_factor["value"] == 80.0
    assert explanation["uncertainty"] == "low"


def test_explains_away_favorite_from_snapshot() -> None:
    versioned = versioned_prediction(1300.0, 1800.0)

    explanation = ExplanationService().generate(versioned)
    elo_factor = factor_by_name(
        explanation,
        "elo_difference",
    )

    assert elo_factor["impact"] == "away"
    assert elo_factor["value"] == -500.0
    assert explanation["alternative_result"] in {
        "home",
        "draw",
    }


def test_balanced_match_has_high_uncertainty() -> None:
    versioned = versioned_prediction(
        1500.0,
        1500.0,
        home_advantage=0.0,
    )

    explanation = ExplanationService().generate(versioned)
    elo_factor = factor_by_name(
        explanation,
        "elo_difference",
    )

    assert elo_factor["impact"] == "neutral"
    assert explanation["uncertainty"] == "high"


def test_explanation_has_readable_spanish_output() -> None:
    versioned = versioned_prediction(1500.0, 1500.0)
    service = ExplanationService()
    explanation = service.generate(versioned)

    text = service.to_spanish(explanation)

    assert "mismo Elo" in text
    assert "ventaja por localía" in text
    assert "Incertidumbre" in text
    assert "Resultado alternativo" in text


def test_elo_form_explanation_contains_snapshot_factors() -> None:
    model = EloFormPredictionModel()
    home_team = TeamRating(
        1,
        "Local",
        1500.0,
        recent_points=12.0,
        recent_goal_difference=5.0,
        home_points_per_match=2.5,
    )
    away_team = TeamRating(
        2,
        "Visitante",
        1500.0,
        recent_points=6.0,
        recent_goal_difference=-1.0,
        away_points_per_match=1.0,
    )
    versioned = VersionedPrediction(
        match_id=1,
        model_name=model.name,
        model_version=model.version,
        configuration=model.configuration,
        prediction=model.predict(home_team, away_team),
        input_snapshot={
            "home_team": {
                "team_id": 1,
                "elo": 1500.0,
                "recent_points": 12.0,
                "recent_goal_difference": 5.0,
                "home_points_per_match": 2.5,
                "away_points_per_match": 0.0,
            },
            "away_team": {
                "team_id": 2,
                "elo": 1500.0,
                "recent_points": 6.0,
                "recent_goal_difference": -1.0,
                "home_points_per_match": 0.0,
                "away_points_per_match": 1.0,
            },
            "model_configuration": model.configuration,
            "generated_at": "2026-07-21T12:00:00+00:00",
        },
        created_at="2026-07-21T12:00:00+00:00",
    )

    explanation = ExplanationService().generate(versioned)

    assert factor_by_name(
        explanation,
        "recent_points",
    )["value"] == 6.0
    assert factor_by_name(
        explanation,
        "recent_goal_difference",
    )["value"] == 6.0
    assert factor_by_name(
        explanation,
        "venue_performance",
    )["value"] == 1.5


def test_poisson_explanation_uses_reproducible_output() -> None:
    model = PoissonPredictionModel()
    home = TeamRating(1, "Local", 1500.0)
    away = TeamRating(2, "Visitante", 1500.0)
    prediction = model.predict(home, away)
    versioned = VersionedPrediction(
        match_id=1,
        model_name=model.name,
        model_version=model.version,
        configuration=model.configuration,
        prediction=prediction,
        input_snapshot={
            "home_team": {
                "team_id": 1,
                "home_attack_strength": 1.0,
                "home_defense_strength": 1.0,
                "league_home_goals_average": 1.4,
            },
            "away_team": {
                "team_id": 2,
                "away_attack_strength": 1.0,
                "away_defense_strength": 1.0,
                "league_away_goals_average": 1.1,
            },
            "model_configuration": model.configuration,
            "model_output": {
                "expected_home_goals": prediction.expected_home_goals,
                "expected_away_goals": prediction.expected_away_goals,
                "most_likely_score": prediction.most_likely_score,
                "score_matrix": prediction.score_matrix,
            },
        },
        created_at="2026-07-21T12:00:00+00:00",
    )

    service = ExplanationService()
    explanation = service.generate(versioned)

    assert factor_by_name(
        explanation, "expected_goals"
    )["home_value"] == 1.4
    assert factor_by_name(
        explanation, "most_likely_score"
    )["value"] == [1, 1]
    assert factor_by_name(
        explanation, "league_goal_averages"
    )["away_value"] == 1.1
    assert "marcador más probable" in service.to_spanish(explanation)
