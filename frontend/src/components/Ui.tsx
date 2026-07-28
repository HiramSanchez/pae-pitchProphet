import type {CSSProperties} from "react";

import type {JournalStatus, Outcome} from "../types";

export function PageHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="page-header">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

export function Loading() {
  return <div className="notice">Consultando el motor de PitchProphet…</div>;
}

export function ErrorNotice({message}: {message: string}) {
  return <div className="notice error">{message}</div>;
}

export function JournalPill({
  status,
}: {
  status?: JournalStatus;
}) {
  const label = {
    open: "Abierta",
    finalized: "Confirmada",
    evaluated: "Evaluada",
  }[status ?? "open"];
  return (
    <span className={`status-pill ${status ?? "not-open"}`}>
      {status ? label : "Sin abrir"}
    </span>
  );
}

export const outcomeText: Record<Outcome, string> = {
  HOME: "Local",
  DRAW: "Empate",
  AWAY: "Visitante",
};

export function AccuracyRing({value}: {value: number}) {
  const percent = Math.round(value * 100);
  return (
    <div
      className="accuracy-ring"
      style={{"--accuracy": `${percent * 3.6}deg`} as CSSProperties}
    >
      <strong>{percent}%</strong>
      <span>efectividad</span>
    </div>
  );
}
