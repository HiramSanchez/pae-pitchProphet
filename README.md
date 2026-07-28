# PitchProphet

PitchProphet is a Python backend for importing football fixtures and results,
maintaining derived team data, generating reproducible match predictions, and
comparing model performance over time. It combines a SQLite application with
command-line workflows and a FastAPI REST interface.

The project currently provides a complete local backend and API. It does not
include a graphical frontend, a ChatGPT-like chat interface, live commercial
data feeds, or an LLM integration.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Requirements and installation](#requirements-and-installation)
- [Database setup](#database-setup)
- [Running the data update pipeline](#running-the-data-update-pipeline)
- [Running the API](#running-the-api)
- [API endpoints](#api-endpoints)
- [How to use PitchProphet](#how-to-use-pitchprophet)
- [Understanding prediction output](#understanding-prediction-output)
- [Testing](#testing)
- [Automation](#automation)
- [Troubleshooting](#troubleshooting)
- [Limitations and future work](#limitations-and-future-work)
- [Documentation](#documentation)

## Features

- Four versioned prediction models:
  - **Elo** with home advantage and dynamic draw probability;
  - **Elo Form** with recent points, goal difference, and venue performance;
  - **Poisson** with smoothed attack and defence strengths, expected goals,
    and a truncated score matrix;
  - **Ensemble** with configurable weighted probabilities from component
    models.
- An in-memory model registry keyed by model name and version.
- Predictions for every scheduled match in a tournament round.
- Model name, version, effective configuration, confidence, input snapshot,
  and structured explanation stored with each prediction.
- Immutable prediction revisions when scheduled-match inputs change.
- Walk-forward historical evaluation without future-data leakage, including
  Log Loss, Brier Score, accuracy, top-two accuracy, and calibration error.
- Immutable, deduplicated evaluation history.
- Idempotent match synchronization and update pipeline.
- Manual JSON-file and HTTP JSON data sources.
- Deterministic rebuilds of standings, team statistics, Elo, and Elo history.
- Structured queries for model comparisons, best predictions, draw
  probabilities, model performance, and changed predictions.
- FastAPI endpoints and a deterministic Spanish question interpreter.
- Bounded operational retries, UTC JSON logs, and `update_runs` auditing.

## Architecture

```text
                    +------------------+
                    | scripts / FastAPI|
                    +--------+---------+
                             |
            +----------------+----------------+
            |                                 |
     +------v------+                   +------v------+
     | data sources|                   | query layer |
     +------+------+                   +------+------+
            |                                 |
            +---------------+-----------------+
                            |
                     +------v------+
                     |  services   |
                     +---+------+--+
                         |      |
              +----------+      +-----------+
              |                             |
       +------v-------+             +-------v--------+
       | repositories |             |prediction models|
       +------+-------+             +-------+--------+
              |                             |
       +------v-------+             +-------v--------+
       |SQLite/database|             | domain models  |
       +--------------+             +----------------+
```

- **Scripts and API** are composition and transport boundaries. They parse
  input, create dependencies, and call services.
- **Data sources** convert a JSON file or HTTP response into canonical match
  objects; they never write SQLite directly.
- **Services** coordinate update, prediction, evaluation, explanation,
  automation, and query use cases.
- **Query layer** maps supported Spanish questions to structured service
  operations. It performs no probability calculations.
- **Repositories** contain application SQL and map rows to domain objects.
- **Database** owns connections and idempotent schema migrations.
- **Prediction models** are pure mathematical components with no SQLite,
  repository, service, or HTTP dependencies.
- **Domain models** are typed dataclasses shared across the application.

## Project structure

```text
PitchProphet/
|-- data/                 # Local SQLite database (runtime data)
|-- docs/                 # User and operational documentation
|-- examples/             # Valid sample match-source JSON
|-- scripts/              # Module-based CLI entry points
|-- src/
|   |-- api/              # FastAPI routes and Pydantic request schemas
|   |-- data_sources/     # Manual-file and HTTP input adapters
|   |-- database/         # SQLite connection and migrations
|   |-- models/           # Domain dataclasses and pure Elo math
|   |-- prediction/       # Models, registry, ensemble, explanations
|   |-- query/            # Deterministic intent interpretation
|   |-- repositories/     # SQLite persistence and queries
|   `-- services/         # Application orchestration
|-- tests/                # Unit and in-memory SQLite integration tests
|-- main.py               # Console standings and user-pick summary
`-- requirements.txt      # Runtime and test dependencies
```

## Requirements and installation

- Python **3.11 or newer** (`StrEnum` is used by the codebase).
- Windows PowerShell or Command Prompt for the commands below.
- No external database server or optional package is required.

After cloning or downloading the repository, open PowerShell in its root and
run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use Command Prompt instead:

```cmd
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The application requires no environment variables. Paths are resolved from
the repository root, so run all module commands from that directory.

## Database setup

The local database is `data/liga_mx.db`. Initialize a new database and all
currently required schemas with:

```powershell
python -m scripts.initialize_database
```

The initializer creates the core schema and runs the team-statistics,
prediction-persistence, prediction-revision, evaluation, and update-pipeline
migrations. Migrations are idempotent. The data update commands also run the
complete runtime migration set automatically before processing a source.

For an older database, individual migration commands remain available:

```powershell
python -m scripts.migrate_prediction_persistence
python -m scripts.migrate_evaluation_persistence
python -m scripts.migrate_team_statistics
```

The prediction-persistence migration preserves legacy human picks by renaming
the old `predictions` table to `user_predictions` before creating the current
model-prediction table.

Tests never require the real database: repository and pipeline integration
tests use temporary or in-memory SQLite connections. Do not point tests or
experiments at `data/liga_mx.db`. For manual inspection without writes, open it
with SQLite URI `file:data/liga_mx.db?mode=ro`.

The update pipeline rebuilds team statistics, current Elo, and `elo_history`
deterministically from completed matches. To rebuild standings statistics
alone, run:

```powershell
python -m scripts.recalculate_statistics
```

## Running the data update pipeline

Always invoke project scripts as modules from the repository root.

### Local JSON example

```powershell
python -m scripts.update_data --source-file examples/sample_matches.json --source-name sample
```

The input must be a JSON array of match objects. The bundled
[`examples/sample_matches.json`](examples/sample_matches.json) contains two
completed and two scheduled matches. The exact field contract and an update
exercise are in the [user guide](docs/user-guide.md).

On an empty database, this example reports four inserted matches and eight
predictions: four active models for each scheduled match. It also creates one
historical evaluation per model. Repeating the same command produces no match
or prediction duplicates, but records another successful `update_runs` row.

### HTTP JSON source

The HTTP endpoint must return the same top-level JSON array and match objects
as the sample file:

```powershell
python -m scripts.update_data --api-url https://example.test/matches.json --source-name official-feed --timeout 15
```

- Exactly one of `--source-file` and `--api-url` is required.
- `--source-name` identifies the source namespace. Keep it stable across
  updates so `external_match_id` values resolve to the same matches.
- `--timeout` is the HTTP timeout in seconds and must be positive.

Successful output has this form:

```text
Actualización 1: 4 nuevos, 0 actualizados, 8 predicciones generadas.
```

To verify the audit record without changing the database:

```powershell
@'
import sqlite3
with sqlite3.connect("file:data/liga_mx.db?mode=ro", uri=True) as connection:
    for row in connection.execute(
        "SELECT id, status, matches_added, matches_updated, "
        "predictions_generated, started_at, finished_at "
        "FROM update_runs ORDER BY id DESC LIMIT 5"
    ):
        print(row)
'@ | python -
```

## Running the API

Start FastAPI through its module entry point:

```powershell
python -m scripts.run_api --host 127.0.0.1 --port 8000
```

- API base URL: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

`GET /` currently returns `404 Not Found` because no root route is registered;
this does not mean the API failed to start. The recommended way to explore and
execute requests is Swagger UI.

## API endpoints

| Method | Route | Purpose | Required input | Main response | Relevant errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/tournaments/{tournament_id}/rounds/{round_number}/predictions` | List stored predictions for a round. | Integer path parameters. | Array of prediction views; may be empty. | `422` for malformed path values. |
| GET | `/matches/{match_id}/predictions` | Compare all stored models for a match. | Integer `match_id`. | Model comparison with predictions, favorites, agreement, and probability ranges. | `404` when no predictions exist; `422` for malformed input. |
| GET | `/matches/{match_id}/explanation` | Get one model's structured explanation. | Integer `match_id`; optional `model_name` (default `ensemble`) and `model_version` (default `1.0.0`). | Prediction and explanation factors. | `404` when that prediction/explanation does not exist. |
| GET | `/models/performance` | Get latest evaluations ranked by Log Loss. | Positive query parameter `tournament_id`. | Array of model evaluations. | `422` when the ID is missing or not positive. |
| GET | `/tournaments/{tournament_id}/rounds/next` | Get the next scheduled round as one product view. | Integer tournament ID. | Round, journal state, matches, personal picks, and persisted model predictions. | `404` when no scheduled round exists. |
| GET | `/tournaments/{tournament_id}/rounds/{round_number}/results` | Get match results and personal picks for a round. | Integer tournament and round IDs. | Match statuses, scores, actual outcomes, journal state, and picks. | `404` when the round does not exist. |
| GET | `/tournaments/{tournament_id}/performance/personal` | Get personal categorical accuracy. | Integer tournament ID. | Evaluated matches, correct picks, and accuracy; zero values are valid. | `422` for malformed path values. |
| GET | `/tournaments/{tournament_id}/performance/comparison` | Compare personal accuracy with frozen model forecasts. | Integer tournament ID. | Participants evaluated on the same completed matches. | `422` for malformed path values. |
| POST | `/tournaments/{tournament_id}/rounds/{round_number}/journal` | Open the single-user journal for a round. | Integer tournament and round IDs. | Journal state and an empty initial pick list. | `404` when the round has no active matches. |
| PUT | `/tournaments/{tournament_id}/rounds/{round_number}/picks` | Save partial picks while a journal is open. | List of match IDs and `home`, `draw`, or `away`. | Current journal and pick collection. | `400` for invalid matches; `409` when not open. |
| PATCH | `/picks/{prediction_id}` | Change one open personal pick. | One lowercase predicted outcome. | Updated personal prediction. | `404` when absent; `409` when locked. |
| POST | `/tournaments/{tournament_id}/rounds/{round_number}/finalize` | Confirm a complete round and freeze model forecasts. | Integer tournament and round IDs. | Finalized journal and picks. | `400` when incomplete; `409` for invalid state. |
| GET | `/tournaments/{tournament_id}/rounds/{round_number}/picks` | Retrieve a personal journal. | Integer tournament and round IDs. | Journal and saved picks. | `404` when no journal exists. |
| POST | `/updates/run` | Run the idempotent pipeline from canonical matches in the request. | `source_name` and `matches`; `source_name` defaults to `api`. | Run ID and insert/update/prediction counts. | `422` for invalid request data; pipeline failures return server errors. |
| POST | `/queries` | Interpret a supported Spanish question and return structured data. | Non-empty `question`, positive `tournament_id`, optional positive `match_id`. | Intent, Spanish message, and structured result. | `400` for missing intent context; `422` for unsupported intent or invalid request. |

### Request and response examples

Values below are representative outputs from the in-memory API integration
tests. IDs, probabilities, metrics, and timestamps depend on your data.

#### Predictions by round

```http
GET /tournaments/1/rounds/2/predictions
```

```json
[
  {
    "prediction_id": 1,
    "match_id": 2,
    "tournament_id": 1,
    "round_number": 2,
    "home_team_name": "B",
    "away_team_name": "A",
    "model_name": "elo",
    "model_version": "1.0.0",
    "prediction": {
      "home_team_id": 2,
      "away_team_id": 1,
      "home_probability": 0.4208,
      "draw_probability": 0.2513,
      "away_probability": 0.3279,
      "predicted_result": "HOME",
      "expected_home_goals": null,
      "expected_away_goals": null,
      "most_likely_score": null,
      "score_matrix": null,
      "component_probabilities": null
    },
    "confidence": 0.4208,
    "explanation": {
      "main_factors": [
        {
          "description": "El equipo visitante tiene mayor Elo",
          "factor": "elo_difference",
          "impact": "away",
          "value": -36.678
        },
        {
          "description": "Se aplicó ventaja por localía",
          "factor": "home_advantage",
          "impact": "home",
          "value": 80.0
        }
      ],
      "uncertainty": "medium",
      "alternative_result": "away"
    },
    "created_at": "2026-07-22T04:42:36.925362+00:00"
  }
]
```

The real response contains one item for every stored model prediction; the
sample pipeline normally returns four items per scheduled match.

#### Predictions by match

```http
GET /matches/2/predictions
```

```json
{
  "match_id": 2,
  "predictions": [
    {
      "prediction_id": 1,
      "match_id": 2,
      "tournament_id": 1,
      "round_number": 2,
      "home_team_name": "B",
      "away_team_name": "A",
      "model_name": "elo",
      "model_version": "1.0.0",
      "prediction": {
        "home_team_id": 2,
        "away_team_id": 1,
        "home_probability": 0.4208,
        "draw_probability": 0.2513,
        "away_probability": 0.3279,
        "predicted_result": "HOME",
        "expected_home_goals": null,
        "expected_away_goals": null,
        "most_likely_score": null,
        "score_matrix": null,
        "component_probabilities": null
      },
      "confidence": 0.4208,
      "explanation": {
        "main_factors": [
          {
            "description": "El equipo visitante tiene mayor Elo",
            "factor": "elo_difference",
            "impact": "away",
            "value": -36.678
          },
          {
            "description": "Se aplicó ventaja por localía",
            "factor": "home_advantage",
            "impact": "home",
            "value": 80.0
          }
        ],
        "uncertainty": "medium",
        "alternative_result": "away"
      },
      "created_at": "2026-07-22T04:42:36.925362+00:00"
    }
  ],
  "favorites": {
    "elo:1.0.0": "home"
  },
  "agreed_result": "home",
  "probability_ranges": {
    "home": [0.4208, 0.4208],
    "draw": [0.2513, 0.2513],
    "away": [0.3279, 0.3279]
  }
}
```

`predictions` contains the same complete prediction-view objects shown in the
round response.

#### Match explanation

```http
GET /matches/2/explanation?model_name=elo&model_version=1.0.0
```

```json
{
  "prediction": {
    "prediction_id": 1,
    "match_id": 2,
    "tournament_id": 1,
    "round_number": 2,
    "home_team_name": "B",
    "away_team_name": "A",
    "model_name": "elo",
    "model_version": "1.0.0",
    "prediction": {
      "home_team_id": 2,
      "away_team_id": 1,
      "home_probability": 0.4208,
      "draw_probability": 0.2513,
      "away_probability": 0.3279,
      "predicted_result": "HOME",
      "expected_home_goals": null,
      "expected_away_goals": null,
      "most_likely_score": null,
      "score_matrix": null,
      "component_probabilities": null
    },
    "confidence": 0.4208,
    "explanation": {
      "main_factors": [
        {
          "description": "El equipo visitante tiene mayor Elo",
          "factor": "elo_difference",
          "impact": "away",
          "value": -36.678
        },
        {
          "description": "Se aplicó ventaja por localía",
          "factor": "home_advantage",
          "impact": "home",
          "value": 80.0
        }
      ],
      "uncertainty": "medium",
      "alternative_result": "away"
    },
    "created_at": "2026-07-22T04:42:36.925362+00:00"
  },
  "explanation": {
    "main_factors": [
      {
        "description": "El equipo visitante tiene mayor Elo",
        "factor": "elo_difference",
        "impact": "away",
        "value": -36.678
      },
      {
        "description": "Se aplicó ventaja por localía",
        "factor": "home_advantage",
        "impact": "home",
        "value": 80.0
      }
    ],
    "uncertainty": "medium",
    "alternative_result": "away"
  }
}
```

The factors are generated from the persisted input snapshot rather than from
presentation text or an LLM.

#### Model performance

```http
GET /models/performance?tournament_id=1
```

```json
[
  {
    "model_name": "elo",
    "model_version": "1.0.0",
    "tournament_id": 1,
    "evaluated_matches": 1,
    "log_loss": 0.7496,
    "brier_score": 0.4196,
    "accuracy": 1.0,
    "top_two_accuracy": 1.0,
    "calibration_error": 0.5274,
    "confusion_matrix": {},
    "evaluated_at": "2026-07-22T04:42:36.922247+00:00",
    "evaluation_id": 1,
    "evaluation_key": "4a593c31919cee4c87964d9b1ca879db0e6621371e4428a90bed0aad8963d87e",
    "from_round": 1,
    "to_round": 1
  }
]
```

#### Run an update

```http
POST /updates/run
Content-Type: application/json

{
  "source_name": "api-sample",
  "matches": [
    {
      "external_match_id": "api-sample-1",
      "tournament_name": "Example League",
      "season": "2026",
      "round_number": 1,
      "home_team_name": "North FC",
      "away_team_name": "South FC",
      "status": "scheduled"
    }
  ]
}
```

```json
{
  "run_id": 1,
  "matches_added": 1,
  "matches_updated": 0,
  "predictions_generated": 4
}
```

#### Ask a structured question

```http
POST /queries
Content-Type: application/json

{
  "question": "¿Cuáles son las mejores predicciones para la siguiente jornada y por qué?",
  "tournament_id": 999
}
```

```json
{
  "intent": "best_predictions",
  "message": "No hay predicciones para la siguiente jornada.",
  "data": []
}
```

`data` contains ranked best-prediction objects when the tournament has stored
scheduled predictions; the example deliberately uses an unknown tournament to
show the valid empty result.

## How to use PitchProphet

1. Create the virtual environment and install `requirements.txt`.
2. Run `python -m scripts.initialize_database`.
3. Load the bundled data with:

   ```powershell
   python -m scripts.update_data --source-file examples/sample_matches.json --source-name sample
   ```

4. Start the API:

   ```powershell
   python -m scripts.run_api --host 127.0.0.1 --port 8000
   ```

5. Open <http://127.0.0.1:8000/docs>.
6. Execute `GET /models/performance?tournament_id=1`, replacing `1` with the
   tournament ID created in your database, or submit the Spanish question from
   the `/queries` example.
7. Read each prediction as an estimated probability distribution, not a
   guaranteed outcome.

PitchProphet is currently a backend/API. The `/queries` endpoint recognizes a
small deterministic set of Spanish intents; it is not a general-purpose chat
or LLM interface.

## Understanding prediction output

- `home_probability`, `draw_probability`, and `away_probability` estimate the
  mutually exclusive match outcomes and sum to approximately 1.
- `predicted_result` is the outcome with the highest probability: `HOME`,
  `DRAW`, or `AWAY`.
- `confidence` is the largest of the three probabilities. It is not a claim of
  certainty or historical accuracy.
- `model_name` and `model_version` identify the exact predictor.
- Model comparison responses expose each model's favorite, a common
  `agreed_result` when all favorites coincide, and probability ranges that
  make discrepancies visible.
- `explanation` contains deterministic factors derived from the model's stored
  input snapshot, plus uncertainty and an alternative result.
- Poisson can additionally expose expected goals, a likely score, and a score
  matrix. Ensemble exposes component model probabilities.

These probabilities depend on the available match history, configuration, and
data quality. They are estimates, not guarantees or betting advice.

## Testing

Run the complete suite from the repository root:

```powershell
python -m pytest
```

Useful focused suites include:

```powershell
python -m pytest tests/test_api.py
python -m pytest tests/test_data_update_service.py tests/test_sample_matches.py
python -m pytest tests/test_prediction_models.py tests/test_backtesting_service.py
```

At the time of this README review, the complete suite contains **141 passing
tests**. This count will naturally change as the project evolves.

## Automation

Run the complete update workflow with bounded retries and optional JSONL logs:

```powershell
python -m scripts.run_automated_update --source-file examples/sample_matches.json --source-name sample --max-attempts 3 --retry-delay 10 --log-file logs/pitchprophet.jsonl
```

The command retries the complete idempotent operation, logs UTC structured
events without exception messages that may contain secrets, and writes one
`update_runs` audit row for every pipeline attempt once the audit schema is
available. Exit code `0` means success; exit code `1` means all attempts
failed. Retry delay is limited to 0 through 60 seconds.

For periodic local runs, configure Windows Task Scheduler as described in the
[Task Scheduler guide](docs/windows-task-scheduler.md). The project does not
run a resident scheduler or daemon.

## Troubleshooting

### `ModuleNotFoundError: No module named 'src'`

Run commands from the repository root and use module syntax:

```powershell
python -m scripts.update_data --source-file examples/sample_matches.json --source-name sample
```

Do not run `python scripts/update_data.py`.

### `--source-file` or `--api-url` is required

The update commands intentionally require exactly one source. Use the bundled
sample command above or provide an HTTP endpoint that returns the same JSON
array schema.

### `GET /` returns 404

This is expected because no root endpoint exists. Use `/docs`,
`/openapi.json`, or one of the registered API endpoints.

### The database is empty or a table is missing

Run:

```powershell
python -m scripts.initialize_database
```

For a legacy database where `main.py` reports that `user_predictions` is
missing, back up `data/liga_mx.db` and run:

```powershell
python -m scripts.migrate_prediction_persistence
```

### A tournament, round, or match returns no predictions

Confirm the numeric IDs in the database, check that the match status is
`scheduled`, and run the update pipeline. A round endpoint may validly return
an empty array. Match prediction and explanation endpoints return `404` when
the requested stored data does not exist.

### Port 8000 is already in use

Choose another port:

```powershell
python -m scripts.run_api --host 127.0.0.1 --port 8001
```

### An HTTP source fails

Verify that the URL returns a UTF-8 JSON array matching the documented source
schema, that `--timeout` is positive and sufficient, and that the machine has
network access. The automated command classifies these failures as
`source_unavailable` in its JSON logs.

## Limitations and future work

### Current limitations

- SQLite and local files are intended for a single local deployment, not
  horizontally scaled concurrent workers.
- No graphical frontend or root web page is included.
- The question interpreter supports a fixed set of Spanish keyword-based
  intents; it is not general natural-language understanding.
- No commercial sports provider, authentication, authorization, or API rate
  limiting is bundled.
- Scheduling is external through Windows Task Scheduler.
- Prediction quality depends on the amount and quality of imported history.

### Potential future work

- A separate web or mobile frontend.
- Authenticated multi-user API access.
- Remote database/storage and cloud scheduling.
- Production data-provider adapters with secure credential handling.
- Broader multilingual query interpretation or an optional LLM presentation
  layer that remains isolated from prediction calculations.
- Monitoring integrations for operational alerts.

These are possible improvements, not implemented features.

## Documentation

- [User guide](docs/user-guide.md): exact source JSON schema, local update
  exercise, idempotency, and verification queries.
- [Windows Task Scheduler](docs/windows-task-scheduler.md): periodic local
  automation setup.
- [Agent and architecture guide](AGENTS.md): dependency rules, contracts, and
  contributor workflow.
- [Implementation roadmap](PLAN.md): historical phased plan; use the code and
  tests as the source of truth for implemented behavior.

Documentation files such as `ARCHITECTURE.md`, `DEVELOPMENT.md`, and
`PROJECT_HISTORY.md` do not currently exist and are therefore not linked.
