# Manual de usuario

## Prueba local del pipeline de actualización

Inicializa la base local si todavía no existe:

```powershell
python -m scripts.initialize_database
```

Desde la raíz del repositorio ejecuta el ejemplo incluido:

```powershell
python -m scripts.update_data --source-file examples/sample_matches.json --source-name sample
```

El archivo contiene un torneo, cuatro equipos, dos partidos completados en la
jornada 1 y dos programados en la jornada 2. En una base vacía, la primera
ejecución debe informar cuatro partidos nuevos y ocho predicciones: cuatro
modelos para cada partido programado. También crea cuatro evaluaciones, una
por modelo, usando los partidos completados.

Los conteos pueden ser distintos si la base ya contiene esos identificadores
de fuente o los mismos partidos. Una segunda ejecución sin cambiar el archivo
debe informar cero nuevos, cero actualizados y cero predicciones nuevas. Esto
comprueba la idempotencia, aunque sí registra un nuevo intento exitoso en
`update_runs`.

### Esquema JSON de `--source-file`

La raíz debe ser una lista JSON. Cada elemento debe ser un objeto con este
contrato exacto:

| Campo | Tipo | Obligatorio | Regla |
| --- | --- | --- | --- |
| `external_match_id` | string | Sí | Identificador no vacío y estable dentro de `source_name`. |
| `tournament_name` | string | Sí | Nombre no vacío; se normalizan espacios. |
| `season` | string | Sí | Temporada no vacía. |
| `round_number` | integer | Sí | Mayor que cero. |
| `home_team_name` | string | Sí | Nombre local no vacío. |
| `away_team_name` | string | Sí | Nombre visitante no vacío. |
| `status` | string | Sí | `scheduled`, `completed`, `postponed` o `cancelled`. |
| `match_date` | string o null | No | Se recomienda ISO 8601 con zona horaria, preferiblemente UTC. |
| `home_goals` | integer o null | No | Obligatorio si el estado es `completed`. |
| `away_goals` | integer o null | No | Obligatorio si el estado es `completed`. |

Los dos marcadores deben estar presentes juntos o ser ambos `null`. Los
campos desconocidos no están permitidos. `source_name` y
`external_match_id` forman la identidad externa usada para actualizar el mismo
partido en ejecuciones posteriores.

### Probar una actualización

Después de la primera ejecución, cambia en una copia del archivo uno de los
partidos `scheduled` a `completed` y asigna ambos marcadores, sin cambiar su
`external_match_id`. Ejecuta nuevamente el mismo comando y conserva
`--source-name sample`. Debe informar un partido actualizado, recalcular el
estado derivado, evaluar el nuevo resultado y no duplicar el partido.

No cambies `source-name` entre ejecuciones de la misma fuente: un nombre nuevo
representa otra identidad de origen.

### Verificar los resultados

Abre la base en modo de solo lectura desde la raíz del proyecto:

```powershell
@'
import sqlite3

uri = "file:data/liga_mx.db?mode=ro"
with sqlite3.connect(uri, uri=True) as connection:
    queries = {
        "update_runs": """
            SELECT id, status, matches_added, matches_updated,
                   predictions_generated, started_at, finished_at
            FROM update_runs ORDER BY id DESC LIMIT 5
        """,
        "matches": """
            SELECT m.id, t.name, t.season, m.round_number,
                   home.name, away.name, m.status,
                   m.home_goals, m.away_goals
            FROM matches m
            JOIN tournaments t ON t.id = m.tournament_id
            JOIN teams home ON home.id = m.home_team_id
            JOIN teams away ON away.id = m.away_team_id
            WHERE t.name = 'Liga de Ejemplo' AND t.season = '2026'
            ORDER BY m.round_number, m.id
        """,
        "evaluations": """
            SELECT e.model_name, e.model_version, e.evaluated_matches,
                   e.log_loss, e.evaluated_at
            FROM model_evaluations e
            JOIN tournaments t ON t.id = e.tournament_id
            WHERE t.name = 'Liga de Ejemplo' AND t.season = '2026'
            ORDER BY e.id
        """,
        "predictions": """
            SELECT p.match_id, p.model_name, p.model_version,
                   p.predicted_result, p.confidence
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            JOIN tournaments t ON t.id = m.tournament_id
            WHERE t.name = 'Liga de Ejemplo' AND t.season = '2026'
            ORDER BY p.match_id, p.model_name
        """,
    }
    for label, query in queries.items():
        print(f"\n{label}")
        for row in connection.execute(query):
            print(row)
'@ | python -
```

Verifica que el último `update_runs` tenga estado `succeeded`, que existan los
cuatro partidos sin duplicados, evaluaciones de los cuatro modelos y cuatro
predicciones por cada partido que siga programado.
