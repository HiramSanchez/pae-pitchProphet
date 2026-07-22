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
