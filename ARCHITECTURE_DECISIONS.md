# PitchProphet architecture decisions

## ADR-001 — Deterministic questions remain the production boundary

- **Status:** accepted
- **Date:** 2026-07-28

Phase 18's optional LLM adapter is deferred technical debt. No provider,
model, budget, SDK, or secret is configured. The deterministic Spanish
interpreter remains the only conversational path and all structured data
continues to come from `QueryService`.

Reconsidering the adapter requires explicit approval of provider, model,
cost ceiling, and secret handling. It must retain deterministic fallback and
must never receive SQLite connections, SQL schema, or execute calculations.

## ADR-002 — Local single-process operations

- **Status:** accepted
- **Date:** 2026-07-28

PitchProphet v2 remains a local, single-user SQLite application. Connections
enforce foreign keys and use a five-second SQLite busy timeout. Update retries
operate on complete idempotent attempts. Journal finalization uses a short
savepoint so picks and frozen model snapshots transition together.

Existing databases are backed up with SQLite's online backup API before
initialization/migrations. Restores verify integrity and preserve the current
database in a separate safety backup first.

## ADR-003 — Frontend deployment boundary

- **Status:** accepted
- **Date:** 2026-07-28

The React application is built as static assets. Production environments must
provide `VITE_API_BASE_URL` at build time, serve the generated `dist`
directory with SPA fallback to `index.html`, and configure the API's allowed
origin explicitly. No production host is selected or deployed by this phase.
