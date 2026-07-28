import {useEffect, useMemo, useState} from "react";

import {api} from "../api/client";
import {ErrorNotice, JournalPill, Loading, PageHeader} from "../components/Ui";
import type {NextRound, PickOutcome} from "../types";
import {canEditJournal, isCompleteSelection, outcomeLabel} from "../utils/picks";

export function PersonalPicksPage() {
  const [data, setData] = useState<NextRound>();
  const [selections, setSelections] = useState<Record<number, PickOutcome>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    api.nextRound().then((next) => {
      setData(next);
      setSelections(
        Object.fromEntries(
          next.matches
            .filter((match) => match.personal_pick)
            .map((match) => [
              match.match_id,
              match.personal_pick!.predicted_result.toLowerCase(),
            ]),
        ) as Record<number, PickOutcome>,
      );
    });

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message));
  }, []);

  const matchIds = useMemo(
    () => data?.matches.map((match) => match.match_id) ?? [],
    [data],
  );
  const editable = canEditJournal(data?.journal?.status);
  const complete = isCompleteSelection(matchIds, selections);

  async function openJournal() {
    if (!data) return;
    setError("");
    try {
      await api.openJournal(data.round_number);
      await load();
      setMessage("La quiniela está abierta.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo abrir la quiniela.");
    }
  }

  async function save() {
    if (!data) return;
    setError("");
    try {
      await api.savePicks(
        data.round_number,
        Object.entries(selections).map(([matchId, outcome]) => ({
          match_id: Number(matchId),
          predicted_outcome: outcome,
        })),
      );
      await load();
      setMessage("Tus decisiones quedaron guardadas.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudieron guardar tus decisiones.");
    }
  }

  async function finalize() {
    if (!data) return;
    setError("");
    try {
      await api.finalize(data.round_number);
      await load();
      setMessage("Quiniela confirmada. Los modelos quedaron congelados.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo confirmar la quiniela.");
    }
  }

  if (error && !data) return <ErrorNotice message={error} />;
  if (!data) return <Loading />;

  return (
    <section>
      <PageHeader
        eyebrow={`Jornada ${data.round_number}`}
        title="Tu lectura del juego"
        description="Guarda avances libremente. Confirma cuando todos los partidos reflejen tu decisión final."
      />
      <div className="journal-toolbar">
        <JournalPill status={data.journal?.status} />
        {!data.journal && <button onClick={() => void openJournal()}>Abrir quiniela</button>}
        {editable && <button className="secondary" onClick={() => void save()}>Guardar avances</button>}
        {editable && <button disabled={!complete} onClick={() => void finalize()}>Confirmar jornada</button>}
      </div>
      {error && <ErrorNotice message={error} />}
      {message && <div className="notice success">{message}</div>}
      <div className="pick-list">
        {data.matches.map((match, index) => (
          <article className="pick-row" key={match.match_id}>
            <span className="match-number">{String(index + 1).padStart(2, "0")}</span>
            <div className="pick-teams">
              <strong>{match.home_team_name}</strong>
              <span>{match.away_team_name}</span>
            </div>
            <div className="outcome-control">
              {(Object.keys(outcomeLabel) as PickOutcome[]).map((outcome) => (
                <button
                  key={outcome}
                  disabled={!editable}
                  className={selections[match.match_id] === outcome ? "selected" : ""}
                  onClick={() => setSelections((current) => ({...current, [match.match_id]: outcome}))}
                >
                  {outcomeLabel[outcome]}
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
