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


@dataclass(frozen=True)
class CompletedMatch:
    match_id: int
    tournament_id: int
    round_number: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_goals: int
    away_goals: int
    match_date: str | None = None


@dataclass(frozen=True)
class ExternalMatch:
    external_match_id: str
    tournament_name: str
    season: str
    round_number: int
    home_team_name: str
    away_team_name: str
    status: str
    match_date: str | None = None
    home_goals: int | None = None
    away_goals: int | None = None

    def __post_init__(self) -> None:
        if not self.external_match_id.strip():
            raise ValueError("external_match_id is required")
        if self.round_number <= 0:
            raise ValueError("round_number must be positive")
        if self.status not in {
            "scheduled", "completed", "postponed", "cancelled"
        }:
            raise ValueError("Invalid match status")
        has_both_scores = (
            self.home_goals is not None and self.away_goals is not None
        )
        if self.status == "completed" and not has_both_scores:
            raise ValueError("Completed matches require both scores")
        if (self.home_goals is None) != (self.away_goals is None):
            raise ValueError("Scores must both be present or absent")
