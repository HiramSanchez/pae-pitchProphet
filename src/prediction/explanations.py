from src.models.prediction import PredictedResult, Prediction


HIGH_UNCERTAINTY_GAP = 0.05
MEDIUM_UNCERTAINTY_GAP = 0.15


def build_elo_factors(
    input_snapshot: dict[str, object],
) -> list[dict[str, object]]:
    home_team = input_snapshot["home_team"]
    away_team = input_snapshot["away_team"]
    configuration = input_snapshot["model_configuration"]

    if not isinstance(home_team, dict):
        raise ValueError("Invalid home_team snapshot")
    if not isinstance(away_team, dict):
        raise ValueError("Invalid away_team snapshot")
    if not isinstance(configuration, dict):
        raise ValueError("Invalid model_configuration snapshot")

    home_elo = float(home_team["elo"])
    away_elo = float(away_team["elo"])
    elo_difference = home_elo - away_elo
    home_advantage = float(configuration["home_advantage"])

    if elo_difference > 0:
        elo_impact = "home"
        elo_description = "El equipo local tiene mayor Elo"
    elif elo_difference < 0:
        elo_impact = "away"
        elo_description = "El equipo visitante tiene mayor Elo"
    else:
        elo_impact = "neutral"
        elo_description = "Ambos equipos tienen el mismo Elo"

    return [
        {
            "factor": "elo_difference",
            "impact": elo_impact,
            "value": elo_difference,
            "description": elo_description,
        },
        {
            "factor": "home_advantage",
            "impact": "home",
            "value": home_advantage,
            "description": "Se aplicó ventaja por localía",
        },
    ]


def build_elo_form_factors(
    input_snapshot: dict[str, object],
) -> list[dict[str, object]]:
    factors = build_elo_factors(input_snapshot)
    home_team = input_snapshot["home_team"]
    away_team = input_snapshot["away_team"]
    configuration = input_snapshot["model_configuration"]

    if not isinstance(home_team, dict):
        raise ValueError("Invalid home_team snapshot")
    if not isinstance(away_team, dict):
        raise ValueError("Invalid away_team snapshot")
    if not isinstance(configuration, dict):
        raise ValueError("Invalid model_configuration snapshot")

    form_values = [
        (
            "recent_points",
            float(home_team["recent_points"])
            - float(away_team["recent_points"]),
            float(configuration["recent_points_weight"]),
            "El rendimiento reciente favorece al {team}",
        ),
        (
            "recent_goal_difference",
            float(home_team["recent_goal_difference"])
            - float(away_team["recent_goal_difference"]),
            float(
                configuration["recent_goal_difference_weight"]
            ),
            "La diferencia de goles reciente favorece al {team}",
        ),
        (
            "venue_performance",
            float(home_team["home_points_per_match"])
            - float(away_team["away_points_per_match"]),
            float(configuration["venue_performance_weight"]),
            "El rendimiento por condición favorece al {team}",
        ),
    ]

    for factor_name, value, weight, description in form_values:
        if value > 0:
            impact = "home"
            team_label = "equipo local"
        elif value < 0:
            impact = "away"
            team_label = "equipo visitante"
        else:
            impact = "neutral"
            team_label = "ningún equipo"
        factors.append(
            {
                "factor": factor_name,
                "impact": impact,
                "value": value,
                "weight": weight,
                "description": description.format(team=team_label),
            }
        )

    return factors


def build_poisson_factors(
    input_snapshot: dict[str, object],
) -> list[dict[str, object]]:
    home_team = input_snapshot["home_team"]
    away_team = input_snapshot["away_team"]
    model_output = input_snapshot.get("model_output")
    if not isinstance(home_team, dict):
        raise ValueError("Invalid home_team snapshot")
    if not isinstance(away_team, dict):
        raise ValueError("Invalid away_team snapshot")
    if not isinstance(model_output, dict):
        raise ValueError("Invalid Poisson model output snapshot")

    expected_home = float(model_output["expected_home_goals"])
    expected_away = float(model_output["expected_away_goals"])
    likely_score = model_output["most_likely_score"]
    if not isinstance(likely_score, (list, tuple)):
        raise ValueError("Invalid most_likely_score snapshot")

    return [
        {
            "factor": "expected_goals",
            "impact": (
                "home"
                if expected_home > expected_away
                else "away"
                if expected_home < expected_away
                else "neutral"
            ),
            "home_value": expected_home,
            "away_value": expected_away,
            "description": (
                "Los goles esperados son "
                f"{expected_home:.2f} a {expected_away:.2f}"
            ),
        },
        {
            "factor": "attack_defense_strength",
            "impact": "neutral",
            "home_attack": float(home_team["home_attack_strength"]),
            "away_defense": float(away_team["away_defense_strength"]),
            "away_attack": float(away_team["away_attack_strength"]),
            "home_defense": float(home_team["home_defense_strength"]),
            "description": (
                "Se combinaron fortalezas ofensivas y defensivas "
                "según la condición de local o visitante"
            ),
        },
        {
            "factor": "league_goal_averages",
            "impact": "neutral",
            "home_value": float(
                home_team["league_home_goals_average"]
            ),
            "away_value": float(
                away_team["league_away_goals_average"]
            ),
            "description": (
                "Los promedios de liga usados fueron "
                f"{float(home_team['league_home_goals_average']):.2f} "
                "como local y "
                f"{float(away_team['league_away_goals_average']):.2f} "
                "como visitante"
            ),
        },
        {
            "factor": "most_likely_score",
            "impact": "neutral",
            "value": [int(likely_score[0]), int(likely_score[1])],
            "description": (
                "El marcador más probable es "
                f"{int(likely_score[0])}-{int(likely_score[1])}"
            ),
        },
    ]


def calculate_uncertainty(prediction: Prediction) -> str:
    ranked_probabilities = sorted(
        (
            prediction.home_probability,
            prediction.draw_probability,
            prediction.away_probability,
        ),
        reverse=True,
    )
    probability_gap = (
        ranked_probabilities[0] - ranked_probabilities[1]
    )

    if probability_gap < HIGH_UNCERTAINTY_GAP:
        return "high"
    if probability_gap < MEDIUM_UNCERTAINTY_GAP:
        return "medium"
    return "low"


def alternative_result(prediction: Prediction) -> str:
    probabilities = {
        PredictedResult.HOME: prediction.home_probability,
        PredictedResult.DRAW: prediction.draw_probability,
        PredictedResult.AWAY: prediction.away_probability,
    }
    ranked_results = sorted(
        probabilities,
        key=probabilities.get,
        reverse=True,
    )
    return ranked_results[1].value.lower()
