# Guía explicativa del código — Pipeline de partidas de ajedrez

Este documento explica el código que sostiene la Entrega 1. Su objetivo es servir como
base para una explicación oral o para extenderla a un PDF. No reemplaza al código: lo
traduce a decisiones de ingeniería de datos.

La pregunta de la entrega es: **¿el grupo tiene un pipeline automatizado que produce un
dataset válido sin intervención manual?** El archivo que orquesta esa respuesta es
`dags/pipeline_ajedrez_dag.py`; los módulos de `src/` hacen el trabajo de datos.

## 1. Vista global: qué ocurre en una corrida

```text
PubAPI de Chess.com
        |
        v
listar_jugadores  -- selección automática por banda de ELO
        |
        v
descarga_usuario x N  -- fan-out: una tarea por cuenta
        |
        v
consolidar_descarga
        |
        v
limpieza_y_parseo
        |
        v
feature_engineering
        |
        v
verificar_calidad
        |
        v
exportar_dataset
        |
        v
Parquet completo + CSV de muestra + resumen JSON
```

La descarga se ejecuta en paralelo por cuenta; después el flujo es lineal. No se puede
limpiar una partida que aún no fue descargada, ni se debe publicar un dataset que no pasó
los controles de calidad.

### Relación entre el DAG y `src/`

| Parte | Responsabilidad | Archivo principal |
|---|---|---|
| Orquestación | Define tareas, dependencias, reintentos y estado en Airflow | `dags/pipeline_ajedrez_dag.py` |
| Configuración | Centraliza seeds, filtros, rutas, umbrales y política de selección | `config/config.yaml` |
| Selección | Arma la lista de jugadores por banda de ELO (seeds + oponentes validados) | `src/player_selection.py` |
| Descarga | Consulta la PubAPI y guarda los JSON crudos | `src/download_data.py` |
| Limpieza | Parsea PGN, deduplica, tipa y filtra partidas | `src/clean_data.py` |
| Features | Crea variables derivadas de ELO, ritmo y apertura | `src/feature_engineering.py` |
| Exportación | Escribe artefactos finales y el resumen | `src/pipeline.py` |
| Utilidades | Carga YAML y configura logs | `src/utils.py` |

Airflow **no reemplaza** a pandas ni a los módulos de `src/`: solo indica cuándo y en qué
orden se los ejecuta, dejando una corrida visible y auditables sus logs.

## 2. Preparación del archivo DAG

### Imports

```python
from __future__ import annotations

import logging
import os
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

log = logging.getLogger(__name__)
```

- `from __future__ import annotations` habilita el manejo diferido de anotaciones de
  tipos. Por ejemplo, `-> list[str]` documenta que una función devuelve una lista de
  textos. No altera la lógica de datos, pero hace más claro el contrato de cada función.
- `logging` permite registrar mensajes asociados a cada tarea en la UI de Airflow. Se
  usa `log.info(...)` en lugar de `print(...)` para que los logs puedan inspeccionarse
  después de la corrida.
- `os` se usa para cambiar el directorio de trabajo del proceso.
- `Path` representa rutas de forma segura y legible. `Path("/a") / "b"` produce
  `/a/b` sin concatenar strings manualmente.
- `pendulum` construye fechas con zona horaria, que Airflow usa para su planificación.
- `dag` y `task` son decoradores de la API TaskFlow de Airflow 3: convierten funciones
  Python en un DAG y en tareas observables, respectivamente.
- `__name__` es el nombre del módulo actual; ayuda a identificar el origen de cada log.

### El directorio de trabajo dentro de Docker

```python
PROJECT_ROOT = "/project"

def _enter_project_root() -> None:
    """Set the working directory to the mounted project root."""
    os.chdir(PROJECT_ROOT)
```

El worker de Airflow arranca en `/opt/airflow`, pero el proyecto compartido entre la
máquina anfitriona y los contenedores está montado en `/project`. Si una tarea buscara
`data/raw` desde el directorio equivocado, podría escribir archivos dentro del contenedor
en lugar de hacerlo en el repositorio. Por eso cada tarea llama a `_enter_project_root()`
antes de tocar archivos.

**Cómo explicarlo:** “Docker aísla el entorno de ejecución. Fijamos `/project` como raíz
para que las rutas de configuración, datos y código apunten al volumen compartido y los
artefactos sean persistentes fuera del contenedor.”

### Argumentos por defecto y rutas

```python
DEFAULT_ARGS = {
    "owner": "proyecto-integrador",
    "retries": 1,
    "email_on_failure": False,
}

CONFIG_PATH = "/project/config/config.yaml"
RAW_DIR = Path("/project/data/raw")
PROCESSED_DIR = Path("/project/data/processed")
INTERIM_PATH = PROCESSED_DIR / "_interim_clean.parquet"
```

- `owner` es metadato de mantenimiento.
- `retries: 1` permite a Airflow reintentar una tarea completa que falló.
- `email_on_failure: False` evita correos automáticos; los fallos se revisan en la UI y
  en los logs.

Hay dos niveles distintos de reintentos:

| Nivel | Qué reintenta |
|---|---|
| `requests` dentro de `DataDownloader` | Una request HTTP puntual, por ejemplo ante 429 o 5xx. |
| Airflow | La tarea completa si terminó en error. |

`INTERIM_PATH` es un Parquet temporal. Lo escribe la limpieza, lo vuelve a escribir la
tarea de features, lo lee calidad y finalmente lo consume exportación. Al final se borra.

## 3. El decorador `@dag`

```python
@dag(
    dag_id="pipeline_ajedrez_chesscom",
    description="Pipeline completo: descarga Chess.com → limpieza → features → CSV verificado",
    default_args=DEFAULT_ARGS,
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    tags=["ajedrez", "utn-frm", "entrega-1"],
    doc_md=__doc__,
)
def pipeline_ajedrez_chesscom():
    ...
```

El decorador declara ante Airflow que la función siguiente construye un DAG. No descarga
partidas cuando Airflow lee este archivo: registra el grafo para que aparezca en la UI.

| Parámetro | Significado en este proyecto |
|---|---|
| `dag_id` | Nombre único que aparece en Airflow: `pipeline_ajedrez_chesscom`. |
| `description` | Explicación breve visible en la interfaz. |
| `default_args` | Valores comunes para las tareas, como reintentos. |
| `schedule=None` | No hay corridas periódicas; se dispara manualmente. |
| `start_date` | Fecha desde la que Airflow consideraría el DAG para planificación automática. No define qué partidas descarga. |
| `catchup=False` | Si algún día se programa el DAG, no crea automáticamente todas las corridas históricas pendientes. |
| `tags` | Etiquetas para encontrarlo en la UI. |
| `doc_md=__doc__` | Publica el docstring inicial del archivo como documentación Markdown del DAG. |

`start_date` y `catchup` importan sobre todo para DAGs con schedule. Con `schedule=None`
no se generan corridas automáticas: la ventana de datos de Chess.com la define
`download.until_month` en `config.yaml`, no `start_date`.

## 4. `listar_jugadores`: selección automática y entrada del fan-out

```python
@task(task_id="listar_jugadores")
def listar_jugadores() -> list[str]:
    import pandas as pd
    from src.player_selection import PlayerSelector, write_manifest
    from src.utils import load_config

    _enter_project_root()
    config = load_config(CONFIG_PATH)
    parquet_path = Path(config["paths"]["clean_parquet"])
    selector = PlayerSelector(config)

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)          # extrae oponentes ya observados
    else:
        df = selector.discover_opponents_from_api() # bootstrap: descubre por la PubAPI

    jugadores, result = selector.build_username_list(df)
    write_manifest(result, Path(config["player_selection"]["manifest_path"]))
    log.info("Jugadores a descargar (%d): %s", len(jugadores), jugadores)
    return jugadores
```

Esta tarea ya no lee una lista fija del YAML: **selecciona los jugadores automáticamente por
banda de ELO** (ver [`criterio-seleccion-jugadores.md`](criterio-seleccion-jugadores.md)).
Funciona en dos modos:

- **Selección completa:** si existe el Parquet de una corrida anterior, extrae los oponentes
  observados en el dataset, los valida contra la PubAPI y elige hasta 20 por banda.
- **Bootstrap (primera corrida):** si no hay Parquet previo, descubre oponentes de los seeds
  consultando la PubAPI (`discover_opponents_from_api`).

En ambos casos la lista final es `seeds + seleccionados` (sin duplicados) y se guarda un
manifiesto auditable en `data/processed/player_selection_manifest.yaml`. Los imports de
módulos del proyecto se hacen dentro de la tarea para que ocurran en el worker cuando la
tarea se ejecuta, no cuando Airflow analiza el archivo para dibujar el DAG.

Ejemplo de retorno:

```python
["RebeccaHarris", "erik", "AnnaCramling", ..., "hikaru", "otro_oponente", ...]
```

Esta lista es la entrada para el mapeo dinámico de la descarga. Su longitud es variable: el
fan-out se adapta solo a cuántos jugadores devuelva la selección.

## 5. `.expand()`: mapeo dinámico y paralelismo controlado

Al final de la función del DAG aparece:

```python
jugadores = listar_jugadores()
resultados = descarga_usuario.expand(username=jugadores)
```

`.expand()` es **dynamic task mapping**. Si `jugadores` contiene N nombres, Airflow crea N
instancias de la misma tarea:

```text
descarga_usuario[RebeccaHarris]
descarga_usuario[erik]
descarga_usuario[AnnaCramling]
...
descarga_usuario[hikaru]
```

Cada instancia recibe un único argumento:

```python
descarga_usuario(username="hikaru")
```

Eso es un **fan-out**: un trabajo se abre en muchas ramas independientes. Cuando todas
terminan, `consolidar_descarga` vuelve a reunir los resultados: es el **fan-in**.

```python
@task(
    task_id="descarga_usuario",
    map_index_template="{{ username }}",
    max_active_tis_per_dag=3,
)
def descarga_usuario(username: str) -> dict:
    ...
```

- `map_index_template` hace que la UI muestre el username en lugar de índices como `[0]`
  o `[1]`.
- `max_active_tis_per_dag=3` permite como máximo tres instancias simultáneas de **esta
  tarea**. Es una protección ante el rate limit de la API de Chess.com.

No se eligió `max_active_tasks=8` en el DAG porque no es equivalente. Esa configuración
limitaría el total de tareas activas de todo el DAG, pero permitiría ocho descargas al
tiempo: exactamente el comportamiento que se quiere evitar. Un límite global de tres
también sería menos preciso porque restringiría tareas futuras que no llaman a Chess.com.

**Cómo explicarlo:** “Paralelizamos lo independiente —las cuentas—, pero limitamos a tres
las consultas concurrentes a la API externa. Así ganamos tiempo sin sobrecargar la fuente.”

## 6. `descarga_usuario`: ingesta y capa Bronze

```python
@task(...)
def descarga_usuario(username: str) -> dict:
    from airflow.sdk import get_current_context
    from src.download_data import DataDownloader
    from src.utils import load_config

    get_current_context()["username"] = username
    _enter_project_root()
    config = load_config(CONFIG_PATH)
    downloader = DataDownloader(config)
    dest = downloader.dest_for(username)
    try:
        path = downloader.download_user_games(username, dest)
        games = downloader.count_games(path)
        return {"username": username, "path": str(path), "games": games, "ok": True}
    except Exception as exc:
        log.warning("Descarga de %s falló, se saltea: %s: %s", username, type(exc).__name__, exc)
        return {"username": username, "path": None, "games": 0, "ok": False}
```

La tarea delega la lógica de red a `DataDownloader`:

```text
DataDownloader.download_user_games()
  1. consulta /games/archives;
  2. recorre archivos mensuales desde el más reciente hacia atrás;
  3. ignora meses posteriores a `until_month`;
  4. conserva partidas rated, estándar y bullet/blitz/rapid;
  5. guarda hasta 1.000 partidas por cuenta.
```

El resultado se guarda en:

```text
data/raw/chesscom_<username>_raw.json
```

Ese JSON se conserva tal como llegó de Chess.com: es la **capa Bronze**.

### Idempotencia

Dentro de `download_user_games()`:

```python
if dest.exists():
    logger.info("Ya existe %s — se saltea la descarga de %s.", dest, username)
    return dest
```

Si el JSON ya existe, no se vuelve a pedir. Esto reduce llamadas innecesarias a la API y
hace repetible el pipeline sobre la misma ventana de datos.

### Tolerancia a fallos

Una cuenta que responde 404, no tiene partidas o falla por red no derriba de inmediato todo
el fan-out. La tarea devuelve `ok=False`; después se decide si el conjunto total sigue
siendo suficiente. Esto es degradación controlada, no ignorar el error: el fallo queda en
los logs y se considera en la consolidación.

## 7. `consolidar_descarga`: fan-in y mínimos de calidad de ingesta

```python
@task(task_id="consolidar_descarga")
def consolidar_descarga(resultados: list[dict]) -> dict[str, str]:
    ...
    ok = {r["username"]: r["path"] for r in resultados if r["ok"]}
    failed = {r["username"]: "descarga falló" for r in resultados if not r["ok"]}
    total_games = sum(r["games"] for r in resultados if r["ok"])
    downloader.enforce_minimums(len(ok), total_games, failed)
    return ok
```

Recibe una lista de resultados, uno por cuenta. Separa las cuentas exitosas de las
fallidas, suma partidas crudas y aplica los umbrales de `config.yaml`:

```yaml
min_users_ok: 8
min_total_games: 1500
```

Si hay menos de ocho cuentas exitosas o menos de 1.500 partidas crudas, lanza un error y
el DAG queda en rojo. Si aprueba, devuelve solo las rutas Bronze exitosas.

La decisión ocurre **después** del fan-out porque antes no se conoce el estado global. Es
una regla de calidad sobre la ingesta: se tolera una falla aislada, pero no se publica un
dataset que perdió demasiado volumen.

## 8. `limpieza_y_parseo`: Bronze a Silver

```python
@task(task_id="limpieza_y_parseo")
def limpieza(raw_paths: dict[str, str]) -> int:
    from src.clean_data import DataCleaner
    ...
    cleaner = DataCleaner(config)
    df, raw_count = cleaner.clean(paths)
    df = cleaner.optimize_dtypes(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM_PATH, index=False)
    return raw_count
```

Esta tarea toma las rutas JSON Bronze y llama a `DataCleaner`. Ese módulo:

| Método / regla | Resultado |
|---|---|
| `parse_game()` | Extrae metadatos y movimientos desde el PGN de cada partida. |
| `parse_all()` | Concatena cuentas y elimina partidas repetidas por `GameUrl`. |
| `parse_result()` | Convierte `1-0`, `0-1` y `1/2-1/2` a `resultado`. |
| `parse_numeric_fields()` | Convierte ELO y controles de tiempo a números. |
| `count_moves()` | Crea `cantidad_jugadas` contando medio-movimientos (*plies*). |
| `parse_date()` | Convierte `Date` a fecha; fechas inválidas pasan a `NaT`. |
| `filter_invalid_rows()` | Conserva solo partidas standard, rated, con resultados/ELO/fecha y al menos cinco plies. |
| `normalize_termination()` | Elimina usernames del motivo de finalización y lo normaliza. |
| `optimize_dtypes()` | Usa enteros compactos, categorías y fechas correctas. |

La clave primaria es `GameUrl`. Es posible que dos usuarios configurados hayan jugado entre
sí; la misma partida aparecería en los dos JSON. La deduplicación por esa URL garantiza
que una fila siga representando una sola partida.

El filtro de cinco plies quita abandonos administrativos o casi inmediatos: no aportan
señal representativa para la duración ni para el resultado de una partida jugada.

### La excepción tidy: `moves_text`

`moves_text` guarda muchas jugadas dentro de una celda. Es una concesión explícita: partir
las jugadas en filas rompería la unidad de análisis “una fila = una partida”, y abrirlas
en columnas tendría ancho variable. Para el modelado de duración se usa la variable atómica
derivada `cantidad_jugadas`.

## 9. Parquet temporal y por qué no se usa XCom para el DataFrame

```python
df.to_parquet(INTERIM_PATH, index=False)
```

Un DataFrame de pandas vive en la memoria del worker mientras su tarea está ejecutándose.
Al finalizar, la siguiente tarea puede correr en otro worker y no tiene acceso a esa
memoria. Por eso se lo serializa en un archivo compartido:

```text
limpieza escribe _interim_clean.parquet
  -> features lo lee y lo vuelve a escribir
  -> calidad lo lee
  -> exportación lo lee y luego lo elimina
```

Por XCom viajan solo valores pequeños como `raw_count`, estados y rutas. No viajan miles de
filas. XCom es almacenamiento de metadatos de Airflow, no el lugar para mover DataFrames.

Parquet se elige porque es un formato binario y columnar: ocupa menos que CSV en muchos
casos, es rápido para pandas y conserva tipos como fechas, enteros y categorías. CSV queda
como formato de muestra legible; JSON conserva la fidelidad de la respuesta cruda.

| Formato | Uso en este proyecto |
|---|---|
| JSON | Bronze: respuesta de la API tal como llega. |
| Parquet | Dataset completo limpio y comunicación entre tareas. |
| CSV | Muestra humana de hasta 5.000 filas. |

## 10. `feature_engineering`: columnas derivadas

```python
@task(task_id="feature_engineering")
def feature_engineering(raw_count: int) -> int:
    import pandas as pd
    from src.feature_engineering import FeatureEngineer

    df = pd.read_parquet(INTERIM_PATH)
    engineer = FeatureEngineer(config)
    df = engineer.transform(df)
    df.to_parquet(INTERIM_PATH, index=False)
    return raw_count
```

`raw_count` no se usa para transformar: se recibe para crear la dependencia con limpieza y
para conservar ese número hasta el resumen de exportación.

`FeatureEngineer.transform()` agrega:

```text
diferencia_elo = WhiteElo - BlackElo
elo_promedio = (WhiteElo + BlackElo) / 2
nivel_promedio = banda de ELO
es_sorpresa = gana el jugador de menor ELO
familia_apertura = clasificación de la letra ECO
```

Estas variables vuelven más interpretable el análisis exploratorio. Sin embargo, antes de
modelar hay que controlar fuga de información:

- `es_sorpresa` se calcula con `resultado`, así que **no puede** ser feature para predecir
  `resultado`; serviría solo como descripción posterior al hecho.
- Chess.com informa ELO posterior a la partida. `WhiteElo`, `BlackElo` y sus derivados
  pueden contener información posterior al resultado. Es una limitación documentada que
  debe tratarse en Entrega 2/3.

Esto no invalida la Entrega 1: el pipeline tiene que producir y documentar el dataset. Pero
sí condiciona la tabla de variables candidatas y el diseño del futuro modelo.

## 11. `verificar_calidad`: validación antes de publicar

```python
@task(task_id="verificar_calidad")
def verificar_calidad(raw_count: int) -> int:
    df = pd.read_parquet(INTERIM_PATH)
    ...
```

La tarea usa `assert`: si una condición falla, Airflow marca la tarea roja. Como
`exportar_dataset` depende de ella, no se escriben artefactos finales de un dataset que no
cumple. Es un **quality gate** o portero de calidad.

| Criterio | Verificación en código | Sentido de calidad |
|---|---|---|
| Clave única | `df["GameUrl"].is_unique` | Una fila por partida; sin duplicación. |
| Volumen | `len(df) >= quality.min_final_games` | Dataset suficiente tras limpieza. |
| Ancho | `df.shape[1] >= 5` | Hay suficientes variables útiles. |
| Tipos | numérico + categórico + fecha | Dataset apto para análisis y modelos. |
| Nulos | solo columnas declaradas | Completitud conocida y documentada. |
| Columnas vacías | ninguna al 100% nula | No se exporta información inexistente. |
| Targets | `resultado` y `cantidad_jugadas` sin nulos | Objetivos modelables y completos. |

Además valida que `WhiteElo` y `BlackElo` estén entre 100 y 3.600. Es una verificación
extra de precisión: ratings negativos, cero o absurdamente altos señalarían corrupción o
un error de parseo.

El criterio de volumen usa el mínimo explícito `quality.min_final_games` (hoy **1.500**),
no un porcentaje de la descarga. Son contratos distintos: `download.min_total_games`
(también 1.500) es el piso de la **descarga cruda**, mientras que `quality.min_final_games`
es el piso del dataset **limpio y analizable**. La limpieza retiene ~99,85 %, así que el
final queda cómodamente por encima del mínimo.

Por último guarda un baseline de volumen en una Variable de Airflow. Si el volumen cambia
más de 5% respecto a la última corrida exitosa, avisa en logs. No corta el DAG porque el
cambio puede ser deliberado, por ejemplo al actualizar `until_month`; es una medida de
observabilidad.

## 12. `exportar_dataset`: artefactos finales

```python
@task(task_id="exportar_dataset")
def exportar(raw_count: int) -> str:
    df = pd.read_parquet(INTERIM_PATH)

    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
    df.sample(n=sample_size, random_state=config["processing"]["random_state"]).to_csv(
        sample_path, index=False
    )
    summary = build_summary(df, raw_count)
    ...
    INTERIM_PATH.unlink(missing_ok=True)
    return str(parquet_path)
```

Solo se ejecuta después de aprobar calidad. Genera:

| Archivo | Contenido | Función |
|---|---|---|
| `partidas_ajedrez_clean.parquet` | Todas las filas limpias y validadas | Artefacto principal para análisis. |
| `partidas_ajedrez_clean_sample.csv` | Muestra determinística de hasta 5.000 filas | Inspección y demostración. |
| `data_summary.json` | Filas crudas/finales, retención, targets, nulos y métricas | Evidencia de calidad y trazabilidad. |

La muestra usa `random_state=42`, por lo que el mismo dataset produce la misma muestra.

### Bronze, Silver y Gold en este proyecto

- **Bronze:** JSON de `data/raw/`, sin transformar, guardado tal como llega de la API.
- **Silver:** el Parquet final completo, limpio, tipado, deduplicado y validado. El CSV
  es una muestra de esa misma tabla, no necesariamente el dataset completo.
- **Gold:** todavía no es un artefacto formal del proyecto. Será una tabla estable y
  específica para un consumidor final: por ejemplo, features permitidas para el modelo de
  Entrega 3 o agregados para la aplicación de Entrega 4.

`_interim_clean.parquet` no es el Silver final: es un artefacto temporal entre tareas y se
elimina al terminar correctamente la exportación.

## 13. La construcción del grafo

```python
jugadores = listar_jugadores()
resultados = descarga_usuario.expand(username=jugadores)
raw_paths = consolidar_descarga(resultados)
raw_count = limpieza(raw_paths)
raw_count_fe = feature_engineering(raw_count)
raw_count_ok = verificar_calidad(raw_count_fe)
exportar(raw_count_ok)
```

En la API TaskFlow, estas llamadas construyen dependencias y objetos de referencia a los
resultados de tareas; no ejecutan todo inmediatamente al importar el archivo. Pasar el
retorno de una tarea como argumento de otra crea las flechas del grafo.

Finalmente:

```python
pipeline_ajedrez_chesscom()
```

registra el DAG cuando Airflow procesa el archivo. La ejecución real sucede cuando se
dispara una corrida desde la UI o CLI.

## 14. Respuestas breves para la defensa

**¿Qué es una fila?** Una partida individual rated, estándar y de ritmo bullet, blitz o
rapid, donde participa una de las cuentas configuradas.

**¿Cuál es la clave?** `GameUrl`, porque identifica una partida concreta. Se deduplica y
se valida que sea única.

**¿Por qué no se manda el DataFrame por XCom?** Porque XCom es para metadatos pequeños;
el DataFrame se escribe como Parquet compartido entre workers.

**¿Por qué `.expand()`?** Porque cada cuenta se puede descargar de forma independiente.
Airflow crea una instancia por username sin duplicar código.

**¿Por qué máximo tres descargas?** Para reducir la tasa de requests simultáneas a la API
de Chess.com y evitar rate limiting.

**¿Qué ocurre si falla una cuenta?** Se registra el fallo y se continúa; el DAG falla solo
si no se cumplen los mínimos globales de ocho usuarios y 1.500 partidas crudas.

**¿Cómo se sabe que el dato final es válido?** `verificar_calidad` corre antes de exportar
y detiene el DAG si falla cualquiera de los siete criterios.

**¿Qué pasa si el parser estaba mal?** Se conserva Bronze. Se corrige el código y se
regenera Silver sin volver a depender de la API.

**¿Qué archivos son Silver?** El Parquet completo es el dataset Silver principal; el CSV
es una muestra para inspección y el JSON es su resumen de calidad.

**¿Qué no se debe usar para modelar `resultado`?** `es_sorpresa`, porque usa el resultado
para calcularse. Los ELO también requieren cuidado porque Chess.com los informa después de
la partida.
