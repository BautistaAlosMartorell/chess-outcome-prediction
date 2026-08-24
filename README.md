# Ajedrez online: ELO, apertura y ritmo como predictores del resultado

Proyecto Integrador — Ciencia de Datos (UTN FRM, 5.º año, Ingeniería en Sistemas de
Información, 2026).

## Pregunta de investigación

¿Qué combinación de nivel de ELO, apertura jugada, modalidad de ritmo
(bullet/blitz/rapid) y color de piezas predice mejor quién gana una partida de ajedrez
online, y qué tan larga es esa partida?

La unidad de análisis es una partida individual. Esta primera entrega implementa el
pipeline automatizado de ingeniería de datos: descarga, parseo, limpieza, validación,
ingeniería de features y exportación del dataset de trabajo.

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

### Limitación del rating

Chess.com entrega en cada objeto el rating asociado al jugador al finalizar la partida.
Se utiliza como una aproximación muy cercana a su fuerza en ese encuentro, pero no es un
rating estrictamente congelado antes de jugar. Esta limitación debe considerarse al
formular el modelado predictivo de la Entrega 3 para evitar interpretar como totalmente
prospectiva una señal que incorpora el ajuste inmediato del resultado.

## Por qué la fuente cumple los siete criterios

| # | Criterio | Aplicación |
|---|---|---|
| 1 | Datos tidy | El dataset final tiene una fila por partida y una columna por variable. |
| 2 | Unidad alineada | La partida es exactamente la unidad sobre la que pregunta el proyecto. |
| 3 | Algo modelable | `resultado` es el target de clasificación y `cantidad_jugadas`, el de regresión. |
| 4 | Descarga automatizada | La PubAPI se consulta sin intervención manual ni credenciales. |
| 5 | Volumen | La corrida validada produjo 7.208 partidas limpias. |
| 6 | Columnas informativas | Hay ratings, color, apertura, ritmo, tiempo, resultado, fecha y terminación. |
| 7 | Documentación | Chess.com publica endpoints, campos, códigos de respuesta y reglas de uso. |

## Estructura

```text
config/config.yaml                         parámetros y cuentas de Chess.com
data/raw/                                 JSON regenerables, ignorados por Git
data/processed/                           Parquet, sample y resumen, ignorados por Git
notebooks/01_data_ingestion_verification.ipynb
src/download_data.py                      descarga secuencial e idempotente
src/clean_data.py                         parseo de JSON + PGN y limpieza
src/feature_engineering.py                features analíticas
src/pipeline.py                           orquestador CLI
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
| `Termination` | category | Motivo textual de finalización. |
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
| `favorito` | str | Color con mayor rating o `Ninguno`. |
| `nivel_promedio` | category | Banda de rating configurada. |
| `modalidad` | category | Bullet, Blitz o Rapid según `TimeClass`. |
| `es_sorpresa` | int8 | 1 cuando gana el jugador con menor rating. |
| `familia_apertura` | category | Familia ECO: flanco, semiabierta, abierta, cerrada o india. |

## Cómo ejecutar

Requiere Python 3.11 o superior.

### Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.pipeline
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.pipeline
```

Si los JSON crudos ya existen:

```bash
python -m src.pipeline --skip-download
```

También puede abrirse `notebooks/01_data_ingestion_verification.ipynb` y ejecutarse con
**Restart & Run All**.

## Artefactos generados

- `data/processed/partidas_ajedrez_clean.parquet`
- `data/processed/partidas_ajedrez_clean_sample.csv`
- `data/processed/data_summary.json`

Corrida real validada el 24/08/2026:

- 7.215 registros descargados.
- 7.208 partidas finales.
- 99,9% de retención.
- 1 duplicado eliminado porque dos cuentas configuradas participaron en la misma partida.
- 6 partidas rated sin movimientos descartadas (abortos o resultados administrativos).
- 0 nulos en el dataset final.

Los archivos de `data/` no se versionan: se regeneran ejecutando el pipeline.
