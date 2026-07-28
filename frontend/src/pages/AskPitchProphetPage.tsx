import {FormEvent, useState} from "react";

import {api} from "../api/client";
import {ErrorNotice, PageHeader} from "../components/Ui";
import type {QueryAnswer} from "../types";

const suggestions = [
  "¿Cuál es la siguiente jornada?",
  "¿Cómo me fue en la jornada 1?",
  "¿Cuál es mi efectividad?",
  "¿Cómo voy contra los modelos?",
];

export function AskPitchProphetPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<QueryAnswer>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    try {
      setAnswer(await api.ask(question));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <PageHeader
        eyebrow="Consulta determinística"
        title="Pregunta con intención"
        description="Respuestas en español construidas exclusivamente con datos persistidos de PitchProphet."
      />
      <div className="ask-panel">
        <form onSubmit={(event) => void submit(event)}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Escribe tu pregunta sobre jornadas, pronósticos o rendimiento…"
          />
          <button disabled={loading || !question.trim()}>
            {loading ? "Consultando…" : "Preguntar"}
          </button>
        </form>
        <div className="suggestions">
          {suggestions.map((suggestion) => (
            <button key={suggestion} onClick={() => setQuestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
        {error && <ErrorNotice message={error} />}
        {answer && (
          <article className="answer-card">
            <span className="eyebrow">{answer.intent}</span>
            <h2>{answer.message}</h2>
            <pre>{JSON.stringify(answer.data, null, 2)}</pre>
          </article>
        )}
      </div>
    </section>
  );
}
