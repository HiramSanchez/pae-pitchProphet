# PitchProphet agent guide

## Purpose and sources of truth

PitchProphet imports football fixtures/results, maintains standings and Elo,
produces reproducible predictions with multiple models, evaluates them, and
serves structured explanations and queries. Code and tests define implemented
behavior. `PLAN.md` is the phased roadmap; consult only the relevant phase and
this guide instead of re-reading the whole repository for routine work.

## Current architecture

- `src/models`: domain data and pure Elo math; no SQLite or orchestration.
- `src/prediction`: pure prediction models, registry, ensemble, and
  deterministic explanation factors. Models depend only on domain/config.
- `src/repositories`: all application SQLite queries and row mapping.
- `src/services`: orchestration of repositories and pure domain/prediction
  logic. Keep formulas out unless they are service-specific coordination.
- `src/database`: connections and idempotent schema migrations.
- `src/data_sources`: reserved for Phase 9 input adapters; sources return
  canonical domain data and never write SQLite.
- `src/query`: reserved for structured read use cases; must use services or
  repositories, never raw SQLite outside repositories.
- `src/api`: reserved for the HTTP/conversational boundary. It validates and
  translates requests but does not calculate predictions or query SQLite.
- `scripts`: thin CLI composition roots. Do not place reusable business rules
  here.
- `tests`: unit tests plus SQLite integration tests using in-memory databases.

Allowed dependency direction:

```text
api/scripts -> services -> repositories -> database
                     |-> prediction -> models
data_sources -> models
```

Predictive models must never depend on services, repositories, SQLite, HTTP,
or external APIs. Repositories must not depend on services.

## Public contracts to preserve

- `PredictionModel`: `name`, `version`, numeric `configuration`, and
  `predict(home_team, away_team) -> Prediction`.
- `PredictionService.predict`, `predict_from_ratings`, and `predict_round`.
- `MatchRepository.find_scheduled_by_round`, `find_completed_matches`, and
  `find_completed_by_tournament`.
- `PredictionRepository` preserves immutable predictions identified by
  `(match_id, model_name, model_version)`; configuration mismatches are errors.
- `TeamRepository.find_rating_with_form` remains a compatibility alias for
  `find_prediction_features`.
- Model identities and versions: `elo`, `elo_form`, `poisson`, and `ensemble`,
  currently `1.0.0`. Do not change behavior without versioning when persisted
  reproducibility would be affected.

## Persistence

Core SQLite entities are `tournaments`, `teams`, `matches`, and `elo_history`.
`matches` uses `round_number`, `home_goals`, `away_goals`, and statuses
`scheduled`, `completed`, `postponed`, or `cancelled`. Its current natural
uniqueness is tournament, round, home team, and away team. Team statistics are
stored on `teams` and rebuilt from completed matches.

Approved migrations add/upgrade `user_predictions`, `model_versions`,
`predictions`, and `model_evaluations`. Versioned predictions store model,
version, numeric configuration, probabilities, confidence, input snapshot,
structured explanation, and creation time. Poisson and ensemble extended
outputs live in `input_snapshot_json.model_output`; do not add columns for
them. Never assume the local real database has already run every migration:
inspect `PRAGMA table_info` before schema-sensitive changes.

Any schema change requires an idempotent migration, in-memory migration tests,
and a documented compatibility/recovery path. Never mutate `data/liga_mx.db`
during tests or exploratory checks; open it with SQLite `mode=ro`.

## Established decisions

- Elo math has one implementation of `expected_score` in `src/models/elo.py`;
  the service re-export is transitional compatibility only.
- `PredictionService` is an orchestrator and accepts an optional model.
- Walk-forward evaluation predicts a whole round before incorporating its
  results, preventing temporal leakage.
- Poisson uses smoothed venue-specific attack/defense inputs, league priors
  1.4/1.1 over five matches, and a normalized score matrix from 0 through 10.
- The registry is in memory and identifies models by `(name, version)`; all
  registered models are active.
- Ensemble is pure, receives explicit positive finite weights, normalizes them,
  and persists component configurations/probabilities. Automatic weight
  selection belongs in orchestration, not the model.
- Explanations are deterministic and derived from snapshots, never invented by
  an LLM.
- Prefer simple concrete implementations; do not add unused abstractions or
  speculative extension points.

## Commands

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.initialize_database
python -m pytest
python -m scripts.predict_round <tournament_id> <round_number>
python -m scripts.backtest_models <tournament_id>
python -m scripts.evaluate_models <tournament_id>
```

Use `python -m ...` for project scripts. Use `rg`/`rg --files` for searches.

## Code and test rules

- Pythonic, consistently typed code; clear names, small focused methods, no
  dead code or duplicated business rules.
- Apply SOLID only where it simplifies an active use case.
- Validate mathematical invariants inside predictive models and persistence or
  input invariants at their boundaries.
- Test behavior, not implementation. New model logic gets isolated unit tests;
  repository/migration flows use in-memory SQLite; external I/O uses fakes.
- For every phase run focused tests, `python -m pytest`, `git diff --check`, and
  inspect the final diff. Preserve or improve coverage.

## Git, safety, and phased workflow

- Stay on the current branch. Never push without explicit authorization, never
  rewrite history, and never use destructive Git/filesystem commands.
- Preserve unrelated user changes. Do not commit `PLAN.md` unless its roadmap
  was explicitly changed.
- Implement one phase per reviewable commit. At phase end report decisions,
  files, tests, risks, and a Conventional Commit suggestion; do not commit until
  approved and do not begin editing the next phase before that commit approval.
- At a new phase, perform only an incremental review: changes since the last
  commit, directly affected files/contracts/tests, this guide, and the integrated
  remaining-phase plan. Re-scan the full repository only when evidence shows
  this context is stale.
- Update this file only when a durable architectural or workflow instruction
  changes.

Stop before implementation and request approval for: a significant departure
from `PLAN.md`; an unplanned schema migration; public API break; deletion or
loss of data; new external dependency; multiple reasonable architecture
choices; combining phases; a code-related baseline test failure; or material
scope expansion. Clearly present alternatives and downstream impact.
