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
python -m scripts.seed_jornada_1
python -m scripts.process_results
python -m scripts.migrate_team_statistics
python -m scripts.recalculate_statistics
```

4. Run the application:
```bash
python main.py
```

5. Run the tests:
```bash
python -m pytest
```
