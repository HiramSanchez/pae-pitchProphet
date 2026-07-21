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
