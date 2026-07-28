import {useEffect, useState} from "react";

import {api} from "../api/client";
import {ErrorNotice, Loading, PageHeader, outcomeText} from "../components/Ui";
import type {NextRound} from "../types";

export function NextRoundPage() {
  const [data, setData] = useState<NextRound>();
  const [error, setError] = useState("");

  useEffect(() => {
    api.nextRound().then(setData).catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <ErrorNotice message={error} />;
  if (!data) return <Loading />;

  return (
    <section>
      <PageHeader
        eyebrow={`Liga MX · Jornada ${data.round_number}`}
        title="El siguiente capítulo"
        description="Pronósticos persistidos para todos los partidos programados antes de tomar tu decisión."
      />
      <div className="summary-strip">
        <div><strong>{data.matches.length}</strong><span>partidos</span></div>
        <div><strong>{data.matches.reduce((n, match) => n + match.predictions.length, 0)}</strong><span>pronósticos</span></div>
        <div><strong>4</strong><span>modelos</span></div>
      </div>
      <div className="match-grid">
        {data.matches.map((match) => {
          const ensemble = match.predictions.find(
            (item) => item.model_name === "ensemble",
          );
          return (
            <article className="match-card" key={match.match_id}>
              <div className="match-meta">
                <span>Partido {match.match_id}</span>
                <span>{match.status}</span>
              </div>
              <div className="teams">
                <strong>{match.home_team_name}</strong>
                <span>vs</span>
                <strong>{match.away_team_name}</strong>
              </div>
              {ensemble ? (
                <>
                  <div className="probabilities">
                    <span><b>{Math.round(ensemble.prediction.home_probability * 100)}%</b> Local</span>
                    <span><b>{Math.round(ensemble.prediction.draw_probability * 100)}%</b> Empate</span>
                    <span><b>{Math.round(ensemble.prediction.away_probability * 100)}%</b> Visita</span>
                  </div>
                  <div className="prediction-call">
                    Ensemble favorece: <strong>{outcomeText[ensemble.prediction.predicted_result]}</strong>
                  </div>
                </>
              ) : <p className="muted">Sin predicción Ensemble.</p>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
