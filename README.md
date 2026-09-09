# Ajedrez online: ELO, apertura y ritmo como predictores del resultado

Proyecto Integrador — Ciencia de Datos (UTN FRM, 5.º año, Ingeniería en Sistemas de
Información, 2026).

## Pregunta de investigación

¿Qué combinación de nivel de ELO, apertura jugada, modalidad de ritmo
(bullet/blitz/rapid) y color de piezas predice mejor quién gana una partida de ajedrez
online, y qué tan larga es esa partida?

La unidad de análisis es una partida individual. Esta primera entrega implementa el
pipeline automatizado de ingeniería de datos: descarga, parseo, limpieza, validación,
ingeniería de características y exportación del dataset de trabajo.

## Fuente de datos

Se usa la [PubAPI oficial de Chess.com](https://www.chess.com/news/view/published-data-api),
una API pública de solo lectura que no requiere cuenta, API key ni autenticación.

Endpoints utilizados:

```text
GET https://api.chess.com/pub/player/{username}/games/archives
GET https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}
```

El primer endpoint enumera los archivos mensuales disponibles. El pipeline recorre el
segundo desde el mes más reciente hacia atrás y conserva hasta 1.000 partidas rated de
ajedrez estándar en bullet, blitz o rapid por usuario. Todas las solicitudes se hacen en
serie, tal como recomienda Chess.com; los archivos ya descargados se reutilizan.

**Ventana temporal congelada.** `config.yaml` fija `download.until_month: "2026-08"`: se
ignoran los archivos mensuales posteriores a agosto de 2026. Sin este tope, correr el
pipeline en octubre traería los meses nuevos y el dataset cambiaría de tamaño en cada
corrida. Con el tope, **una corrida desde cero (sin `data/raw/` previo) produce el mismo
conjunto de partidas** que la corrida validada. Para retomar la ingesta en curso en
entregas siguientes basta con mover el mes o ponerlo en `null`.

### Jugadores configurados

Las ocho cuentas fueron verificadas contra la API y aportan niveles distintos:

- `RebeccaHarris` — nivel club, alrededor de 1400.
- `erik` — nivel club/intermedio, alrededor de 1700.
- `AnnaCramling` — jugadora titulada y streamer, alrededor de 2400.
- `AlexandraBotez` — jugadora titulada y streamer, alrededor de 2500.
- `GothamChess` — maestro internacional y streamer, alrededor de 2900.
- `IMRosen` — maestro internacional, alrededor de 2900.
- `chessbrah` — cuenta de gran maestro/streaming, alrededor de 3200.
- `hikaru` — élite mundial, alrededor de 3400.

Los ratings son orientativos y cambian con el tiempo. La configuración viva está en
`config/config.yaml`.

### Limitación del rating (fuga de información hacia el resultado)

Chess.com entrega en cada objeto el rating del jugador **después** de que el resultado
ajustó su puntaje Glicko, no un snapshot previo a la partida. A diferencia de Lichess
(que expone el rating previo y el ajuste posterior por separado), esta API no permite
aislar el rating estrictamente anterior sin reconstruir el historial cronológico
completo de cada jugador.

En consecuencia, `WhiteElo`, `BlackElo` y todo lo derivado de ellos (`diferencia_elo`,
`elo_promedio`, `favorito`, `nivel_promedio`, `es_sorpresa`) contienen una fuga de
información hacia `resultado`, de magnitud pequeña pero sistemática, concentrada
justamente en las partidas de rating parejo. Se documenta como limitación conocida de
la fuente para el modelado de Entrega 3, no se corrige con un parche improvisado.

### Limitación de la muestra (no es una muestra aleatoria de Chess.com)

Las 8 cuentas configuradas son jugadores de nivel club a élite mundial, varias de ellas
streamers de alto seguimiento, no una muestra aleatoria de la población general de
Chess.com. Por construcción del método de descarga, el 100 % de las filas del dataset
contiene al menos una de estas 8 cuentas, y la mediana de `WhiteElo` es 2778 (nivel
Gran Maestro). Las conclusiones de las próximas entregas se formulan sobre "jugadores
de nivel intermedio a élite mundial en Chess.com", no sobre "ajedrez online" en
general.

## Por qué la fuente cumple los siete criterios

| # | Criterio | Aplicación |
|---|---|---|
| 1 | Datos tidy | El dataset final tiene una fila por partida y una columna por variable. |
| 2 | Unidad alineada | La partida es exactamente la unidad sobre la que pregunta el proyecto. |
| 3 | Algo modelable | `resultado` es el target de clasificación y `cantidad_jugadas`, el de regresión. |
| 4 | Descarga automatizada | La PubAPI se consulta sin intervención manual ni credenciales. |
| 5 | Volumen | La corrida validada produjo 7.204 partidas limpias. |
| 6 | Columnas informativas | Hay ratings, color, apertura, ritmo, tiempo, resultado, fecha y terminación. |
| 7 | Documentación | Chess.com publica endpoints, campos, códigos de respuesta y reglas de uso. |

## Estructura

```text
config/config.yaml                         parámetros y cuentas de Chess.com
data/raw/                                  JSON regenerables, ignorados por Git
data/processed/                            Parquet, sample y resumen, ignorados por Git
dags/pipeline_ajedrez_dag.py               DAG de Airflow: descarga (mapeada por cuenta) → limpieza → ingeniería de características → verificación → exportación
docker-compose.yml                         stack de Airflow 3.3 (postgres, redis, api-server, scheduler, dag-processor, triggerer, worker)
Dockerfile                                 imagen de Airflow con las dependencias del proyecto
.env.example                               plantilla de variables de entorno para la stack
notebooks/01_data_ingestion_verification.ipynb
src/download_data.py                       descarga idempotente por cuenta (el DAG la paraleliza con .expand())
src/clean_data.py                          parseo de JSON + PGN y limpieza
src/feature_engineering.py                 características analíticas derivadas
src/pipeline.py                            orquestador CLI
tests/test_chess_pipeline.py               pruebas unitarias sin acceso de red
```

## Diccionario de datos

### Variables obtenidas de Chess.com y del PGN

| Columna | Tipo | Descripción |
|---|---|---|
| `GameUrl` | str | Identificador/URL pública de la partida; se usa para deduplicar. |
| `Event` | category | Tipo de evento informado por el PGN. |
| `Date` | datetime64 | Fecha de la partida. |
| `White`, `Black` | str | Username de cada jugador. |
| `Result` | str | Resultado PGN: `1-0`, `0-1` o `1/2-1/2`. |
| `WhiteElo`, `BlackElo` | int | Rating informado por Chess.com al cierre de la partida. |
| `Variant` | str | Variante; el pipeline conserva solo ajedrez estándar. |
| `TimeControl` | str | Control de tiempo crudo, por ejemplo `180+2`. |
| `TimeClass` | category | Clase oficial: `bullet`, `blitz` o `rapid`. |
| `ECO` | category | Código ECO de la apertura. |
| `Opening` | category | Nombre derivado de la URL ECO oficial de la partida. |
| `Termination` | category | Motivo de finalización normalizado (resignation, time, checkmate, etc.), sin el username del ganador que trae el dato crudo de Chess.com. |
| `Rated` | bool | Indica si la partida afectó el rating. |
| `moves_text` | str | Jugadas en notación algebraica, sin comentarios de reloj. |

### Features generadas

| Feature | Tipo | Descripción |
|---|---|---|
| `resultado` | category | Gana blancas, gana negras o empate. Target de clasificación. |
| `cantidad_jugadas` | int | Cantidad de medio-movimientos o plies. Target de regresión. |
| `tiempo_base_seg`, `incremento_seg` | int | Componentes del control de tiempo. |
| `diferencia_elo` | int | `WhiteElo - BlackElo`. |
| `elo_promedio` | float | Rating promedio de ambos jugadores. |
| `favorito` | category | Color con mayor rating o `Ninguno`. |
| `nivel_promedio` | category | Banda de rating configurada. |
| `modalidad` | category | Bullet, Blitz o Rapid según `TimeClass`. |
| `es_sorpresa` | int8 | 1 cuando gana el jugador con menor rating. |
| `familia_apertura` | category | Familia ECO: flanco, semiabierta, abierta, cerrada, india o desconocida. |

## Cómo ejecutar

### Con Airflow (Docker) — es la forma en que se evalúa la entrega

Requiere Docker con el plugin `compose`. El stack corre sobre **Apache Airflow 3.3**
(la versión que dicta la cátedra). Un compañero que clona el repo no toca nada más que
copiar el `.env`:

```bash
git clone <repo> && cd <repo>
cp .env.example .env                 # la primera vez; .env está en .gitignore
docker compose up airflow-init       # migra la BD de metadatos (esquema 3.x) y crea el admin
docker compose up -d                 # levanta postgres, redis, api-server, scheduler, dag-processor, triggerer y worker
```

Después:

1. Abrir <http://localhost:8080> y entrar con `admin` / `admin`.
2. Buscar el DAG `pipeline_ajedrez_chesscom`, activarlo con el toggle (viene pausado) y
   dispararlo con ▶ (*Trigger DAG*).
3. La corrida lista usuarios, descarga en paralelo por cuenta y luego recorre la cadena
   `consolidar_descarga` → `limpieza_y_parseo` →
   `ingenieria_de_caracteristicas` → `verificar_calidad` → `exportar_dataset`.
   La verificación hace `assert` de los siete criterios de calidad, así que una corrida
   en verde implica un dataset válido.

Los artefactos quedan en `data/` del host (el `docker-compose.yml` monta `./data`):

```text
data/raw/chesscom_<usuario>_raw.json          capa cruda, un archivo por cuenta
data/processed/partidas_ajedrez_clean.parquet dataset final
data/processed/partidas_ajedrez_clean_sample.csv
data/processed/data_summary.json
```

Volver a disparar el DAG sin borrar `data/raw/` reutiliza los JSON ya descargados
(descarga idempotente). Para apagar la stack: `docker compose down` (conserva los
volúmenes) o `docker compose down -v` (reset total).

### Sin Docker (CLI / notebook)

Mismo pipeline, mismos módulos de `src/`, sin Airflow. Requiere Python 3.11 o superior.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # Windows: py -m venv .venv; .venv\Scripts\python.exe ...
.venv/bin/python -m src.pipeline                          # --skip-download si los JSON crudos ya existen
```

También puede abrirse `notebooks/01_data_ingestion_verification.ipynb` y ejecutarse con
**Restart & Run All**.

### Tests

```bash
python -m unittest discover -s tests
```

## Artefactos generados

- `data/processed/partidas_ajedrez_clean.parquet`
- `data/processed/partidas_ajedrez_clean_sample.csv`
- `data/processed/data_summary.json`

Corrida validada el 06/09/2026 (DAG completo en Airflow, ventana congelada hasta
agosto de 2026):

- 7.215 registros descargados.
- 7.204 partidas finales.
- 99,85% de retención.
- 11 registros descartados: 1 duplicado (dos cuentas configuradas jugaron entre sí y
  ambas reportan la partida) + 10 partidas con menos de 5 medio-movimientos (abandonos
  o resultados administrativos inmediatos, no partidas jugadas).
- 0 nulos en el dataset final.

Los archivos de `data/` no se versionan: se regeneran ejecutando el pipeline. Con la
ventana temporal congelada, una corrida desde cero reproduce estos números.
