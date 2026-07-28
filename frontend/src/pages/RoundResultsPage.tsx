import {useEffect, useState} from "react";

import {api} from "../api/client";
import {ErrorNotice, Loading, PageHeader, outcomeText} from "../components/Ui";
import type {RoundResults} from "../types";

export function RoundResultsPage() {
  const [round, setRound] = useState(1);
  const [data, setData] = useState<RoundResults>();
  const [error, setError] = useState("");

  function load(selected: number) {
    setError("");
    setData(undefined);
    api.results(selected).then(setData).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => load(1), []);

  return (
    <section>
      <PageHeader
        eyebrow="Archivo de jornadas"
        title="Lo que realmente ocurrió"
        description="Resultados oficiales y el contraste con tus decisiones personales."
      />
      <div className="round-picker">
        <label>Jornada <input type="number" min="1" max="17" value={round} onChange={(event) => setRound(Number(event.target.value))} /></label>
        <button onClick={() => load(round)}>Consultar</button>
      </div>
      {error && <ErrorNotice message={error} />}
      {!error && !data && <Loading />}
      {data && (
        <div className="results-list">
          {data.matches.map((match) => (
            <article key={match.match_id}>
              <div><strong>{match.home_team_name}</strong><span>{match.away_team_name}</span></div>
              <div className="score">{match.home_goals ?? "—"} <small>:</small> {match.away_goals ?? "—"}</div>
              <div className="result-note">
                {match.actual_result ? outcomeText[match.actual_result] : match.status}
                {match.personal_pick && <small>{match.personal_pick.points_awarded ? "✓ Acierto" : "× Error"}</small>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
