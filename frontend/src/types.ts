export type Outcome = "HOME" | "DRAW" | "AWAY";
export type PickOutcome = "home" | "draw" | "away";
export type JournalStatus = "open" | "finalized" | "evaluated";

export interface Prediction {
  home_probability: number;
  draw_probability: number;
  away_probability: number;
  predicted_result: Outcome;
}

export interface PredictionView {
  prediction_id: number;
  match_id: number;
  model_name: string;
  model_version: string;
  prediction: Prediction;
  confidence: number;
  explanation?: {
    uncertainty?: string;
    main_factors?: Array<{description?: string}>;
  };
}

export interface PersonalPick {
  prediction_id: number;
  match_id: number;
  predicted_result: Outcome;
  points_awarded: number | null;
}

export interface Journal {
  round_id: number;
  tournament_id: number;
  round_number: number;
  status: JournalStatus;
}

export interface ProductMatch {
  match_id: number;
  home_team_name: string;
  away_team_name: string;
  status: string;
  match_date: string | null;
  personal_pick: PersonalPick | null;
  predictions: PredictionView[];
}

export interface NextRound {
  tournament_id: number;
  round_number: number;
  journal: Journal | null;
  matches: ProductMatch[];
}

export interface RoundResultMatch {
  match_id: number;
  home_team_name: string;
  away_team_name: string;
  status: string;
  home_goals: number | null;
  away_goals: number | null;
  actual_result: Outcome | null;
  personal_pick: PersonalPick | null;
}

export interface RoundResults {
  tournament_id: number;
  round_number: number;
  journal: Journal | null;
  matches: RoundResultMatch[];
}

export interface PersonalPerformance {
  tournament_id: number;
  evaluated_matches: number;
  correct: number;
  accuracy: number;
}

export interface PerformanceParticipant {
  name: string;
  correct: number;
  accuracy: number;
}

export interface ModelComparison {
  tournament_id: number;
  evaluated_matches: number;
  participants: PerformanceParticipant[];
}

export interface QueryAnswer {
  intent: string;
  message: string;
  data: unknown;
}
