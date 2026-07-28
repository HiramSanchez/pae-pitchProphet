import type {JournalStatus, PickOutcome} from "../types";

export function canEditJournal(
  status: JournalStatus | undefined,
): boolean {
  return status === "open";
}

export function isCompleteSelection(
  matchIds: number[],
  selections: Record<number, PickOutcome>,
): boolean {
  return (
    matchIds.length > 0 &&
    matchIds.every((matchId) => Boolean(selections[matchId]))
  );
}

export const outcomeLabel: Record<PickOutcome, string> = {
  home: "Local",
  draw: "Empate",
  away: "Visitante",
};
