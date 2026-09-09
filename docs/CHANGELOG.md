# Changelog

## Corrección del criterio de volumen final (2026-09-09)

- **Qué:** el criterio 2 de `verificar_calidad` ahora exige el mínimo explícito
  `quality.min_final_games: 4000`. Se eliminó el cálculo `min_total_games * 0.9`.
- **Por qué:** `download.min_total_games` es el piso de la **descarga cruda** y no debe
  redefinir el tamaño mínimo del dataset **analizable**. Son contratos distintos: la
  descarga debe traer al menos 4.000 partidas y, tras limpieza, el dataset final también
  debe conservar al menos 4.000. Si el segundo no se cumple, el log informa las partidas
  válidas, el mínimo final y el total crudo leído.
- **Además:** el task id `feature_engineering` se renombró a
  `ingenieria_de_caracteristicas` para que todas las tareas visibles del DAG estén en
  español.

### Ajuste del rango plausible de ELO

- **Qué:** el techo de la verificación de ELO sube de `3600` a `4000`.
- **Por qué:** 3.600 era un margen elegido a partir de picos históricos conocidos, no un
  máximo oficial de Chess.com. El nuevo techo mantiene la detección de valores corruptos
  (cero, negativos o absurdamente altos) sin rechazar un futuro récord válido.

## Mejoras del diagnóstico sobre el pipeline (2026-09-07)

Serie de mejoras sobre la base ya migrada a Airflow 3.3 (branch `feat/mejoras-diagnostico`),
implementadas de menor a mayor riesgo, con una corrida completa en verde después de cada una.
Todo lo nuevo usa sintaxis de Airflow 3 (`airflow.sdk`, `schedule=`, dynamic task mapping).

### Punto 1 — Umbral de volumen anclado al gate de descarga (`verificar_calidad`)

- **Qué:** el criterio 2 dejó de usar el piso hardcodeado `len(df) >= 1_000` (heredado del
  ejemplo de cátedra) y ahora se calcula como `int(min_total_games * 0.9)` leyendo
  `download.min_total_games` del config → **3600** con la config actual.
- **Por qué:** 1 000 no tenía relación con nuestro caso (baseline real: 7204 filas). El gate
  de descarga ya garantiza ≥ 4000 partidas crudas; la limpieza retiene ~99.85 %, así que el
  piso limpio ronda ese número. El 0.9 deja margen para variación normal de filtrado sin dejar
  de discriminar una caída real. Al leerlo del config, criterio 2 y gate de descarga quedan
  acoplados: si se mueve `min_total_games`, el umbral se mueve solo.
- **Verificación:** `airflow dags test` en verde — 7204 filas ≥ 3600, los 7 criterios OK.

### Punto 2 — Validar antes de exportar (reordenar el grafo)

- **Qué:** el grafo pasó de `… → exportar_dataset → verificar_calidad` a
  `… → verificar_calidad → exportar_dataset`. `verificar_calidad` ahora valida el parquet
  **intermedio** (`_interim_clean.parquet`, ya con features) y retorna `raw_count`;
  `exportar_dataset` corre después y sólo si la validación pasó.
- **Por qué:** antes se escribían Parquet + CSV + `data_summary.json` y recién después se
  validaba releyendo el Parquet final. Si un criterio fallaba, los artefactos de un dataset
  inválido ya estaban en disco. Validando el intermedio primero, un dataset que no cumple
  **no llega a materializarse**. El intermedio y el final tienen el mismo contenido, así que
  la validación es equivalente.
- **Verificación:** `airflow dags test` en verde — mismos 7 criterios, 7204 filas × 27
  columnas; el orden de tareas ahora es `verificar_calidad` → `exportar_dataset`.

### Punto 3 — Rango plausible de ELO (dimensión precisión)

- **Qué:** `verificar_calidad` agrega un chequeo `[100, 3600]` para `WhiteElo` y `BlackElo`.
  Es una extensión de la dimensión precisión, etiquetada aparte para **no** alterar la
  numeración de los 7 criterios de cátedra.
- **Por qué:** el rating Glicko de Chess.com en vivo va de ~100 (cuentas nuevas/débiles) a
  ~3600 (aire sobre el pico élite en bullet, Hikaru ~3400-3500). Un valor fuera de ese rango
  no es un jugador real: es corrupción del dato (0, negativos, parseo mal hecho). En la
  corrida validada los rangos observados fueron **732-3468 (White) y 218-3469 (Black)**, bien
  dentro del rango elegido.
- **Verificación:** `airflow dags test` en verde — el chequeo de precisión pasa junto con los
  7 criterios.

### Punto 4 — Categorías fallback visibles en `data_summary.json`

- **Qué:** `build_summary` (`src/pipeline.py`, compartido por DAG y CLI) agrega
  `categorias_fallback` con el conteo y porcentaje de filas en `familia_apertura="Desconocida"`
  y `Termination="otro"`.
- **Por qué:** esas etiquetas son reemplazos cuando el crudo no trae el dato (ECO fuera de A-E,
  motivo de finalización no reconocido). Son missingness disfrazada de categoría: contra la
  dimensión completitud conviene que estén reportadas, no invisibles, aunque sean una decisión
  de diseño válida (no se imputan ni se descartan). En la corrida validada ambas dan **0 filas
  (0 %)**, lo que confirma explícitamente que no hay nulos encubiertos.
- **Verificación:** `airflow dags test` en verde; `data_summary.json` incluye la nueva sección.

### Punto 5 — Fallback de `limpieza_y_parseo` robusto a archivos faltantes

- **Qué:** cuando el XCom `raw_paths` viene vacío, la reconstrucción de rutas ahora filtra por
  `.exists()` en disco (sólo usuarios cuyo JSON crudo realmente está) y, si no queda ninguno,
  corta con un `FileNotFoundError` claro en vez de reventar en el parseo.
- **Por qué:** el config lista los 8 usuarios objetivo, pero la descarga tolera fallos por
  usuario (`min_users_ok`). Reconstruir a ciegas para los 8 incluía cuentas que pudieron no
  descargarse → `FileNotFoundError` al parsear un archivo inexistente. Ahora el fallback
  refleja lo que hay en disco.
- **Verificación:** `airflow dags test` en verde (ruta normal con `raw_paths` presente intacta).

### Punto 6 — Descarga paralela por cuenta con `.expand()` (dynamic task mapping)

- **Qué:** la tarea `descarga_partidas` (un `for` secuencial dentro de una sola tarea) se
  reemplazó por tres tareas:
  - `listar_usuarios` → lista de cuentas del config (fuente del `.expand()`).
  - `descarga_usuario` **mapeada** por cuenta (`.expand(username=...)`), con
    `map_index_template="{{ username }}"` para que la UI muestre el username en cada índice,
    tolerante a su propio fallo (devuelve un dict de estado, no re-lanza).
  - `consolidar_descarga` (reduce) → evalúa `min_users_ok`/`min_total_games` **después** del
    fan-out y arma las rutas crudas para `limpieza_y_parseo`.
  - En `src/download_data.py` se factoró la lógica de mínimos a `enforce_minimums(...)`
    (reusada por el CLI `download_all` y por el DAG) y se agregó `dest_for(...)` /
    `count_games(...)` (antes `_count_games`).
- **Por qué:** el `for` secuencial evaluaba los mínimos dentro del loop y no aprovechaba que
  las cuentas son independientes. Con `.expand()` cada cuenta es una task instance propia
  (reintentos y logs por cuenta), la tolerancia a fallos se evalúa una sola vez al final, y
  Airflow puede paralelizar la descarga.
- **Paralelismo:** `max_active_tis_per_dag=3` en `descarga_usuario`. **No es arbitrario:** cada
  cuenta emite requests en serie con `request_delay=0.25s` y backoff ante 429/5xx; correr las 8
  en paralelo multiplicaría ×8 la tasa de requests y dispararía rate-limiting. Con 3 en paralelo
  el burst queda acotado, el backoff absorbe algún 429 y en cold-run rinde ~3× sobre el serial;
  en re-runs es indistinto (las descargas idempotentes se saltean).
- **Verificación:** `airflow dags test` en verde — 8 instancias mapeadas (índices `0..7` por
  username), `consolidar_descarga` reporta 8/8 usuarios OK y 7215 partidas crudas, dataset final
  7204 × 27. Las 7 pruebas unitarias siguen en verde (incluida la de tolerancia a fallos del CLI).

### Punto 7 — Observabilidad de volumen con Airflow Variable (dimensión actualidad)

- **Qué:** `verificar_calidad` guarda el volumen de la última corrida exitosa en la Variable
  `pipeline_ajedrez_volumen_baseline` y **avisa** (log de warning, no falla) si la corrida
  actual se desvía > 5 % del baseline.
- **Por qué:** `download.until_month` está congelado para esta entrega (`"2026-08"`), así que la
  fuente no incorpora partidas nuevas y el volumen debería ser estable entre corridas. Con ese
  contexto un desvío > 5 % señala un cambio real (until_month movido, filtro tocado, fuente
  alterada) y merece revisión — pero no invalida el dataset por sí solo, por eso avisa y no
  rompe. Cuando en Entrega 2 se descongele until_month habrá que revisar el umbral.
- **Bug encontrado y corregido:** `Variable.set(key, len(df))` pasaba un `int`; la Task
  Execution API de Airflow 3 (`PutVariable`) exige que el value sea `str` y rompía con
  `ValidationError` **sólo bajo el worker real** — `airflow dags test` corre in-process y no
  valida ese contrato, así que lo dejaba pasar. Se guarda como `str(len(df))` y se relee con
  `int(...)`. **Lección:** interacciones con la Execution API (Variables, etc.) se validan con
  una corrida disparada por el scheduler, no sólo con `dags test`.
- **Verificación:** corrida real disparada por el scheduler (CeleryExecutor), no `dags test`.
  1ª corrida establece el baseline (7204) y todas las tareas quedan en `success`; 2ª corrida
  loguea "Volumen 7204 dentro del ±5 % del baseline 7204" (info, sin warning). Ambas ejercitan
  los 7 puntos juntos bajo el executor real.

## Migración Airflow 2.10.5 → Airflow 3.3 (2026-09-07)

Se migró el orquestador de **Apache Airflow 2.10.5 a 3.3.0** para que el código hable el
mismo idioma que la cátedra (Unidad 1, `02-airflow-unidad1.md`). **No se tocó la lógica
de datos** (`src/`): solo el orquestador y su entorno. La corrida en Airflow 3 reproduce
exactamente el dataset validado en Airflow 2 (**7215 crudas → 7204 finales, 27 columnas,
0 nulos**, mismas distribuciones) y pasa los mismos 7 criterios de calidad.

### Qué cambió

**Imagen base (`Dockerfile`)**
- `ARG AIRFLOW_VERSION`: `2.10.5` → `3.3.0`.
- Los providers `standard`, `celery` y `fab` vienen bundled en la imagen base 3.3.0; no
  se agregan a `requirements.txt`. Las dependencias del pipeline (pandas, numpy, etc.)
  quedan igual.

**DAG (`dags/pipeline_ajedrez_dag.py`) — reescrito a la TaskFlow API**
- `from airflow import DAG` + `PythonOperator` → `from airflow.sdk import dag, task`
  (`PythonOperator` estándar ahora vive en `airflow.providers.standard.operators.python`).
- `from airflow.utils.dates import days_ago` (removido en Airflow 3) → `import pendulum`
  con `start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires")`.
- Parámetro del DAG `schedule_interval=None` → `schedule=None`.
- Las 5 tareas pasan de `PythonOperator` a funciones `@task`; las dependencias salen de
  encadenar returns (`raw_paths = descarga()` → `limpieza(raw_paths)` → …). Se
  eliminaron los `xcom_push`/`xcom_pull` manuales. **XCom sigue llevando solo metadatos**
  (rutas y conteos); el DataFrame sigue viajando por disco (`_interim_clean.parquet`).

**Stack (`docker-compose.yml`) — servicios y entorno de Airflow 3**
- `webserver` → `airflow-apiserver` (`command: api-server`), healthcheck contra
  `/api/v2/monitor/health`.
- Nuevos servicios: `airflow-dag-processor` (`command: dag-processor`, parseo de DAGs
  como proceso aparte) y `airflow-triggerer` (`command: triggerer`).
- Auth: se agregó `AIRFLOW__CORE__AUTH_MANAGER=…FabAuthManager` (mantiene el login
  admin/admin) y se **quitó** `AIRFLOW__API__AUTH_BACKENDS` (`basic_auth`/`session`,
  removido en Airflow 3).
- Task Execution API (nueva en Airflow 3): se agregó
  `AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow-apiserver:8080/execution/` y
  `AIRFLOW__API_AUTH__JWT_SECRET` (los workers firman con JWT contra el api-server).
- Healthchecks de scheduler/dag-processor/triggerer con
  `airflow jobs check --job-type … --local`.
- `airflow-init` usa el entrypoint estándar (`_AIRFLOW_DB_MIGRATE` +
  `_AIRFLOW_WWW_USER_CREATE`) en vez del `airflow users create` manual.

**Base de metadatos**
- La DB **se recreó de cero** (`docker compose down -v` antes de migrar): `airflow db
  migrate` crea el esquema 3.x sobre una base limpia. No es un upgrade in-place del
  esquema de Airflow 2. Los datos del pipeline (`data/`) no se ven afectados: viven en un
  bind mount, no en el volumen de metadatos.

**Entorno (`.env.example`)**
- Se agregó `AIRFLOW__API_AUTH__JWT_SECRET` (con default de desarrollo).
