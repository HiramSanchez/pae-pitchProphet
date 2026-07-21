from dataclasses import dataclass

from src.models.prediction import Prediction


@dataclass(frozen=True)
class ScheduledMatch:
    match_id: int
    tournament_id: int
    round_number: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str


@dataclass(frozen=True)
class MatchPrediction:
    match_id: int
    tournament_id: int
    round_number: int
    home_team_name: str
    away_team_name: str
    prediction: Prediction
    explanation: dict[str, object] | None = None
