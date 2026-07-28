import type {
  Journal,
  ModelComparison,
  NextRound,
  PersonalPerformance,
  PickOutcome,
  QueryAnswer,
  RoundResults,
} from "../types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
export const TOURNAMENT_ID = 1;

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(
      payload.detail ?? `La solicitud falló (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  nextRound: () =>
    request<NextRound>(
      `/tournaments/${TOURNAMENT_ID}/rounds/next`,
    ),
  openJournal: (round: number) =>
    request<{journal: Journal}>(
      `/tournaments/${TOURNAMENT_ID}/rounds/${round}/journal`,
      {method: "POST"},
    ),
  savePicks: (
    round: number,
    picks: Array<{match_id: number; predicted_outcome: PickOutcome}>,
  ) =>
    request(
      `/tournaments/${TOURNAMENT_ID}/rounds/${round}/picks`,
      {method: "PUT", body: JSON.stringify({picks})},
    ),
  finalize: (round: number) =>
    request(
      `/tournaments/${TOURNAMENT_ID}/rounds/${round}/finalize`,
      {method: "POST"},
    ),
  results: (round: number) =>
    request<RoundResults>(
      `/tournaments/${TOURNAMENT_ID}/rounds/${round}/results`,
    ),
  performance: () =>
    request<PersonalPerformance>(
      `/tournaments/${TOURNAMENT_ID}/performance/personal`,
    ),
  comparison: () =>
    request<ModelComparison>(
      `/tournaments/${TOURNAMENT_ID}/performance/comparison`,
    ),
  ask: (question: string) =>
    request<QueryAnswer>("/queries", {
      method: "POST",
      body: JSON.stringify({
        question,
        tournament_id: TOURNAMENT_ID,
      }),
    }),
};
