# Manual de usuario

## Usar la aplicación web

Inicia la API desde la raíz del repositorio:

```powershell
python -m scripts.run_api --host 127.0.0.1 --port 8000
```

En otra terminal inicia el cliente:

```powershell
cd frontend
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`. En **Siguiente jornada** puedes consultar los
partidos y los pronósticos del modelo. En **Mi quiniela** abre el registro,
elige local, empate o visitante para cada partido y confirma la jornada cuando
esté completa. La confirmación bloquea las selecciones para conservar el
historial. **Resultados** y **Rendimiento** muestran lo ocurrido y comparan tu
efectividad con los modelos. **Preguntar** acepta únicamente las intenciones
en español soportadas por el intérprete determinista.

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

## Consultas orientadas al producto

Con el API iniciado, la vista completa de la siguiente jornada se obtiene con:

```http
GET /tournaments/1/rounds/next
```

La respuesta agrupa los cruces, el estado de cada partido, su fecha opcional,
la quiniela personal si existe y las predicciones persistidas de los modelos.
No recalcula predicciones durante la consulta.

Los resultados y el rendimiento se consultan con:

```http
GET /tournaments/1/rounds/1/results
GET /tournaments/1/performance/personal
GET /tournaments/1/performance/comparison
```

Una respuesta de rendimiento con cero partidos evaluados es válida. La
comparación utiliza los pronósticos de modelo congelados al finalizar la
quiniela y solo incluye modelos representados en todos los partidos
comparados.

## Preguntas determinísticas en español

`POST /queries` también acepta preguntas de producto:

```text
¿Cuál es la siguiente jornada?
¿Cuáles fueron mis pronósticos?
¿Cómo me fue en la jornada 8?
¿Cuál es mi efectividad?
¿Cómo voy contra los modelos?
```

El intérprete normaliza mayúsculas y acentos, selecciona una operación de
`QueryService` y devuelve un mensaje en español junto con datos estructurados.
No utiliza un LLM, no ejecuta SQL arbitrario y no calcula predicciones. Para
consultar resultados se debe indicar explícitamente el número de jornada; si
una pregunta sobre pronósticos personales no indica jornada, se devuelve la
quiniela personal más reciente.
