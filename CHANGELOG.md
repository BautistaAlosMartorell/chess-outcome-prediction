# Changelog

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
