# Pitch Prophet

## Current features

- SQLite persistence
- Liga MX tournament and team storage
- Match result registration
- Elo rating calculation
- Elo history by match
- Team statistics and standings
- User prediction tracking
- Automated tests

## Tech stack

- Python
- SQLite
- pytest

## Inicialización

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/initialize_database.py
```

## Local setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:
```bash
python -m pip install -r requirements.txt
```

3. Initialize the local database:
```bash
python -m scripts.initialize_database
python -m scripts.migrate_prediction_persistence
python -m scripts.migrate_evaluation_persistence
python -m scripts.seed_jornada_1
python -m scripts.process_results
python -m scripts.migrate_team_statistics
python -m scripts.recalculate_statistics
```

4. Run the application:
```bash
python main.py
```

Run temporal model evaluation:

```bash
python -m scripts.backtest_models 1
python -m scripts.evaluate_models 1
```

Run the HTTP API:

```bash
python -m scripts.run_api --host 127.0.0.1 --port 8000
```

Interactive documentation is available at `/docs` while the API is running.

Run an idempotent automated update with bounded retries:

```bash
python -m scripts.run_automated_update --source-file matches.json --source-name scheduled-file --max-attempts 3 --retry-delay 10 --log-file logs/pitchprophet.jsonl
```

For periodic local execution, see
[Windows Task Scheduler](docs/windows-task-scheduler.md).

5. Run the tests:
```bash
python -m pytest
```
