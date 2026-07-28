# PitchProphet — Plan de implementación por fases

## Objetivo

Convertir PitchProphet en un sistema capaz de:

- actualizar automáticamente partidos, resultados, estadísticas y ratings;
- generar predicciones para próximas jornadas y fases;
- comparar múltiples modelos;
- determinar automáticamente qué modelo funciona mejor;
- explicar el porqué de cada predicción;
- responder preguntas en lenguaje natural;
- conservar trazabilidad de los datos usados en cada cálculo.

La prioridad es obtener resultados confiables y útiles. La arquitectura debe ser modular, pero sin agregar abstracciones que todavía no se utilizan.

---

## Reglas obligatorias para Codex

1. Trabajar en una rama de feature por fase.
2. Inspeccionar el código y el esquema real antes de modificar archivos.
3. No asumir nombres de columnas.
4. La tabla `matches` usa actualmente:
   - `round_number`
   - `home_goals`
   - `away_goals`
   - `status`
5. Los partidos pendientes tienen `status = 'scheduled'`.
6. Los partidos terminados tienen `status = 'completed'`.
7. No modificar el esquema sin una migración.
8. Ejecutar `python -m pytest` antes y después de cada fase.
9. No mezclar refactors grandes con nuevas funcionalidades en el mismo commit.
10. SQLite debe permanecer encapsulado en repositories e infraestructura.
11. Los modelos matemáticos no deben depender de SQLite.
12. Toda predicción debe registrar modelo, versión, configuración y snapshot de entrada.
13. No crear carpetas, protocolos o clases que no se utilicen en la fase actual.
14. Detenerse al terminar cada fase y presentar:
    - archivos modificados;
    - decisiones tomadas;
    - pruebas ejecutadas;
    - resultado de las pruebas;
    - commit sugerido;
    - riesgos o pendientes.
15. No avanzar automáticamente a la siguiente fase sin revisión del usuario.

---

## Arquitectura objetivo

Se usará una arquitectura por capas inspirada en Clean Architecture, pero pragmática.

```text
src/
├── config.py
├── database/
│   ├── connection.py
│   └── migrations/
├── models/
│   ├── match.py
│   ├── prediction.py
│   ├── evaluation.py
│   └── model_version.py
├── prediction/
│   ├── base.py
│   ├── registry.py
│   ├── elo_model.py
│   ├── elo_form_model.py
│   ├── poisson_model.py
│   ├── ensemble_model.py
│   └── explanations.py
├── repositories/
│   ├── match_repository.py
│   ├── team_repository.py
│   ├── prediction_repository.py
│   ├── model_repository.py
│   └── evaluation_repository.py
├── services/
│   ├── prediction_service.py
│   ├── statistics_service.py
│   ├── backtesting_service.py
│   ├── evaluation_service.py
│   ├── data_update_service.py
│   ├── explanation_service.py
│   └── query_service.py
└── data_sources/
    ├── base.py
    ├── manual_source.py
    └── external_api_source.py
```

Esta estructura representa la dirección final. No debe crearse completa desde el inicio.

---

# Fase 0 — Estabilizar el estado actual

## Objetivo

Alinear el código existente con el esquema real de SQLite y establecer una línea base estable.

## Tareas

- Revisar `MatchRepository`.
- Reemplazar referencias incorrectas:
  - `matchday` por `round_number`;
  - `home_score` por `home_goals`;
  - `away_score` por `away_goals`.
- Renombrar `find_pending_by_matchday` a `find_scheduled_by_round`.
- Consultar partidos programados mediante:

```sql
WHERE tournament_id = ?
  AND round_number = ?
  AND status = 'scheduled'
```

- Renombrar `PendingMatch.matchday` a `round_number`.
- Preferir el nombre `ScheduledMatch` sobre `PendingMatch`.
- Actualizar imports y pruebas.
- Confirmar que `find_completed_matches` continúa funcionando.

## Criterios de aceptación

- No existen referencias a columnas inexistentes.
- Se recuperan correctamente partidos programados por torneo y jornada.
- Se recuperan correctamente partidos completados.
- Toda la suite de pruebas pasa.

## Commit sugerido

```text
fix: align match repository with database schema
```

---

# Fase 1 — Separar Elo de PredictionService

## Objetivo

Extraer toda la lógica matemática a un modelo independiente de SQLite.

## Crear

```text
src/prediction/
├── __init__.py
├── base.py
└── elo_model.py
```

## Contrato mínimo

```python
class PredictionModel(Protocol):
    name: str
    version: str

    def predict(
        self,
        home_team: TeamRating,
        away_team: TeamRating,
    ) -> Prediction:
        ...
```

No agregar métodos que aún no se utilicen.

## EloPredictionModel

Mover desde `PredictionService`:

- ventaja local;
- expected score;
- probabilidad dinámica de empate;
- distribución HOME/DRAW/AWAY;
- selección del resultado más probable;
- validaciones de configuración.

Metadatos iniciales:

```python
name = "elo"
version = "1.0.0"
```

## PredictionService

Debe encargarse únicamente de:

- leer equipos mediante repositories;
- validar que existan;
- invocar el modelo;
- coordinar flujos;
- persistir posteriormente.

No debe conservar fórmulas.

## Pruebas

- probabilidades suman 1;
- probabilidades están entre 0 y 1;
- localía favorece al local con Elo igual;
- un visitante muy superior puede ser favorito;
- equipos equilibrados tienen mayor empate;
- configuración inválida produce error;
- el servicio delega al modelo.

## Criterios de aceptación

- `EloPredictionModel` funciona sin base de datos.
- `PredictionService` no contiene matemáticas.
- Pruebas separadas para modelo y servicio.
- Toda la suite pasa.

## Commits sugeridos

```text
refactor: extract Elo prediction model
test: separate model and service prediction tests
```

---

# Fase 2 — Predecir una jornada completa

## Objetivo

Generar predicciones para todos los partidos programados de una jornada.

## Modelos

```python
@dataclass(frozen=True)
class ScheduledMatch:
    match_id: int
    tournament_id: int
    round_number: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
```

```python
@dataclass(frozen=True)
class MatchPrediction:
    match_id: int
    tournament_id: int
    round_number: int
    home_team_name: str
    away_team_name: str
    prediction: Prediction
```

## PredictionService

Agregar:

```python
predict_round(
    tournament_id: int,
    round_number: int,
) -> list[MatchPrediction]
```

Flujo:

1. recuperar partidos `scheduled`;
2. obtener ratings;
3. invocar el modelo;
4. devolver predicciones;
5. no persistir todavía.

## Script

Crear:

```text
scripts/predict_round.py
```

Uso:

```bash
python -m scripts.predict_round 1 2
```

## Criterios de aceptación

- Solo se predicen partidos `scheduled`.
- Una jornada vacía devuelve lista vacía y mensaje claro.
- Existen pruebas de integración con SQLite en memoria.
- Toda la suite pasa.

## Commit sugerido

```text
feat: generate predictions for scheduled round
```

---

# Fase 3 — Persistencia y versionado

## Objetivo

Guardar predicciones reproducibles y evitar duplicados.

## Migración: model_versions

```sql
CREATE TABLE model_versions (
    id INTEGER PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    configuration_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, model_version)
);
```

## Migración: predictions

```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    home_probability REAL NOT NULL,
    draw_probability REAL NOT NULL,
    away_probability REAL NOT NULL,
    predicted_result TEXT NOT NULL,
    confidence REAL NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    explanation_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id),
    UNIQUE(match_id, model_name, model_version)
);
```

## PredictionRepository

Implementar:

- `save`;
- `exists`;
- `find_by_match_and_model`;
- `find_by_round`.

No sobrescribir silenciosamente una predicción existente.

## Snapshot mínimo

- Elo local;
- Elo visitante;
- ventaja local;
- parámetros del modelo;
- momento de generación.

## Confidence

Usar inicialmente:

```text
max(home_probability, draw_probability, away_probability)
```

## Criterios de aceptación

- Dos ejecuciones no duplican datos.
- Cada predicción puede reproducirse.
- Modelo, versión y configuración quedan registrados.
- Pruebas de migración y repository pasan.

## Commits sugeridos

```text
feat: add prediction persistence schema
feat: persist versioned match predictions
```

---

# Fase 4 — Explicaciones estructuradas

## Objetivo

Explicar el resultado usando factores reales del modelo.

## Crear

```text
src/prediction/explanations.py
src/services/explanation_service.py
```

## Formato orientativo

```json
{
  "main_factors": [
    {
      "factor": "elo_difference",
      "impact": "home",
      "value": 76,
      "description": "El equipo local tiene mayor Elo"
    },
    {
      "factor": "home_advantage",
      "impact": "home",
      "value": 80,
      "description": "Se aplicó ventaja por localía"
    }
  ],
  "uncertainty": "medium",
  "alternative_result": "draw"
}
```

## Reglas

- No usar un LLM para decidir los factores.
- Los factores deben salir del modelo y del snapshot.
- El lenguaje natural se produce después.
- Marcar incertidumbre cuando las probabilidades principales sean cercanas.

## Criterios de aceptación

- Toda predicción persistida tiene explicación.
- La explicación coincide con el snapshot.
- Existe salida legible en español.
- Hay pruebas para favorito local, visitante y partido parejo.

## Commit sugerido

```text
feat: generate structured prediction explanations
```

---

# Fase 5 — Backtesting temporal y evaluación

## Objetivo

Medir la calidad del modelo sin fuga de información futura.

## Walk-forward validation

Para cada jornada:

1. construir estadísticas solo con partidos anteriores;
2. generar predicciones;
3. comparar con resultados reales;
4. incorporar la jornada;
5. actualizar Elo y estadísticas;
6. continuar.

Nunca utilizar datos posteriores para predecir el pasado.

## Métricas

Implementar:

- Log Loss;
- Brier Score multiclase;
- Accuracy;
- Top-2 Accuracy;
- matriz de confusión;
- error de calibración.

La métrica principal será:

```text
menor Log Loss
```

## Persistencia

```sql
CREATE TABLE model_evaluations (
    id INTEGER PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    tournament_id INTEGER,
    evaluated_matches INTEGER NOT NULL,
    log_loss REAL NOT NULL,
    brier_score REAL NOT NULL,
    accuracy REAL NOT NULL,
    top_two_accuracy REAL NOT NULL,
    calibration_error REAL,
    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## Scripts

```text
scripts/backtest_models.py
scripts/evaluate_models.py
```

## Criterios de aceptación

- No existe fuga temporal.
- Los resultados son reproducibles.
- Las métricas tienen pruebas con ejemplos conocidos.
- Se genera un ranking de modelos.
- Toda la suite pasa.

## Commits sugeridos

```text
feat: implement temporal model backtesting
feat: calculate prediction evaluation metrics
```

---

# Fase 6 — Elo con forma reciente

## Objetivo

Agregar un segundo modelo que incorpore rendimiento reciente.

## Crear

```text
src/prediction/elo_form_model.py
```

## Variables iniciales

- Elo;
- puntos en últimos cinco partidos;
- diferencia de goles reciente;
- rendimiento local del local;
- rendimiento visitante del visitante;
- ventaja local.

## Reglas

- Usar únicamente información anterior al partido.
- Mantener pesos en configuración.
- No reemplazar Elo v1.
- Registrar como `elo_form 1.0.0`.

## Criterios de aceptación

- Implementa el mismo contrato.
- Snapshot incluye todos los factores.
- Backtest comparable con Elo v1.
- Se determina el ganador por Log Loss y calibración.

## Commit sugerido

```text
feat: add Elo model with recent form
```

---

# Fase 7 — Modelo Poisson

## Objetivo

Generar probabilidades mediante goles esperados.

## Crear

```text
src/prediction/poisson_model.py
```

## Variables

- promedio de goles de liga;
- fuerza ofensiva local y visitante;
- fuerza defensiva local y visitante;
- condición local;
- datos previos al partido.

## Salida adicional

- marcador más probable;
- goles esperados;
- matriz truncada de marcadores;
- HOME/DRAW/AWAY.

Registrar como `poisson 1.0.0`.

## Criterios de aceptación

- Probabilidades suman aproximadamente 1.
- El truncamiento está documentado.
- Existe smoothing para pocos partidos.
- Se compara con modelos previos.

## Commit sugerido

```text
feat: add Poisson score prediction model
```

---

# Fase 8 — Registry y ensemble

## Objetivo

Ejecutar y combinar varios modelos.

## Registry

Crear:

```text
src/prediction/registry.py
```

Responsabilidades:

- registrar modelos;
- obtenerlos por nombre y versión;
- listar modelos activos;
- evitar condicionales extensos.

## Ensemble

Crear:

```text
src/prediction/ensemble_model.py
```

Primera versión:

- promedio ponderado de probabilidades;
- pesos configurables;
- pesos basados en backtesting cuando haya suficientes datos.

## Criterios de aceptación

- Elo, Elo+Forma y Poisson pueden ejecutarse juntos.
- Se detectan coincidencias y discrepancias.
- El ensemble está versionado.
- Los pesos quedan registrados.

## Commit sugerido

```text
feat: add prediction model registry and ensemble
```

---

# Fase 9 — Actualización automática

## Objetivo

Actualizar datos sin intervención manual.

## Contrato de fuente

```python
class MatchDataSource(Protocol):
    def fetch_matches(...) -> list[ExternalMatch]:
        ...
```

## Implementaciones iniciales

```text
manual_source.py
external_api_source.py
```

## Pipeline

1. consultar fuente;
2. normalizar torneos y equipos;
3. insertar partidos nuevos;
4. actualizar partidos modificados;
5. detectar partidos completados;
6. recalcular estadísticas;
7. actualizar Elo;
8. evaluar predicciones cerradas;
9. generar predicciones próximas;
10. registrar ejecución.

## Auditoría

```sql
CREATE TABLE update_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    matches_added INTEGER NOT NULL DEFAULT 0,
    matches_updated INTEGER NOT NULL DEFAULT 0,
    predictions_generated INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
```

## Requisito crítico

El pipeline debe ser idempotente. Una segunda ejecución con los mismos datos no puede:

- duplicar partidos;
- duplicar predicciones;
- aplicar Elo dos veces;
- corromper estadísticas.

## Criterios de aceptación

- Pipeline ejecutable desde script.
- Fallos registrados.
- Reejecución segura.
- Pruebas con fuente simulada.

## Commit sugerido

```text
feat: implement idempotent data update pipeline
```

---

# Fase 10 — Servicio de consultas

## Objetivo

Responder preguntas útiles sobre predicciones.

## Métodos iniciales

- `get_best_predictions_for_next_round`;
- `get_prediction_explanation`;
- `get_highest_draw_probabilities`;
- `compare_models_for_match`;
- `get_best_performing_model`;
- `get_recent_model_performance`;
- `get_changed_predictions`.

## Definición de “mejor predicción”

Ordenar considerando:

1. confianza;
2. acuerdo entre modelos;
3. calibración histórica;
4. cantidad y calidad de datos.

No confundir “mejor predicción” con “equipo más fuerte”.

## Criterios de aceptación

El sistema responde estructuradamente:

- cuáles son las predicciones más confiables;
- por qué;
- qué resultado alternativo existe;
- qué modelos coinciden;
- cuál modelo ha rendido mejor.

## Commit sugerido

```text
feat: add prediction query service
```

---

# Fase 11 — API e interfaz conversacional

## Objetivo

Permitir consultas externas y en lenguaje natural.

## API sugerida

Usar FastAPI cuando los servicios estén estables.

```text
GET /tournaments/{id}/rounds/{round}/predictions
GET /matches/{id}/predictions
GET /matches/{id}/explanation
GET /models/performance
POST /updates/run
POST /queries
```

## Rol del LLM

El LLM debe:

1. interpretar intención;
2. llamar a `QueryService`;
3. redactar usando resultados estructurados.

No debe:

- calcular probabilidades;
- inventar estadísticas;
- consultar SQLite directamente;
- modificar resultados;
- reemplazar el backtesting.

## Criterio principal

La pregunta:

```text
¿Cuáles son las mejores predicciones para la siguiente jornada y por qué?
```

debe devolver:

- jornada detectada;
- predicciones ordenadas;
- probabilidades;
- explicación;
- incertidumbre;
- modelo y versión.

## Commit sugerido

```text
feat: expose prediction queries through API
```

---

# Fase 12 — Automatización operativa

## Objetivo

Ejecutar periódicamente el pipeline completo.

## Flujo

```text
actualizar datos
→ recalcular estadísticas y Elo
→ evaluar predicciones cerradas
→ generar nuevas predicciones
→ generar explicaciones
→ registrar ejecución
```

## Opciones

- Task Scheduler para ejecución local en Windows;
- GitHub Actions si el almacenamiento se mueve a infraestructura remota;
- cron o servicio cloud en una fase posterior.

## Alertas mínimas

Detectar y registrar:

- fuente no disponible;
- datos incompletos;
- equipo desconocido;
- fallo de migración;
- probabilidades inválidas;
- pipeline incompleto.

## Criterios de aceptación

- Ejecución programable.
- Logs y auditoría.
- Reintentos seguros.
- No existen duplicados por reejecución.

## Commit sugerido

```text
feat: automate prediction update workflow
```

---

# Orden recomendado de ejecución

```text
Fase 0  Estabilización
Fase 1  Separación del modelo Elo
Fase 2  Predicción de jornada
Fase 3  Persistencia y versiones
Fase 4  Explicaciones
Fase 5  Backtesting
Fase 6  Elo + forma
Fase 7  Poisson
Fase 8  Ensemble
Fase 9  Actualización automática
Fase 10 Consultas
Fase 11 API y conversación
Fase 12 Automatización operativa
```

No comenzar por IA, scraping o API. Primero deben existir predicciones reproducibles, persistidas y evaluables.

---

# Prompt inicial para Codex

Usar este texto junto con el archivo:

```text
Lee PLAN.md y revisa primero todo el repositorio sin modificar archivos.

Después ejecuta únicamente la Fase 0.

Respeta estrictamente:
- el esquema real de SQLite;
- la arquitectura existente;
- las reglas obligatorias del plan;
- los criterios de aceptación;
- el límite de no avanzar a la siguiente fase.

Antes de editar, presenta:
1. diagnóstico del estado actual;
2. archivos que cambiarás;
3. incompatibilidades encontradas;
4. plan breve de implementación.

Después realiza los cambios, ejecuta toda la suite de pruebas y entrega:
1. resumen de cambios;
2. pruebas ejecutadas y resultado;
3. archivos modificados;
4. riesgos o pendientes;
5. commit sugerido.

No hagas commit ni push automáticamente.
No implementes ninguna fase posterior.
```

---

# Definition of Done global

Una fase solo está terminada cuando:

- el código cumple su objetivo;
- no introduce dependencias innecesarias;
- incluye pruebas unitarias o de integración;
- toda la suite pasa;
- las migraciones son reversibles o están claramente documentadas;
- no hay referencias a columnas inexistentes;
- las decisiones importantes quedan documentadas;
- Codex se detiene y solicita revisión antes de continuar.

---

# PitchProphet v2 — Roadmap de producto

## Objetivo

PitchProphet v2 agregará un flujo de producto de un solo usuario sobre el
motor de predicción existente. El usuario podrá:

- consultar los cruces y las predicciones de la siguiente jornada;
- guardar y modificar sus pronósticos mientras la jornada esté abierta;
- confirmar y cerrar manualmente sus pronósticos;
- cargar resultados reales al terminar cada jornada;
- evaluar sus aciertos de manera idempotente;
- comparar su efectividad con Elo, Elo Form, Poisson y Ensemble;
- realizar consultas de dominio en español;
- utilizar una interfaz web en lugar de depender de Swagger.

## Decisiones basadas en el repositorio

1. Se conservarán SQLite, los repositories existentes y una conexión por
   petición.
2. Se preservarán `user_predictions` y todos sus registros históricos.
3. `predictor` será la clave de propietario durante la etapa de un solo
   usuario. No se agregará autenticación ni una tabla `users`.
4. Los resultados personales conservarán los valores `home`, `draw` y `away`.
5. Los cruces de las 17 jornadas del Apertura 2026 se cargarán antes de
   implementar el diario.
6. La Jornada 1 existente, incluido Necaxa como local contra Atlante, sus
   resultados y los nueve pronósticos de Hiram, debe preservarse.
7. Las fechas y horarios de los partidos son opcionales y no controlarán la
   edición de pronósticos.
8. Cada quiniela tendrá un ciclo explícito:
   `open → finalized → evaluated`.
9. Una jornada abierta admite inserciones y cambios.
10. Finalizar una jornada exige un pronóstico para cada partido activo
    almacenado en esa jornada y bloquea cambios posteriores.
11. Los partidos cancelados se excluyen de la validación de completitud.
12. Los partidos aplazados conservan el pronóstico y quedan pendientes de
    evaluación.
13. La siguiente jornada continúa siendo el menor `round_number` con al menos
    un partido `scheduled`, de acuerdo con
    `MatchRepository.find_next_scheduled_round`.
14. No se asumirá que cualquier torneo o fase tiene siempre nueve partidos,
    aunque las 17 jornadas regulares auditadas del Apertura 2026 sí deben
    contener nueve.
15. Los pronósticos de los modelos usados para comparar se congelarán cuando
    se finalice la quiniela, no a la hora del partido.
16. La comparación incluirá solamente partidos completados presentes en el
    mismo conjunto para el usuario y los modelos.
17. La métrica personal inicial será accuracy categórica. No se atribuirán Log
    Loss ni Brier Score al usuario sin solicitar probabilidades personales.
18. `QueryService` seguirá siendo la frontera estructurada de lectura para API,
    conversación y un adaptador LLM opcional.
19. Las capas conversacional y LLM nunca calcularán predicciones ni ejecutarán
    SQL.
20. Las rutas y respuestas públicas existentes se conservarán salvo que se
    apruebe por separado un cambio incompatible.

## Decisiones pendientes

- Confirmar el valor configurable del usuario único. La información histórica
  utiliza `Hiram`.
- Definir si reabrir una jornada finalizada estará permitido mediante una
  operación administrativa explícita. No habrá reapertura automática.
- Elegir la topología de despliegue del frontend durante la Fase 17.
- Elegir proveedor y modelo únicamente si se aprueba la Fase 18 opcional.

# Fase 13 — Calendario y diario personal

## Objetivo

Precargar la fase regular del Apertura 2026 y exponer un diario transaccional
controlado por el estado manual de cada jornada.

## Dependencias

- Fases 0–12 terminadas.
- Pipeline idempotente y esquema actual de `matches`.
- Tabla heredada `user_predictions`.
- Calendario publicado del Apertura 2026 validado antes de insertarlo.

## Fase 13A — Catálogo del Apertura 2026

### Alcance

- Auditar los nueve partidos existentes de la Jornada 1.
- Preservar resultados, localías y pronósticos históricos.
- Preparar los cruces de las Jornadas 2–17.
- Cargar 144 partidos adicionales con estado `scheduled`.
- Usar identificadores externos estables.
- Ejecutar la carga mediante el pipeline existente.
- No exigir `match_date`.
- No sobrescribir un partido `completed` con información incompleta del
  calendario.

### Archivos previstos

```text
data/apertura_2026_fixtures.json
tests/test_apertura_2026_fixtures.py
docs/user-guide.md
```

Si `data/` permanece reservado para datos locales, el fixture versionado deberá
colocarse en `examples/` y documentarse antes de implementar.

### Migración

Ninguna.

### Pruebas

- 17 jornadas y 153 partidos;
- nueve partidos por jornada;
- cada equipo participa una vez por jornada;
- cada pareja de equipos se enfrenta una vez;
- Jornada 1 preservada;
- segunda carga sin duplicados;
- partidos completados no degradados a `scheduled`;
- suite completa.

### Criterios de aceptación

- El Apertura 2026 completo puede consultarse por jornada.
- Jornada 1 conserva resultados y pronósticos históricos.
- Jornadas 2–17 contienen los cruces publicados.
- Reejecutar la carga es seguro.

### Commit sugerido

```text
data: add Apertura 2026 regular-season fixtures
```

## Fase 13B — Persistencia del ciclo de jornada

### Alcance

Crear:

```text
src/database/migrations/user_prediction_journal.py
src/models/user_prediction.py
src/repositories/user_prediction_repository.py
tests/test_user_prediction_migration.py
tests/test_user_prediction_repository.py
```

Modificar:

```text
src/database/migrations/__init__.py
src/database/migrations/runtime.py
scripts/initialize_database.py
src/config.py
```

Crear de forma idempotente:

```sql
CREATE TABLE IF NOT EXISTS user_prediction_rounds (
    id INTEGER PRIMARY KEY,
    tournament_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    predictor TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK(status IN ('open', 'finalized', 'evaluated')),
    opened_at TEXT NOT NULL,
    finalized_at TEXT,
    evaluated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    UNIQUE(tournament_id, round_number, predictor)
);

CREATE INDEX IF NOT EXISTS idx_user_prediction_rounds_status
ON user_prediction_rounds(
    predictor, status, tournament_id, round_number
);
```

Agregar de forma idempotente a `user_predictions`:

```sql
updated_at TEXT
evaluated_at TEXT
```

La migración debe rellenar `updated_at` desde `created_at` para filas
históricas y no eliminar ni reconstruir la tabla.

El repository debe permitir:

- buscar la sesión de una jornada;
- crear una sesión abierta idempotentemente;
- listar pronósticos por torneo, jornada y predictor;
- insertar o actualizar un pronóstico abierto;
- finalizar atómicamente una jornada completa;
- rechazar cambios cuando el estado no sea `open`.

### Migración

Una tabla nueva, un índice y dos columnas aditivas. Se requiere respaldo antes
de aplicarla a la base local.

### Pruebas

- migración desde el esquema heredado;
- preservación de filas;
- migración idempotente;
- transición `open → finalized`;
- rechazo de transiciones inválidas;
- unicidad por torneo, jornada y predictor;
- operaciones del repository;
- suite completa.

### Criterios de aceptación

- Los nueve pronósticos históricos permanecen intactos.
- Una jornada tiene como máximo una sesión por predictor.
- Solo una jornada abierta admite cambios.
- Finalizar dos veces produce el mismo estado lógico.
- No se depende de fecha u horario.

### Commit sugerido

```text
feat: add personal prediction round lifecycle
```

## Fase 13C — Servicio y API del diario

### Alcance

Crear:

```text
src/services/personal_prediction_service.py
tests/test_personal_prediction_service.py
```

Modificar:

```text
src/services/query_service.py
src/api/schemas.py
src/api/app.py
tests/test_query_service.py
tests/test_api.py
```

Agregar:

```text
POST  /tournaments/{tournament_id}/rounds/{round_number}/journal
PUT   /tournaments/{tournament_id}/rounds/{round_number}/picks
PATCH /picks/{pick_id}
POST  /tournaments/{tournament_id}/rounds/{round_number}/finalize
GET   /tournaments/{tournament_id}/rounds/{round_number}/picks
```

Reglas:

1. El servidor resuelve internamente al predictor configurado.
2. Una jornada abierta permite selecciones parciales.
3. Cada partido admite un resultado `home`, `draw` o `away`.
4. Todos los partidos deben pertenecer al torneo y jornada solicitados.
5. Finalizar exige exactamente un pronóstico por partido activo.
6. La validación completa precede cualquier cambio de estado.
7. La finalización y sus snapshots posteriores serán transaccionales.
8. `PUT` y `PATCH` devuelven `409` después de finalizar.
9. Las operaciones repetidas no duplican filas.
10. `QueryService` expone lecturas estructuradas y no realiza escrituras.

### Migración

Ninguna adicional.

### Pruebas

- apertura idempotente;
- guardado parcial;
- actualización de una selección;
- partido duplicado, desconocido o de otra jornada;
- finalización incompleta;
- finalización completa y atómica;
- rechazo de cambios posteriores;
- respuestas `404`, `409` y `422`;
- suite completa.

### Criterios de aceptación

- Puede abrirse y recuperarse una quiniela.
- Pueden guardarse decisiones parciales mientras esté abierta.
- Una quiniela completa puede finalizarse explícitamente.
- Una quiniela finalizada queda bloqueada.
- No se requiere `match_date`.
- Las rutas actuales no sufren regresiones.

### Commit sugerido

```text
feat: expose personal prediction journal API
```

# Fase 14 — Resultados y comparación personal

## Objetivo

Evaluar pronósticos finalizados después de importar resultados y comparar al
usuario justamente con los cuatro modelos.

## Dependencias

- Fase 13 completa.
- Resultados importados mediante `DataUpdateService`.
- Predicciones persistidas de Elo, Elo Form, Poisson y Ensemble.

## Fase 14A — Evaluación personal idempotente

### Alcance

Crear:

```text
src/services/personal_evaluation_service.py
tests/test_personal_evaluation_service.py
```

Modificar:

```text
src/repositories/user_prediction_repository.py
src/services/data_update_service.py
tests/test_data_update_service.py
```

Flujo:

1. Seleccionar quinielas `finalized`.
2. Evaluar partidos `completed` con ambos marcadores.
3. Asignar `points_awarded = 1` o `0`.
4. Establecer `evaluated_at`.
5. Reevaluar de forma segura si se corrige un marcador.
6. Mantener aplazados pendientes.
7. Cambiar la jornada a `evaluated` cuando todos sus partidos aplicables hayan
   sido evaluados.

### Migración

Ninguna.

### Pruebas

- resultados local, empate y visitante;
- pronósticos correctos e incorrectos;
- resultados ausentes;
- partidos aplazados y cancelados;
- corrección de marcador;
- reejecución del pipeline;
- transición a `evaluated`;
- suite completa.

### Criterios de aceptación

- Los resultados importados evalúan automáticamente las quinielas finalizadas.
- La reevaluación no duplica ni acumula puntos.
- Una jornada incompleta permanece pendiente.
- Una jornada completa cambia a `evaluated`.

### Commit sugerido

```text
feat: evaluate personal predictions in update pipeline
```

## Fase 14B — Comparación congelada con modelos

### Alcance

Crear:

```text
src/database/migrations/user_prediction_model_snapshots.py
tests/test_user_prediction_model_snapshots_migration.py
```

Esquema:

```sql
CREATE TABLE IF NOT EXISTS user_prediction_model_snapshots (
    id INTEGER PRIMARY KEY,
    user_prediction_id INTEGER NOT NULL,
    prediction_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    predicted_result TEXT NOT NULL
        CHECK(predicted_result IN ('HOME', 'DRAW', 'AWAY')),
    home_probability REAL NOT NULL,
    draw_probability REAL NOT NULL,
    away_probability REAL NOT NULL,
    captured_at TEXT NOT NULL,
    FOREIGN KEY(user_prediction_id) REFERENCES user_predictions(id),
    FOREIGN KEY(prediction_id) REFERENCES predictions(id),
    UNIQUE(user_prediction_id, model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_user_prediction_snapshots_pick
ON user_prediction_model_snapshots(user_prediction_id);

CREATE INDEX IF NOT EXISTS idx_user_prediction_snapshots_model
ON user_prediction_model_snapshots(model_name, model_version);
```

Al finalizar una quiniela, se copiarán las predicciones persistidas disponibles
para cada partido. Las actualizaciones posteriores del modelo no modificarán
el snapshot.

`QueryService` agregará:

- resultados personales por jornada;
- rendimiento personal acumulado;
- comparación usuario-modelos sobre partidos comunes.

### Migración

Una tabla append-only y dos índices.

### Pruebas

- snapshots de los cuatro modelos;
- unicidad e idempotencia;
- aislamiento ante revisiones posteriores;
- comparación sobre el conjunto común;
- modelos ausentes;
- suite completa.

### Criterios de aceptación

- La comparación utiliza la predicción disponible al finalizar la quiniela.
- Todos los participantes se miden sobre los mismos partidos completados.
- Se reportan aciertos y accuracy.
- Las revisiones posteriores no alteran el histórico.

### Commit sugerido

```text
feat: compare personal accuracy with frozen model forecasts
```

# Fase 15 — API orientada al producto

## Objetivo

Proporcionar lecturas cohesivas para la futura interfaz web.

## Dependencias

- Fases 13 y 14.

## Alcance

Agregar:

```text
GET /tournaments/{tournament_id}/rounds/next
GET /tournaments/{tournament_id}/rounds/{round_number}/results
GET /tournaments/{tournament_id}/performance/personal
GET /tournaments/{tournament_id}/performance/comparison
```

La siguiente jornada debe agrupar:

- identidad del torneo y jornada;
- equipos y estado de cada partido;
- fecha opcional;
- estado de la quiniela;
- pronóstico personal, si existe;
- `PredictionView` persistidos de cada modelo.

### Archivos previstos

```text
src/models/query.py
src/services/query_service.py
src/api/schemas.py
src/api/app.py
tests/test_query_service.py
tests/test_api.py
```

### Migración

Ninguna.

### Pruebas

- resolución de siguiente jornada;
- respuesta sin jornada programada;
- agrupación de partidos, picks y modelos;
- resultados y estados vacíos;
- compatibilidad de rutas existentes;
- suite completa.

### Criterios de aceptación

- El frontend puede cubrir su MVP usando la API documentada.
- No se recalculan predicciones en consultas.
- Las rutas existentes permanecen compatibles.

### Commit sugerido

```text
feat: add product-oriented prediction query API
```

# Fase 16 — Consultas determinísticas en español

## Objetivo

Extender el intérprete existente sin introducir todavía un LLM.

## Dependencias

- Fase 15.

## Alcance

Agregar intents para:

```text
NEXT_ROUND
PERSONAL_PICKS
ROUND_RESULTS
PERSONAL_PERFORMANCE
PERSONAL_MODEL_COMPARISON
```

Preguntas representativas:

```text
¿Cuál es la siguiente jornada?
¿Cuáles fueron mis pronósticos?
¿Cómo me fue en la jornada 8?
¿Cuál es mi efectividad?
¿Cómo voy contra los modelos?
```

### Archivos previstos

```text
src/query/interpreter.py
src/services/conversation_service.py
src/api/schemas.py
tests/test_conversation_service.py
tests/test_api.py
```

### Migración

Ninguna.

### Pruebas

- variantes de redacción y acentos;
- precedencia de intents;
- contexto requerido;
- consultas no soportadas;
- delegación estricta a QueryService;
- suite completa.

### Criterios de aceptación

- Los cinco nuevos grupos tienen cobertura determinística.
- Los intents actuales siguen funcionando.
- La capa no accede directamente a SQLite.

### Commit sugerido

```text
feat: extend deterministic Spanish product queries
```

# Fase 17 — Aplicación web MVP

## Objetivo

Permitir el flujo completo sin utilizar Swagger.

## Dependencias

- API estable de la Fase 15.
- Consultas de la Fase 16.

## Alcance

Crear una aplicación React, TypeScript y Vite:

```text
frontend/
├── src/
│   ├── api/client.ts
│   ├── components/
│   ├── pages/
│   │   ├── NextRoundPage.tsx
│   │   ├── PersonalPicksPage.tsx
│   │   ├── RoundResultsPage.tsx
│   │   ├── PerformancePage.tsx
│   │   └── AskPitchProphetPage.tsx
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
└── vite.config.ts
```

Pantallas:

1. siguiente jornada y predicciones de modelos;
2. captura y confirmación de quiniela;
3. resultados por jornada;
4. comparación de rendimiento;
5. Ask PitchProphet.

Usar React Router y `fetch`. No agregar administración global de estado ni un
framework visual sin una necesidad concreta.

### Migración

Ninguna.

### Pruebas

- selección y confirmación;
- bloqueo después de finalizar;
- errores del API;
- estados vacíos;
- consultas;
- build de producción;
- suite backend.

### Criterios de aceptación

- Todo el flujo puede completarse sin Swagger.
- La UI refleja el estado real del servidor.
- El build de producción termina correctamente.

### Commit sugerido

```text
feat: add PitchProphet web application MVP
```

# Fase 18 — Adaptador LLM opcional

> **Estado: diferida como deuda técnica opcional.** El 28 de julio de 2026 se
> decidió continuar a la Fase 19 sin elegir proveedor, modelo, presupuesto ni
> gestión de secretos. El intérprete determinístico de la Fase 16 permanece
> como comportamiento de producción. Reactivar esta fase requiere una nueva
> aprobación explícita de esas cuatro decisiones.

## Objetivo

Ampliar opcionalmente la interpretación y redacción sin mover cálculos ni datos
fuera de QueryService.

## Dependencias

- Fases 15 y 16.
- Aprobación explícita de proveedor, modelo, costo y secretos.

## Alcance

Flujo:

```text
pregunta
→ adaptador opcional
→ intent y parámetros validados
→ QueryService
→ resultado estructurado
→ redacción opcional
```

Una salida inválida, timeout o fallo del proveedor regresará al intérprete
determinístico. El adaptador no recibirá conexiones, esquema SQL, base de datos
ni secretos.

### Archivos previstos

```text
src/conversation/llm_adapter.py
src/services/conversation_service.py
src/config.py
tests/test_llm_adapter.py
tests/test_conversation_service.py
```

### Migración

Ninguna.

### Pruebas

- intent válido e inválido;
- timeout y fallo;
- fallback determinístico;
- intent no soportado;
- intentos de prompt injection;
- ausencia de secretos en logs;
- suite completa.

### Criterios de aceptación

- Desactivar el adaptador preserva todo el comportamiento.
- El LLM no ejecuta SQL ni modelos.
- Cada dato de respuesta proviene de QueryService.

### Commit sugerido

```text
feat: add optional guarded LLM query adapter
```

# Fase 19 — Finalización operativa

## Objetivo

Hacer seguro y documentado el flujo completo de v2.

## Dependencias

- Fases 13–17.
- Fase 18 solamente si fue aprobada.

## Alcance

- respaldos y restauración antes de migraciones;
- health y readiness del API;
- timeout explícito de SQLite;
- transacciones cortas para finalizar jornadas;
- logs de evaluación y conflictos;
- reintentos idempotentes;
- configuración de producción del frontend;
- smoke test completo:

```text
cargar calendario
→ cargar resultados previos
→ generar siguiente jornada
→ guardar decisiones
→ finalizar quiniela
→ cargar resultados
→ evaluar
→ comparar
→ consultar en español
```

### Archivos previstos

```text
src/database/connection.py
src/services/data_update_service.py
src/services/automation_service.py
src/api/app.py
scripts/initialize_database.py
scripts/run_api.py
scripts/run_automated_update.py
tests/test_v2_workflow.py
README.md
docs/user-guide.md
docs/windows-task-scheduler.md
AGENTS.md
ARCHITECTURE_DECISIONS.md
```

### Migración

No se espera una nueva tabla. Cualquier necesidad descubierta se propondrá y
aprobará por separado.

### Pruebas

- migración desde una base previa a v2;
- conflictos de escritura;
- retry después de fallo;
- flujo end-to-end;
- health y readiness;
- build frontend;
- suite completa.

### Criterios de aceptación

- Instalaciones nuevas y heredadas completan el flujo v2.
- No se pierden pronósticos históricos.
- Actualizaciones y evaluaciones repetidas son seguras.
- API, frontend y operación están documentados.
- Todas las pruebas pasan.

### Commit sugerido

```text
chore: complete PitchProphet v2 operations and documentation
```

# Orden de implementación de PitchProphet v2

```text
Fase 13A  Cargar y validar los cruces de las 17 jornadas
Fase 13B  Persistir el ciclo open/finalized/evaluated
Fase 13C  Guardar y confirmar pronósticos
Fase 14A  Evaluar pronósticos personales
Fase 14B  Comparar con snapshots de modelos
Fase 15   API orientada al producto
Fase 16   Consultas determinísticas en español
Fase 17   Aplicación web React
Fase 18   Adaptador LLM opcional
Fase 19   Operación, documentación y robustecimiento
```

No combinar fases sin aprobación. Al terminar cada fase:

1. reportar archivos modificados;
2. reportar decisiones y riesgos;
3. ejecutar pruebas enfocadas;
4. ejecutar `python -m pytest`;
5. ejecutar `git diff --check`;
6. sugerir el Conventional Commit;
7. detenerse para revisión.
