# Ajedrez online: ELO, apertura y ritmo como predictores del resultado

Proyecto Integrador — Ciencia de Datos (UTN FRM, 5to año, Ingeniería en Sistemas de
Información, 2026).

## Pregunta de investigación

¿Qué combinación de nivel de ELO, apertura jugada, modalidad de ritmo (bullet/blitz/
rapid) y color de piezas predice mejor quién gana una partida de ajedrez online, y qué
tan larga es esa partida?

Esta primera entrega cubre el pipeline de ingeniería de datos: descarga automatizada,
parseo de PGN, limpieza e ingeniería de features sobre partidas reales de ajedrez
online jugadas en Lichess.

## Contexto para quien retome esto (importante, leer antes de tocar código)

Este proyecto **reemplaza** dos iteraciones anteriores del mismo Proyecto Integrador
que quedaron descartadas — no son bugs ni trabajo a medio hacer, son decisiones
tomadas y documentadas:

1. Un primer intento sobre transporte público multimodal del AMBA (colectivo/tren/
   subte con datos SUBE) se abandonó porque la fuente no tenía ni timestamp ni línea
   de colectivo por etapa — no se podía calcular duración de viaje en colectivo, que
   era el objetivo original.
2. Un segundo proyecto, **demanda de subte + clima + feriados**, sí se completó y
   está terminado, commiteado y pusheado en la rama `colectivos` de este mismo repo —
   no se tocó nada de esa rama al armar esta.
3. Este proyecto (ajedrez) es un **replanteo completo** pedido explícitamente por el
   dueño del repo, buscando un tema más entretenido y con más gancho que las fuentes
   anteriores (todas correctas pero "áridas": transporte, clima, feriados). Se armó
   esta rama desde cero, desde el commit de infraestructura de skills (`f673dfe`),
   sin arrastrar código de las ramas anteriores.

**Estado real al momento de escribir esto**: el pipeline está completo y escrito
(`src/*.py`, `config/config.yaml`, notebook), y **validado línea por línea contra una
muestra real de 3 partidas** que el dueño del repo bajó a mano desde su navegador y
subió al chat (porque el entorno donde se escribió este código no podía llegar a la
API de Lichess por una restricción de red del sandbox, no de la fuente en sí). El
parser funciona perfecto contra esa muestra. **Lo que falta**: correr el pipeline
completo con volumen real (cientos/miles de partidas por usuario) desde una máquina
con acceso normal a internet, y confirmar que todo el pipeline —no solo el parser—
corre de punta a punta sin ajustes. Si estás leyendo esto, probablemente sos vos quien
tiene que hacer esa corrida real. Instrucciones abajo, en "Cómo correr el pipeline".

## Por qué esta fuente cumple los 7 criterios de la cátedra

| # | Criterio | Cómo lo cumple este proyecto |
|---|----------|-------------------------------|
| 1 | Datos tidy | Cada fila es una partida de ajedrez individual; cada columna, una variable de esa partida (jugadores, ELO, apertura, resultado). |
| 2 | Unidad alineada con la pregunta | La unidad de análisis es la partida — exactamente aquello sobre lo que se quiere concluir (quién gana, cuánto dura). |
| 3 | Algo modelable | Target de clasificación (`resultado`: gana blancas/negras/empate, y también `es_sorpresa`) y de regresión (`cantidad_jugadas`). |
| 4 | Descargable de forma automatizada | API pública de Lichess, sin autenticación ni API key, un endpoint fijo por usuario (`GET /api/games/user/{username}`). Ver `src/download_data.py`. |
| 5 | Volumen suficiente | Hasta 1.000 partidas por usuario configurado (`config.yaml`), con 8 usuarios en distintos rangos de ELO — apunta a varios miles de partidas totales. |
| 6 | Columnas informativas | ELO de ambos jugadores, diferencia de rating, apertura (ECO + nombre), control de tiempo, terminación, resultado — numéricas, categóricas y de fecha. |
| 7 | Documentación entendible | [Documentación oficial de la API de Lichess](https://lichess.org/api) (OpenAPI spec pública en GitHub: `lichess-org/api`) + diccionario de datos de esta entrega, más abajo. |

## Fuente de datos

**API pública de [Lichess](https://lichess.org)** — el mayor servidor de ajedrez
online gratuito y de código abierto. Endpoint usado: `GET /api/games/user/{username}`,
que devuelve el historial de partidas de un usuario en formato PGN (texto plano),
ordenadas de más reciente a más antigua. No requiere autenticación para uso anónimo
(rate limit: 20 partidas/segundo). Especificación oficial:
[`lichess-org/api`](https://github.com/lichess-org/api), archivo
`doc/specs/tags/games/api-games-user-username.yaml`.

**Jugadores configurados** (`config/config.yaml -> lichess.usernames`), elegidos para
tener variación real de ELO — desde nivel club hasta top mundial:

- `thibault` — fundador de Lichess, nivel club (~1700-1800 blitz).
- `DrNykterstein` — Magnus Carlsen (campeón del mundo), top mundial (~3200+ blitz).
- `Zhigalko_Sergei`, `Konevlad` — Grandes Maestros, nivel top.
- `penguingim1` — streamer/jugador fuerte.
- `RebeccaHarris`, `Bombegranate`, `Msb2` — nivel club/intermedio.

Se puede editar esta lista libremente; solo hace falta que el username exista en
Lichess (se puede confirmar entrando a `https://lichess.org/@/<username>`).

**Nota sobre el formato real de los datos, verificada con datos reales** (no
documentación abreviada): cada partida en el PGN es un bloque de encabezados
`[Clave "Valor"]` seguido de una línea en blanco y las jugadas en notación algebraica,
terminado en el resultado (`1-0`, `0-1`, `1/2-1/2`) y separado de la siguiente partida
por una línea en blanco. `src/clean_data.py` parsea esto con una regex simple — no se
usa `python-chess` porque este proyecto no analiza la calidad de las jugadas, solo
metadata de la partida (quién ganó, con qué ELO, en cuántas jugadas).

## Estructura de carpetas

```
CienciaDeDatos/
├── config/
│   └── config.yaml               # usuarios de Lichess, bandas de ELO, parámetros de descarga
├── data/
│   ├── raw/                      # PGN crudos descargados (vacío en git)
│   └── processed/                 # dataset final + sample + resumen (vacío en git)
├── notebooks/
│   └── 01_data_ingestion_verification.ipynb   # pipeline narrado + verificación
├── src/
│   ├── utils.py                  # logging, config
│   ├── download_data.py          # DataDownloader — descarga PGN desde la API de Lichess
│   ├── clean_data.py             # DataCleaner — parseo de PGN, limpieza, validación
│   ├── feature_engineering.py    # FeatureEngineer — ELO, apertura, modalidad, sorpresas
│   └── pipeline.py               # CLI que orquesta todo el pipeline
├── skills/                        # convenciones del repo para agentes de código (ver abajo)
├── AGENTS.md                      # punto de entrada para Codex y OpenCode
├── CLAUDE.md                      # punto de entrada para Claude Code
├── requirements.txt
└── README.md
```

Las convenciones del repo (ramas y commits, cómo se escriben los notebooks, qué pide
cada entrega, los 7 criterios de la cátedra) están en [`skills/`](skills/), en formato
Agent Skills, para que las lean tanto las personas como los agentes de código
(Claude Code, Codex, OpenCode). Ver [`skills/README.md`](skills/README.md). **Regla
base del repo: no se commitea a `main` ni se suben archivos de `data/`.**

## Diccionario de datos — dataset procesado

Columnas extraídas directamente del PGN:

| Columna | Tipo | Descripción |
|---|---|---|
| `Event` | category | Tipo de partida (`"rated blitz game"`, etc.). |
| `Date` | datetime64 | Fecha en que se jugó la partida. |
| `White`, `Black` | str | Username de cada jugador. |
| `Result` | str | Resultado crudo del PGN (`1-0`, `0-1`, `1/2-1/2`). |
| `WhiteElo`, `BlackElo` | int16 | Rating ELO de cada jugador al momento de la partida. |
| `WhiteRatingDiff`, `BlackRatingDiff` | int8 | Cuánto ELO ganó/perdió cada jugador tras la partida. |
| `Variant` | str | Variante de ajedrez (`"Standard"` — se filtran las demás). |
| `TimeControl` | str | Control de tiempo crudo (`"300+3"` = 300s base + 3s de incremento por jugada). |
| `ECO` | category | Código ECO de la apertura jugada (ej. `"B21"`). Nulo si la descarga no pidió `opening=true`. |
| `Opening` | category | Nombre de la apertura (ej. `"Sicilian Defense: McDonnell Attack"`). |
| `Termination` | category | Cómo terminó la partida (`"Normal"`, `"Time forfeit"`, etc.). |
| `moves_text` | str | Jugadas en notación algebraica, sin anotaciones de reloj. |

Features generadas por `src/feature_engineering.py`:

| Feature | Tipo | Descripción |
|---|---|---|
| `resultado` | category | `"Gana Blancas"`, `"Gana Negras"` o `"Empate"`. **Target de clasificación principal.** |
| `cantidad_jugadas` | int | Cantidad total de medio-movimientos (plies) de la partida. **Target de regresión.** |
| `tiempo_base_seg`, `incremento_seg` | int | Control de tiempo parseado por separado. |
| `diferencia_elo` | int | `WhiteElo - BlackElo`. |
| `elo_promedio` | float | Promedio de ELO de ambos jugadores. |
| `favorito` | str | `"Blancas"`, `"Negras"` o `"Ninguno"`, según quién tenía más ELO. |
| `nivel_promedio` | category | Banda de ELO de la partida (`principiante` a `top_mundial`, ver `config.yaml -> elo.bandas`). |
| `modalidad` | category | `"Bullet"`, `"Blitz"`, `"Rapid"` o `"Clásica"`, según tiempo estimado de partida. |
| `es_sorpresa` | int8 (0/1) | 1 si ganó el jugador con **menor** ELO. **Target de clasificación adicional (binario).** |
| `familia_apertura` | category | Agrupación de la apertura por letra ECO (`Flanco`, `Semiabierta`, `Abierta`, `Cerrada`, `India`). |

## Cómo correr el pipeline

### Requisitos

- Python 3.11+ (probado también con 3.14)
- Instalar dependencias:

```bash
pip install -r requirements.txt
```

### Opción A — Notebook (entregable principal)

```bash
jupyter lab notebooks/01_data_ingestion_verification.ipynb
```

Ejecutar con **Restart & Run All**. El notebook importa las clases de `src/` y corre
el pipeline completo con narrativa explicando cada decisión, más una sección final de
verificación de integridad.

### Opción B — Script CLI

```bash
python -m src.pipeline
# o, si los PGN crudos ya están descargados en data/raw/:
python -m src.pipeline --skip-download
```

La primera corrida descarga las partidas de los 8 usuarios configurados desde la API
de Lichess (liviano, unos MB en total). Al terminar quedan en `data/processed/`:

- `partidas_ajedrez_clean.parquet` — dataset final, comprimido con `snappy`.
- `partidas_ajedrez_clean_sample.csv` — muestra de validación rápida.
- `data_summary.json` — partidas raw/procesadas, distribución de los targets y nulos
  por columna.

### Si te encontrás con que la descarga falla (404 consistente)

Esto le pasó al entorno donde se escribió el pipeline (ver "Contexto" más arriba) — el
código en sí está bien, el endpoint es real y funciona en un navegador normal. Si te
pasa lo mismo desde tu máquina, probá primero entrando manualmente a una URL como:

```
https://lichess.org/api/games/user/thibault?max=50&opening=true&rated=true&perfType=blitz
```

Si eso te descarga un PGN con partidas reales en el navegador pero `requests` sigue
fallando, revisá firewall/proxy/VPN local antes de asumir que el pipeline está roto.

No se requiere ningún estado previo: tanto el notebook como el script corren de punta
a punta desde cero.
