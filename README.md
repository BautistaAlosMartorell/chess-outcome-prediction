# Ajedrez online: ELO, apertura y ritmo como predictores del resultado

Proyecto Integrador — Ciencia de Datos (UTN FRM, 5.º año, Ingeniería en Sistemas de
Información, 2026).

## Pregunta de investigación

¿Qué combinación de nivel de ELO, apertura jugada, modalidad de ritmo
(bullet/blitz/rapid) y color de piezas predice mejor quién gana una partida de ajedrez
online, y qué tan larga es esa partida?

La unidad de análisis es una partida individual. El proyecto incluye el pipeline
automatizado de ingeniería de datos —descarga, parseo, limpieza, validación, ingeniería
de características y exportación— y el análisis exploratorio que contrasta hipótesis y
define las variables candidatas para modelado.

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
**una sola vez** y la deja congelada:

1. **Primera corrida:** si no existe `data/raw/seleccion/jugadores_seleccionados.yaml`,
   arma tres pools de candidatos con listas públicas de la PubAPI. Cada pool alimenta
   ciertas bandas:
   - FM, CM y NM (`/pub/titled/{título}`) para `avanzado`;
   - GM e IM para `experto` y `top_mundial`;
   - jugadores de AR, ES, MX, US, IN, BR, DE y RU (`/pub/country/{iso}/players`) para
     `principiante` e `intermedio`.

   Baraja cada pool con semilla fija (`random_state: 42`) y los recorre en ronda. Estima la
   banda de cada candidato con `/pub/player/{u}/stats` y lo valida contra sus partidas
   hasta el cutoff (perfil activo, al menos 15 partidas rated elegibles, mediana de ELO
   dentro de la banda). La banda final la decide la mediana validada, no la estimación, así
   que un jugador validado en otra banda abierta entra ahí igual. Cuando todas las bandas de
   un pool se llenan, ese pool deja de consultarse. Se usan solo títulos abiertos: llenar
   una banda con listas exclusivas de un género (WFM, WCM) habría sesgado la muestra. Se detiene al juntar 20 jugadores en cada una de las 5 bandas. El avance se
   guarda en un checkpoint, así que si la tarea se corta, retoma desde ahí.
2. **Corridas siguientes:** lee ese archivo y devuelve exactamente la misma lista, sin
   volver a seleccionar. Como la descarga es idempotente, se reusa el bronce ya bajado y
   sale el mismo dataset.

No hay cuentas iniciales elegidas a mano ni dependencia del Parquet de una corrida
anterior. El archivo de selección también es el manifiesto auditable: incluye la política,
los candidatos evaluados y los motivos de rechazo. Junto a él quedan los snapshots crudos
de las listas por país y por título. Por qué hay tres pools y qué se midió para definirlos
está en el doc del criterio de selección. Para volver a seleccionar hay que borrarlo a propósito.
El detalle está en [`docs/entregas/criterio-seleccion-jugadores.md`](docs/entregas/criterio-seleccion-jugadores.md);
la configuración, en `config/config.yaml` bajo `player_selection`.

### Limitación del rating (fuga de información hacia el resultado)

Chess.com entrega en cada objeto el rating del jugador **después** de que el resultado
ajustó su puntaje Glicko, no un snapshot previo a la partida. A diferencia de Lichess
(que expone el rating previo y el ajuste posterior por separado), esta API no permite
aislar el rating estrictamente anterior sin reconstruir el historial cronológico
completo de cada jugador.

En consecuencia, `WhiteElo`, `BlackElo` y todo lo derivado de ellos (`diferencia_elo`,
`elo_promedio`, `nivel_promedio`, `es_sorpresa`) contienen una fuga de
información hacia `resultado`, de magnitud pequeña pero sistemática, concentrada
justamente en las partidas de rating parejo. Se documenta como limitación conocida de
la fuente para el modelado de Entrega 3, no se corrige con un parche improvisado.

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
| 1 | Datos tidy | El dataset final tiene una fila por partida y una columna por variable. |
| 2 | Unidad alineada | La partida es exactamente la unidad sobre la que pregunta el proyecto. |
| 3 | Algo modelable | `resultado` es el target de clasificación y `cantidad_jugadas`, el de regresión. |
| 4 | Descarga automatizada | La PubAPI se consulta sin intervención manual ni credenciales. |
| 5 | Volumen | La corrida validada produjo 80.145 partidas limpias. |
| 6 | Columnas informativas | Hay ratings, color, apertura, ritmo, tiempo, resultado, fecha y terminación. |
| 7 | Documentación | Chess.com publica endpoints, campos, códigos de respuesta y reglas de uso. |

## Estructura

```text
config/config.yaml                         parámetros y cuentas de Chess.com
data/raw/                                  JSON regenerables, ignorados por Git
data/processed/                            Parquet, sample y resumen, ignorados por Git
dags/pipeline_ajedrez_dag.py               DAG de Airflow: listar_jugadores (selección automática) → descarga (mapeada por cuenta) → limpieza → ingeniería de características → verificación → exportación
docker-compose.yml                         stack de Airflow 3.3 (postgres, redis, api-server, scheduler, dag-processor, triggerer, worker)
Dockerfile                                 imagen de Airflow con las dependencias del proyecto
.env.example                               plantilla de variables de entorno para la stack
notebooks/01_data_ingestion_verification.ipynb
notebooks/02_eda_hipotesis.ipynb              EDA, cuatro hipótesis y selección de variables
src/download_data.py                       descarga idempotente por cuenta (el DAG la paraleliza con .expand())
src/clean_data.py                          parseo de JSON + PGN y limpieza
src/feature_engineering.py                 características analíticas derivadas
src/player_selection.py                    selección automática y reproducible de jugadores por banda de ELO
src/pipeline.py                            orquestador CLI
tests/test_chess_pipeline.py               pruebas unitarias sin acceso de red
tests/test_player_selection.py             pruebas del selector de jugadores
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
| `nivel_promedio` | category | Banda de rating configurada. |
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

El CLI reutiliza los mismos módulos de `src/` y la misma lista congelada que el DAG (si
no existe, la crea igual que `listar_jugadores`). Requiere Python 3.11 o superior.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # Windows: py -m venv .venv; .venv\Scripts\python.exe ...
.venv/bin/python -m src.pipeline                          # --skip-download si los JSON crudos ya existen
```

También puede abrirse `notebooks/01_data_ingestion_verification.ipynb`, que ejecuta el
pipeline completo con la misma lista congelada que el DAG y verifica el dataset. El
análisis exploratorio de `notebooks/02_eda_hipotesis.ipynb` consume el Parquet que produce
ese pipeline (80.145 partidas finales). Ambos notebooks deben ejecutarse con
**Restart & Run All**.

### Tests

```bash
python -m unittest discover -s tests
```

## Artefactos generados

- `data/processed/partidas_ajedrez_clean.parquet`
- `data/processed/partidas_ajedrez_clean_sample.csv`
- `data/processed/data_summary.json`

Corrida validada el 22/09/2026 (DAG completo en Airflow, ventana congelada hasta agosto
de 2026, 100 jugadores seleccionados —20 por banda de ELO—):

- 80.521 registros descargados.
- 80.145 partidas finales.
- 99,53% de retención.
- 376 registros descartados por las reglas de deduplicación, alcance y calidad del
  pipeline.
- 0 nulos en el dataset final.
- Las cinco bandas de ELO quedan entre 18,2 % y 21,8 % del dataset.

Los archivos de `data/` no se versionan: la corrida oficial se regenera ejecutando el DAG
de Airflow. Con la lista de jugadores congelada y la ventana temporal congelada, volver a
correrlo reproduce ese mismo dataset. La carpeta `data/raw/seleccion/` es la que fija la
muestra: copiarla a otra máquina reproduce la selección exacta.

### Casos límite observados en la corrida validada

Casos encontrados inspeccionando el Parquet final directamente —no sólo el resumen— y
documentados para que no se confundan con errores del pipeline durante el EDA:

- **56 partidas con `Date` = 2026-09-01** (0,07% del dataset), un día después del tope
  `download.until_month: "2026-08"`. No es un bug del filtro: la ventana congelada decide
  qué archivo mensual bajar por su URL (`.../games/2026/08`), no por la fecha individual.
  El patrón aparece en varias cuentas y confirma un límite horario del archivo mensual de
  Chess.com. La ventana es exacta a nivel de archivo descargado, no a nivel de fecha PGN.
- **Controles de tiempo fuera de los estándar**, como `tiempo_base_seg` = 240 o 660. No son
  errores de parseo: Chess.com permite controles personalizados y esas filas corresponden a
  partidas reales con ese ritmo puntual.

Además, tres usernames seleccionados aparecen en 1.001 filas del dataset final, una más que
`max_games_per_user` (1000). No es un error: el tope se aplica a la descarga *de esa
cuenta*, pero una partida también puede entrar a través de la descarga de su oponente si
ambos fueron seleccionados. La deduplicación por `GameUrl` evita contarla dos veces, aunque
permite que un username supere su propio tope en apariciones totales.
