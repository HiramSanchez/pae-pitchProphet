import {useEffect, useState} from "react";

import {api} from "../api/client";
import {AccuracyRing, ErrorNotice, Loading, PageHeader} from "../components/Ui";
import type {ModelComparison, PersonalPerformance} from "../types";

export function PerformancePage() {
  const [personal, setPersonal] = useState<PersonalPerformance>();
  const [comparison, setComparison] = useState<ModelComparison>();
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.performance(), api.comparison()])
      .then(([mine, models]) => {
        setPersonal(mine);
        setComparison(models);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <ErrorNotice message={error} />;
  if (!personal || !comparison) return <Loading />;

  return (
    <section>
      <PageHeader
        eyebrow="Marcador acumulado"
        title="Tu criterio frente al motor"
        description="Accuracy categórica sobre partidos reales; la comparación usa exactamente el mismo conjunto."
      />
      <div className="performance-hero">
        <AccuracyRing value={personal.accuracy} />
        <div>
          <span className="eyebrow">Histórico personal</span>
          <h2>{personal.correct} aciertos de {personal.evaluated_matches}</h2>
          <p>La Jornada 1 cuenta en tu historial. La comparación comienza con quinielas v2 que tengan snapshots.</p>
        </div>
      </div>
      <div className="leaderboard">
        <div className="leaderboard-head"><span>Participante</span><span>Aciertos</span><span>Accuracy</span></div>
        {comparison.participants.length === 0 ? (
          <div className="empty-state">Finaliza tu primera quiniela v2 para iniciar la comparación.</div>
        ) : comparison.participants.map((participant, index) => (
          <div className="leaderboard-row" key={participant.name}>
            <span><b>{String(index + 1).padStart(2, "0")}</b>{participant.name}</span>
            <span>{participant.correct}/{comparison.evaluated_matches}</span>
            <strong>{Math.round(participant.accuracy * 100)}%</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
