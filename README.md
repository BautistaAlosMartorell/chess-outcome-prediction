# Ajedrez online: predicción del resultado antes y durante la partida

Proyecto Integrador — Ciencia de Datos (UTN FRM, 5.º año, Ingeniería en Sistemas de
Información, 2026).

## Pregunta de investigación

¿Qué tan bien se puede predecir quién gana una partida de ajedrez online, y cuánto le
falta para terminar, **antes de que empiece y a medida que avanza**? Antes de empezar se
conocen el nivel de los jugadores, el ritmo (bullet/blitz/rapid) y el color; durante la
partida se suman la apertura, la posición en el tablero y los relojes.

**Unidad de análisis: la partida en un momento dado** (partida × corte de plies). Hay dos
tablas, una derivada de la otra:

- `partidas_ajedrez_clean.parquet`: **una fila por partida** (tidy). Es la capa base de
  la Entrega 1: describe la partida completa.
- `partidas_cortes.parquet`: **una fila por (partida, corte)**, con la posición y los
  relojes cada 5 plies, del 0 (antes de mover) al 120. Es la tabla de modelado. El corte
  0 es la predicción pre-partida; los demás, la predicción en vivo.

El proyecto incluye el pipeline automatizado de ingeniería de datos —descarga, parseo,
limpieza, validación, ingeniería de características, exportación y tabla de cortes—, el
análisis exploratorio que contrasta hipótesis antes y durante la partida, y el modelado.

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

### Selección automática de jugadores

La primera tarea del DAG (`listar_jugadores`) arma la lista de jugadores a descargar
**una sola vez** y la deja congelada en `config/jugadores_seleccionados.yaml`, que **se
versiona en git**:

1. **Primera corrida:** si no existe `config/jugadores_seleccionados.yaml`,
   arma cuatro pools de candidatos con listas públicas de la PubAPI. Cada pool alimenta
   ciertas bandas:
   - FM, CM y NM (`/pub/titled/{título}`) para `avanzado`;
   - GM e IM para `experto` y `top_mundial`;
   - jugadores de AR, ES, MX, US, IN, BR, DE y RU (`/pub/country/{iso}/players`) para
     `principiante` e `intermedio`;
   - rankings `live_bullet`, `live_blitz` y `live_rapid` de `/pub/leaderboards` para `elite` [3000, 4000). `top_mundial` queda en [2600, 3000).

   Baraja cada pool con semilla fija (`random_state: 42`) y los recorre en ronda. Estima la
   banda de cada candidato con `/pub/player/{u}/stats` y lo valida contra sus partidas
   hasta el cutoff (perfil activo, al menos 15 partidas rated elegibles, mediana de ELO
   dentro de la banda). La banda final la decide la mediana validada, no la estimación, así
   que un jugador validado en otra banda abierta entra ahí igual. Cuando todas las bandas de
   un pool se llenan, ese pool deja de consultarse. Se usan solo títulos abiertos: llenar
   una banda con listas exclusivas de un género (WFM, WCM) habría sesgado la muestra. Se detiene al juntar 20 jugadores en cada una de las 6 bandas. El avance se
   guarda en un checkpoint, así que si la tarea se corta, retoma desde ahí.
2. **Corridas siguientes:** si se agregó una banda, completa sólo esa y registra la ampliación en `extensions`, conservando las cuentas congeladas. La lista vigente amplió las 100 originales a 120. Si no falta ninguna banda, lee ese archivo y devuelve exactamente la misma lista, sin
   volver a seleccionar. Como la descarga es idempotente, se reusa el bronce ya bajado y
   sale el mismo dataset.

No hay cuentas iniciales elegidas a mano ni dependencia del Parquet de una corrida
anterior. El archivo de selección también es el manifiesto auditable: incluye la política,
los candidatos evaluados y los motivos de rechazo. Los snapshots crudos de las listas por
país, por título y de rankings quedan en `data/raw/seleccion/` (regenerables, fuera de git). El documento del criterio de selección explica
los tres pools originales y el cuarto de élite, con las mediciones que los motivaron. Para
volver a seleccionar hay que borrarlo a propósito.

**Por qué la lista está en `config/` y no en `data/`.** Hasta el 22/10/2026 vivía en
`data/raw/seleccion/`, ignorada por git, y cada integrante terminó con su propia lista y
su propio dataset (llegaron a convivir cifras de 80.145 y de 76.803 partidas). La lista es
lo que define la muestra, como `until_month`: es configuración, no un dato regenerable.
El detalle está en [`docs/entregas/criterio-seleccion-jugadores.md`](docs/entregas/criterio-seleccion-jugadores.md);
la configuración, en `config/config.yaml` bajo `player_selection`.

### Limitación del rating (fuga de información hacia el resultado)

Chess.com entrega en cada objeto el rating del jugador **después** de que el resultado
ajustó su puntaje Glicko, no un snapshot previo a la partida. A diferencia de Lichess
(que expone el rating previo y el ajuste posterior por separado), esta API no da el
rating anterior a la partida.

En consecuencia, `WhiteElo`, `BlackElo` y todo lo derivado de ellos (`diferencia_elo`,
`elo_promedio`, `nivel_promedio`, `es_sorpresa`) contienen una fuga de información hacia
`resultado`: el signo del cambio de rating coincide con el resultado en el 99,9 % de las
partidas (notebook 02, sección 9). **No entran al modelo.**

**Cómo se resolvió.** El transformador `PlayerHistoryTransformer` de
`src/history_transformer.py`, dentro del Pipeline del notebook 04, reconstruye el **rating previo** de cada
cuenta seleccionada al cierre de su partida anterior del mismo ritmo, leído de su propio
historial, con cierre estrictamente anterior al inicio actual. El orden por cierre
con `shift()` solo no garantizaba esa condición; la sección 2 del 04 cuantifica y
corrige los solapamientos. Sólo se puede reconstruir el lado de la cuenta seleccionada (≈ 50 % de blancas y
50 % de negras, al menos un lado en el 99,7 % de las partidas): del rival normalmente no se descargó el
historial, así que ese lado llega como NaN al preprocesamiento. El bosque imputa
con estadísticas aprendidas sólo en su train y un indicador de faltante. Es la principal limitación de la
predicción antes de la partida.

### Limitación de la muestra

La muestra no es una selección aleatoria de la población general de Chess.com. Los
candidatos salen de las listas públicas por país (ocho países) y de titulados, y se
estratifican por banda de ELO con cupos iguales. `avanzado`, `experto` y `top_mundial` salen
de listas de titulados, porque en las listas por país casi no hay jugadores de 1800 o más y
la API no publica ninguna lista por rating. Eso deja afuera al amateur fuerte sin título,
que es el perfil típico de 1800–2200. Por eso la distribución de niveles refleja
el diseño (20 jugadores por banda) y no la de la población. Además, las listas por país
solo incluyen a quienes declararon ese país en su perfil. Las conclusiones de las
próximas entregas se formulan sobre el universo de jugadores alcanzados por este método,
no sobre "ajedrez online" en general.

## Por qué la fuente cumple los siete criterios

| # | Criterio | Aplicación |
|---|---|---|
| 1 | Datos tidy | La tabla base tiene una fila por partida; la de cortes, una fila por (partida, corte). Las dos con una columna por variable. |
| 2 | Unidad alineada | La pregunta es sobre la partida en un momento dado, y la tabla de cortes es exactamente eso. |
| 3 | Algo modelable | `resultado` en cada corte es el target de clasificación y `plies_restantes`, el de regresión. |
| 4 | Descarga automatizada | La PubAPI se consulta sin intervención manual ni credenciales. |
| 5 | Volumen | La corrida oficial produjo 100.396 partidas y 1.559.622 filas de cortes. |
| 6 | Columnas informativas | Hay rating previo, color, apertura, ritmo, relojes, material y posición en cada corte, resultado y fecha. |
| 7 | Documentación | Chess.com publica endpoints, campos, códigos de respuesta y reglas de uso. |

## Estructura

```text
config/config.yaml                         parámetros del pipeline y política de selección de jugadores
config/jugadores_seleccionados.yaml        lista congelada de jugadores + manifiesto de la selección (versionada)
data/raw/                                  JSON regenerables, ignorados por Git
data/raw/seleccion/                        snapshots de las listas públicas usadas en la selección
data/processed/                            Parquet, sample y resumen, ignorados por Git
dags/pipeline_ajedrez_dag.py               DAG de Airflow: listar_jugadores (selección automática) → descarga (mapeada por cuenta) → limpieza → ingeniería de características → verificación → exportación → dataset de cortes
docker-compose.yml                         stack de Airflow 3.3 (postgres, redis, api-server, scheduler, dag-processor, triggerer, worker)
Dockerfile                                 imagen de Airflow con las dependencias del proyecto
.env.example                               plantilla de variables de entorno para la stack
notebooks/01_data_ingestion_verification.ipynb     Entrega 1: pipeline narrado y verificación
notebooks/02_eda_hipotesis.ipynb                   Entrega 2: perfil y fugas, cuatro hipótesis antes de la partida (Parte A) y cuatro durante, sobre la tabla de cortes (Parte B), + anexo de matchmaking
notebooks/03_prediccion_en_vivo.ipynb              Entrega 3 (exploración): curva por corte, desbalance de Empate y matchup de apertura
notebooks/04_modelado.ipynb                        Entrega 3: modelado formal (piso, tres familias con CV temporal por partida, grilla, ablación, test una vez) y modelo guardado para la app
src/download_data.py                       descarga idempotente por cuenta (el DAG la paraleliza con .expand())
src/clean_data.py                          parseo de JSON + PGN y limpieza
src/feature_engineering.py                 características analíticas derivadas (incluye el historial del matchup de apertura)
src/live_features.py                       dataset de predicción en vivo: una fila por partida y corte de plies (python-chess)
src/rating_history.py                      lectura de historiales y helpers del EDA
src/history_transformer.py                 rating previo, forma y estilo dentro del Pipeline, con cierre estrictamente anterior al inicio
src/model_validation.py                    validación cruzada temporal por partida (las filas de una partida no se separan)
src/predict.py                             columnas del modelo y predecir(): probabilidades jugada a jugada para la app
src/player_selection.py                    selección de jugadores por banda de ELO, congelada tras la primera corrida
src/pipeline.py                            orquestador CLI
tests/test_chess_pipeline.py               pruebas unitarias sin acceso de red
tests/test_player_selection.py             pruebas del selector de jugadores
tests/test_live_features.py                pruebas del dataset en vivo (incluida la de no mirar jugadas futuras), del rating previo y de la forma reciente
tests/test_modeling.py                     pruebas del splitter temporal por partida y de predecir()
tests/test_history_transformer.py           ventanas, temporalidad y serialización del historial del Pipeline
tests/test_model_realism.py                 comportamiento y calibración del artefacto final (si existe localmente)
models/                                    modelo entrenado (lo regenera el notebook 04), ignorado por Git
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
| `TournamentUrl` | str | URL del torneo de Chess.com; nula si la partida no es de torneo (nulo estructural, documentado). |
| `StartTime`, `EndTime` | datetime64 UTC | Inicio (headers `UTCDate` + `UTCTime`) y fin (`end_time` del JSON). Orden causal entre partidas del mismo día. |

### Features generadas

| Feature | Tipo | Descripción |
|---|---|---|
| `resultado` | category | Gana blancas, gana negras o empate. Target de clasificación. |
| `cantidad_jugadas` | int | Cantidad de medio-movimientos o plies. Target de regresión. |
| `tiempo_base_seg`, `incremento_seg` | int | Componentes del control de tiempo. |
| `diferencia_elo` | int | `WhiteElo - BlackElo`. |
| `elo_promedio` | float | Rating promedio de ambos jugadores. |
| `nivel_promedio` | category | Banda de rating configurada. |
| `es_sorpresa` | int8 | 1 cuando gana el jugador con menor rating. |
| `familia_apertura` | category | Familia ECO: flanco, semiabierta, abierta, cerrada, india o desconocida. |
| `EsTorneo` | bool | `True` si la partida se jugó en un torneo (`TournamentUrl` presente). |
| `matchup_apertura` | category | Primera jugada de blancas × respuesta de negras (`e4-e5`, `d4-Nf6`…): 17 combinaciones congeladas en `config.yaml` + `otra`. Taxonomía propia, no ECO. |
| `n_previas_matchup`, `historial_suficiente` | Int32 / bool | Partidas del mismo matchup y ritmo terminadas antes de que empiece esta, y si llegan al mínimo (30). |
| `tasa_blancas_hist`, `tasa_tablas_hist`, `tasa_negras_hist` | float | Tasas históricas de resultado de esas partidas previas; NaN si el historial es insuficiente (no se imputa). |

### Tabla de cortes (`partidas_cortes.parquet`)

Una fila por `(GameUrl, corte_ply)`. Cada partida se reproduce jugada a jugada con
python-chess desde el PGN crudo (el único lugar con los relojes `%clk`), y en cada corte se
guarda sólo lo que se veía en ese momento. Una partida aporta los cortes anteriores a su
final. El contexto fijo (ritmo, torneo, matchup, rating previo) se une desde la tabla base
por `GameUrl`.

| Columna | Descripción |
|---|---|
| `corte_ply` | Plies jugados en el corte: 0, 5, 10, …, 120 (uno cada 5). El EDA y el notebook 03 usan los de referencia: 0, 10, 20, 30, 40 y 60. |
| `resultado`, `plies_restantes` | Targets: resultado final y plies que faltan desde el corte. |
| `material_*`, `balance_material`, `material_no_peon_frac` | Material de cada bando (peón 1, caballo/alfil 3, torre 5, dama 9), su diferencia y la fracción de material sin peones que queda. |
| `jaques_*`, `capturas_*`, `promociones` | Acumulados hasta el corte. |
| `enroco_*`, `derechos_enroque_*`, `en_jaque`, `movilidad`, `turno_blancas` | Estado de la posición en el corte (`movilidad`: jugadas legales del bando que mueve). |
| `material_colgado_*`, `ataques_al_rey_*`, `peones_pasados_*`, `movilidad_*` | Calidad de la posición de cada bando: puntos de piezas atacadas y sin defensor, ataques rivales sobre la casilla del rey y sus vecinas, peones pasados y jugadas posibles (le toque mover o no). |
| `reloj_*_seg`, `reloj_frac_*`, `diferencia_reloj_seg` | Reloj restante de cada bando, en segundos y como fracción del tiempo base. |
| `gasto_reciente_*_seg` | Segundos gastados en las últimas 5 jugadas propias. NaN en el corte 0 (todavía no hubo jugadas). |

## Cómo ejecutar

### Con Airflow (Docker) — es la forma en que se evalúa la entrega

Requiere Docker con el plugin `compose`. El stack corre sobre **Apache Airflow 3.3**
(la versión que dicta la cátedra). Un compañero que clona el repo no toca nada más que
copiar el `.env` (y, en Linux, dar un permiso; ver abajo):

```bash
git clone <repo> && cd <repo>
cp .env.example .env                 # la primera vez; .env está en .gitignore
docker compose up airflow-init       # migra la BD de metadatos (esquema 3.x) y crea el admin
docker compose up -d                 # levanta postgres, redis, api-server, scheduler, dag-processor, triggerer y worker
```

**En Linux**, los contenedores corren con el usuario `50000`, que necesita escribir en
`config/` si alguna vez hay que volver a seleccionar jugadores:
`setfacl -m u:50000:rwx config`. En Mac y Windows (Docker Desktop) no hace falta.

Después:

1. Abrir <http://localhost:8080> y entrar con `admin` / `admin`.
2. Buscar el DAG `pipeline_ajedrez_chesscom`, activarlo con el toggle (viene pausado) y
   dispararlo con ▶ (*Trigger DAG*).
3. La corrida lista usuarios, descarga en paralelo por cuenta y luego recorre la cadena
   `consolidar_descarga` → `limpieza_y_parseo` →
   `ingenieria_de_caracteristicas` → `verificar_calidad` → `exportar_dataset` →
   `construir_dataset_cortes` (tabla derivada para predicción en vivo, ~5 min).
   La verificación hace `assert` de los siete criterios de calidad, así que una corrida
   en verde implica un dataset válido.

Los artefactos quedan en `data/` del host (el `docker-compose.yml` monta `./data`):

```text
data/raw/chesscom_<usuario>_raw.json          capa cruda, un archivo por cuenta
data/processed/partidas_ajedrez_clean.parquet dataset final
data/processed/partidas_ajedrez_clean_sample.csv
data/processed/data_summary.json
data/processed/partidas_cortes.parquet        tabla derivada para predicción en vivo (partida × corte)
```

Volver a disparar el DAG sin borrar `data/raw/` reutiliza los JSON ya descargados
(descarga idempotente). Para apagar la stack: `docker compose down` (conserva los
volúmenes) o `docker compose down -v` (reset total).

### Sin Docker (CLI / notebook)

El CLI reutiliza los mismos módulos de `src/` y la misma lista congelada que el DAG (si
no existe, la crea igual que `listar_jugadores`). Requiere Python 3.11 o superior.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # Windows: py -m venv .venv; .venv\Scripts\python.exe ...
.venv/bin/python -m src.pipeline                          # --skip-download si los JSON crudos ya existen; --sin-cortes para saltear el dataset en vivo
```

También puede abrirse `notebooks/01_data_ingestion_verification.ipynb`, que ejecuta el
pipeline completo con la misma lista congelada que el DAG y verifica el dataset. Los
notebooks 02, 03 y 04 consumen lo que produce el DAG (las dos tablas de
`data/processed/` y los JSON crudos). Todos deben ejecutarse con **Restart & Run All**,
en ese orden. El 04 requiere decenas de minutos (ver el tiempo medido en su última celda) y deja el modelo para la app en `models/`.

### Tests

```bash
python -m unittest discover -s tests
```

No usan red. Las pruebas de realismo requieren `models/modelo_en_vivo.joblib`;
las de población/calibración necesitan además los Parquet y JSON locales. Si faltan,
unittest las marca como omitidas. Verifican probabilidades iniciales plausibles,
una dama ganada, desventaja de reloj, el ganador cerca del final y calibración por clase.

## Artefactos generados

- `data/processed/partidas_ajedrez_clean.parquet`
- `data/processed/partidas_ajedrez_clean_sample.csv`
- `data/processed/data_summary.json`
- `data/processed/partidas_cortes.parquet`
- `models/modelo_en_vivo.joblib` (lo genera `notebooks/04_modelado.ipynb`; se carga con
  `src.predict.cargar_modelo()` y se usa con `predecir()`)

Corrida oficial del 22/10/2026 (DAG completo en Airflow, ventana congelada hasta agosto
de 2026, DAG `manual__2026-10-22T18:56:28`, 120 jugadores seleccionados —20 por banda de ELO—):

- 101.094 registros descargados.
- 100.396 partidas finales (99,31 % de retención; 698 descartadas por las reglas de
  deduplicación, alcance y calidad del pipeline).
- 35 columnas. Los únicos nulos son estructurales y están documentados: `TournamentUrl`
  (partidas que no son de torneo) y las tres `tasa_*_hist` (1.620 partidas sin historial
  suficiente del matchup).
- Las seis bandas de ELO quedan entre 14,8 % y 19,8 % del dataset.
- Tabla de cortes: 1.559.622 filas, un corte cada 5 plies del 0 al 120 (corte 0: 100.396 ·
  60: 66.413 · 120: 12.323). Filtrada a los cortes de referencia que usan el EDA y el
  notebook 03 son 547.555 filas (corte 0: 100.396 · 10: 99.762 · 20: 98.026 · 30: 94.671 ·
  40: 88.287 · 60: 66.413).

Los archivos de `data/` no se versionan: la corrida oficial se regenera ejecutando el DAG
de Airflow. Con la lista de jugadores versionada en `config/` y la ventana temporal
congelada, volver a correrlo en cualquier máquina reproduce ese mismo dataset.

### Casos límite observados en la corrida oficial

Casos encontrados inspeccionando el Parquet final directamente —no sólo el resumen— y
documentados para que no se confundan con errores del pipeline durante el EDA:

- **93 partidas con `Date` = 2026-09-01** (0,093 % del dataset), un día después del tope
  `download.until_month: "2026-08"`. No es un bug del filtro: la ventana congelada decide
  qué archivo mensual bajar por su URL (`.../games/2026/08`), no por la fecha individual.
  El patrón aparece en varias cuentas y confirma un límite horario del archivo mensual de
  Chess.com. La ventana es exacta a nivel de archivo descargado, no a nivel de fecha PGN.
- **Controles de tiempo fuera de los estándar**, como `tiempo_base_seg` = 240 o 660. No son
  errores de parseo: Chess.com permite controles personalizados y esas filas corresponden a
  partidas reales con ese ritmo puntual.

Además, las cuentas seleccionadas aparecen hasta en 1.204 filas del dataset final, por encima de
`max_games_per_user` (1000). No es un error: el tope se aplica a la descarga *de esa
cuenta*, pero una partida también puede entrar a través de la descarga de su oponente si
ambos fueron seleccionados. La deduplicación por `GameUrl` evita contarla dos veces, aunque
permite que un username supere su propio tope en apariciones totales.
