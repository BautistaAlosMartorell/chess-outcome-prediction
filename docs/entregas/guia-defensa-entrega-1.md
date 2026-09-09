# Guía de defensa — Entrega 1 (Ajedrez online, Chess.com)

> **La pregunta de fondo de esta entrega es una sola:**
> ¿tenés un pipeline que produce tu dataset sin que nadie lo toque a mano?
> Todo lo demás son formas de responderla. Este documento es para que **cualquier
> integrante** pueda contestar **cualquier** pregunta, porque la nota es individual y
> las preguntas van dirigidas.

Fuente única de verdad del código: `README.md`, `config/config.yaml`, `dags/pipeline_ajedrez_dag.py`
y `src/`. Esta guía traduce todo eso a "qué decir y qué mostrar".

---

## 0. Antes de entrar al aula (checklist físico)

Los 20 minutos son para mostrar y explicar, **no** para instalar ni esperar descargas.

- [ ] **Airflow levantado** en la notebook de alguien del grupo, con la UI abierta en
      el navegador (`http://localhost:8080`, usuario/clave `admin`/`admin`).
      Se prende **antes** de entrar:
      ```bash
      cp .env.example .env            # solo la primera vez
      docker compose up airflow-init  # solo la primera vez (migra la BD 3.x y crea el admin)
      docker compose up -d            # levanta api-server + scheduler + dag-processor + triggerer + worker + postgres + redis
      ```
- [ ] **Una corrida en verde ya hecha** en el historial del DAG `pipeline_ajedrez_chesscom`
      (pestaña *Grid*, todas las tareas en verde). **No** se corre en vivo: si tarda
      5 minutos, son 5 de los 20.
- [ ] **El CSV producido abierto o listo para abrir**:
      `data/processed/partidas_ajedrez_clean_sample.csv` (muestra de 5.000 filas) y/o el
      Parquet completo `partidas_ajedrez_clean.parquet`.
- [ ] **Los 7 criterios verificados** con los números a mano (sección 3 de esta guía).
- [ ] Un notebook o consola con el `df` ya cargado para correr las verificaciones en vivo
      si lo piden:
      ```python
      import pandas as pd
      df = pd.read_parquet("data/processed/partidas_ajedrez_clean.parquet")
      ```

> Si algo no llegó a funcionar: **vení igual y decílo**. Mostrar un pipeline a medias y
> saber dónde está trabado se lleva devolución útil. No presentarse, no.

---

## 1. De qué se trata (min 0–2) — tres oraciones, sin filminas

1. **La pregunta.** ¿Qué combinación de nivel de ELO, apertura, modalidad de ritmo
   (bullet/blitz/rapid) y color de piezas predice quién gana una partida de ajedrez
   online y cuán larga es?
2. **La fuente.** La **PubAPI pública de Chess.com** (solo lectura, sin cuenta ni API key),
   consultada de forma automatizada para 8 cuentas de niveles distintos.
3. **Qué es una fila.** *Una fila es una **partida** individual de ajedrez rated
   (bullet/blitz/rapid) jugada por alguna de las cuentas configuradas.*

> **"Una fila es un ___" → una partida.** Coincide con la unidad de la pregunta: la
> pregunta es sobre partidas, y la fila es una partida. Si alguien pregunta "¿y no es un
> jugador, o una jugada?": no — un jugador aparece en muchas filas, y una jugada está
> **dentro** de la columna `moves_text` de una fila (ver la "concesión" en la sección 5).

---

## 2. La corrida (min 2–7) — recorrer el grafo tarea por tarea

El DAG es `pipeline_ajedrez_chesscom` (`dags/pipeline_ajedrez_dag.py`). La descarga se **abre
en paralelo por cuenta** (una task instance por usuario, con dynamic task mapping `.expand()`)
y se **cierra** en una tarea que consolida; de ahí en adelante el grafo es **lineal** porque
cada etapa consume lo que produjo la previa.

```
listar_usuarios → descarga_usuario (×8, .expand) → consolidar_descarga → limpieza_y_parseo → ingenieria_de_caracteristicas → verificar_calidad → exportar_dataset
```

| # | Tarea (task_id) | Módulo | Qué hace | Por qué está ahí |
|---|---|---|---|---|
| 1 | `listar_usuarios` | inline (lee config) | Devuelve la lista de las 8 cuentas del config: es la fuente sobre la que se hace el `.expand()`. | Da el input del fan-out mapeado. |
| 2 | `descarga_usuario` (**mapeada** por cuenta) | `src/download_data.py` | **Una instancia por cuenta** (índice `0..7`, el nombre visible es el username). Pide `.../games/archives`, recorre los archivos mensuales del más reciente al más viejo **salteando los posteriores a `until_month: "2026-08"`** (ventana congelada) y guarda hasta **1.000 partidas rated** (bullet/blitz/rapid) por cuenta en `data/raw/`. Si la cuenta falla (404, sin partidas, red) **no rompe el fan-out**: devuelve un estado "falló". Corre con **`max_active_tis_per_dag=3`** (3 cuentas en paralelo, para no exceder el rate-limit de Chess.com). | Es la **ingesta automatizada**, ahora paralela por cuenta. Guarda el crudo **tal como llega** (capa bronce). |
| 3 | `consolidar_descarga` | `src/download_data.py` | Junta los resultados mapeados y exige los mínimos de tolerancia a fallos **después** del fan-out: corta solo si baja de `min_users_ok: 6` o `min_total_games: 4000`. | Cierra el fan-out y decide si el conjunto descargado alcanza. |
| 4 | `limpieza_y_parseo` | `src/clean_data.py` | Parsea el PGN de cada partida (headers + jugadas), **deduplica por `GameUrl`**, convierte ELOs y control de tiempo a numérico, cuenta jugadas y **filtra** filas inválidas (sin resultado, sin ELO, no-rated, no-estándar, o con < 5 medio-movimientos). | Convierte el crudo semiestructurado en una **tabla tidy**. El filtro define el universo de análisis. |
| 5 | `ingenieria_de_caracteristicas` | `src/feature_engineering.py` | Deriva características analíticas: `diferencia_elo`, `elo_promedio`, `favorito`, `nivel_promedio` (bandas de ELO), `modalidad`, `es_sorpresa`, `familia_apertura` (letra ECO). | Agrega las variables sobre las que se va a modelar en la Entrega 3. |
| 6 | `verificar_calidad` | inline en el DAG | Lee el parquet **intermedio** (antes de exportar) y hace `assert` de los **7 criterios** (entre ellos: mezcla de tipos **con fecha obligatoria**, nulos solo en columnas documentadas, y **ambos** targets `resultado` y `cantidad_jugadas` sin nulos), más un chequeo de **rango plausible de ELO** `[100, 4000]`. Es un límite amplio para detectar corrupción, no un supuesto récord máximo. Si algo falla, **el DAG se pone en rojo y `exportar_dataset` no llega a correr**. También registra el volumen en una Airflow Variable y avisa si se desvía > 5 % del baseline. | Garantía operativa: **toda corrida en verde ⟹ dataset válido**, y no se materializan artefactos de un dataset inválido. |
| 7 | `exportar_dataset` | `src/pipeline.py` | Escribe el **Parquet completo**, una **muestra CSV** de hasta 5.000 filas (`random_state=42`) y `data_summary.json` con métricas. | Materializa la **capa plata** (el entregable) en disco, **solo si la validación pasó**. |

**Cómo pasan los datos entre tareas:** el DAG está escrito con la **TaskFlow API de
Airflow 3** (`@dag` / `@task` de `airflow.sdk`), con **dynamic task mapping** (`.expand()`) en
la descarga; las dependencias salen de pasar el return de una tarea como argumento de la
siguiente. Por XCom viajan solo *metadatos* (las rutas y los conteos, no los DataFrames); el
DataFrame intermedio se serializa en `data/processed/_interim_clean.parquet` y `exportar_dataset`
lo borra. Airflow corre sobre **Apache Airflow 3.3** con **CeleryExecutor**: postgres =
metadatos, redis = broker, api-server = UI/API, scheduler + dag-processor + triggerer =
orquestación, worker = ejecución.

**Frase para el grafo:** "La descarga es paralela **por cuenta** (fan-out con `.expand()`),
porque las 8 cuentas son independientes; después el grafo es lineal, porque no podés limpiar lo
que no descargaste ni exportar lo que no validaste. La validación es un portero de calidad que
corre **antes** de exportar: si el dataset no cumple, ni siquiera se escriben los artefactos."

---

## 3. El dataset contra los 7 criterios (min 7–12) — con números

Corrida real validada el **07/09/2026** (DAG completo en **Airflow 3.3**, disparada por el
scheduler con CeleryExecutor, ventana congelada hasta agosto de 2026): **7.215 registros
descargados → 7.204 partidas finales** (99,85 % de retención). Comandos para verificar **en
vivo** sobre `df`:

| # | Criterio | Qué tiene que dar | Cómo se verifica | Resultado |
|---|---|---|---|---|
| 1 | **Clave sin duplicados** | `True` | `df["GameUrl"].is_unique` | ✅ `True` |
| 2 | **Volumen suficiente** | ≥ `quality.min_final_games` = **4.000** filas | `len(df)` | ✅ `7204` |
| 3 | **Ancho suficiente** | ≥ 5 columnas útiles | `df.shape` | ✅ `(7204, 27)` |
| 4 | **Mezcla de tipos** | numéricas + categóricas **+ fecha** | `df.dtypes.value_counts()` | ✅ int/float + category/object + datetime64 (las tres, fecha obligatoria) |
| 5 | **Nulos conocidos** | solo en columnas documentadas | `df.isna().mean().sort_values(ascending=False)` | ✅ ninguna (ver sección 4) |
| 6 | **Sin columnas vacías** | ninguna 100 % nula | `df.columns[df.isna().all()]` | ✅ vacío |
| 7 | **Columnas objetivo** | `resultado` **y** `cantidad_jugadas` sin nulos | `df[["resultado","cantidad_jugadas"]].isna().sum()` | ✅ `0` y `0` |
| + | **Precisión de ELO** (extensión propia) | `WhiteElo`/`BlackElo` en rango plausible `[100, 4000]` | `df[["WhiteElo","BlackElo"]].agg(["min","max"])` | ✅ observado 732–3468 / 218–3469 |

> **El criterio 2 no usa el "1.000" heredado del ejemplo de cátedra.** Exige el mínimo
> explícito `quality.min_final_games: 4000`, porque ese es el requisito del dataset final.
> `download.min_total_games: 4000` controla por separado el volumen de la descarga cruda.
> Si la limpieza deja menos de 4.000 partidas, el DAG falla y el log muestra los conteos
> crudo y final para investigar la causa.

> **El criterio 1 (clave) es el más importante y el más subestimado.** Es el test operativo
> de la unidad de análisis: si `GameUrl` repitiera, o la unidad está mal definida o el
> pipeline está duplicando filas. Que dé `is_unique == True` prueba que "una fila = una
> partida" **de verdad**, no de palabra. La deduplicación por `GameUrl` en la tarea 2 es
> lo que lo garantiza (en la corrida validada eliminó 1 partida en la que dos de las cuentas
> configuradas se enfrentaron entre sí).

**La clave es `GameUrl`.** **La columna objetivo es `resultado`** (categórica: *Gana Blancas
/ Gana Negras / Empate*), target de clasificación; `cantidad_jugadas` es el target de
regresión (cuán larga es la partida). El criterio 7 del DAG exige que **ambas** estén
presentes y sin nulos, así que las dos son "columna objetivo" a los fines de la verificación.

---

## 4. Lo que se pregunta, no se mide (las respuestas obligadas)

### "Una fila es un ___"
**Una partida.** (Ver sección 1.) Coincide con la pregunta del proyecto.

### Cuál es la columna objetivo
**`resultado`** — columna concreta del CSV, no una idea. Distribución esperada: mayoría
*Gana Blancas* / *Gana Negras*, minoría *Empate*. Objetivo de regresión: `cantidad_jugadas`.
El DAG verifica que **ambas** estén sin nulos (criterio 7).

### Por qué hay nulos donde hay nulos
No pedimos cero nulos (no existen en datos reales); pedimos **saber cuáles y por qué**.
En la corrida validada el dataset final quedó con **0 nulos**, y eso es **una decisión, no
suerte**: el filtro de la tarea 2 **descarta** toda fila sin `resultado`, sin
`WhiteElo`/`BlackElo`, no-rated o con menos de 5 jugadas. Los nulos no se "rellenan": se
eliminan las filas que los tendrían en las columnas críticas.

Además el criterio 5 del DAG es **formal**: hay un diccionario `NULOS_DOCUMENTADOS` (hoy
vacío) y cualquier nulo en una columna **no documentada** rompe la corrida. O sea, la política
actual es "cero nulos, y si algún día aceptamos alguno tiene que estar declarado y explicado".

Dónde **podrían** aparecer nulos si en el futuro se relaja el filtro, y qué significarían:
- `Opening` / `ECO`: partida sin apertura registrada por Chess.com (raro, pero posible).
- `Date`: fecha malformada en el PGN → `pd.to_datetime(..., errors="coerce")` la deja `NaT`.
- `incremento_seg`: 0 (no nulo) cuando el control de tiempo no tiene incremento (ej. `180`).

**Cómo contestar si aparecen nulos en la corrida del día:** correr
`df.isna().mean().sort_values(ascending=False)`, señalar la columna con más nulos y explicar
la causa de esa columna puntual, nunca "no sé". (Con la config actual no deberían aparecer:
si aparecen, el DAG habría quedado en rojo en `verificar_calidad`.)

### Nulos "disfrazados" de categoría (completitud honesta)
Dos columnas usan una etiqueta de reemplazo cuando el crudo no trae el dato:
`familia_apertura="Desconocida"` (ECO ausente o fuera de A–E) y `Termination="otro"` (motivo de
finalización no reconocido). No son nulos técnicos, pero contra la dimensión **completitud** son
missingness disfrazada. Por eso `data_summary.json` los **reporta explícitamente** (sección
`categorias_fallback`, con filas y %): en la corrida validada ambos dan **0 filas (0 %)**, lo que
confirma que no hay datos encubiertos. Es una decisión de diseño (no se imputan ni se descartan),
pero queda visible, no escondida.

### Cómo sabés que el volumen no se degradó entre corridas
`verificar_calidad` guarda el volumen de la última corrida exitosa en una **Airflow Variable**
(`pipeline_ajedrez_volumen_baseline`) y **avisa** (no rompe) si la corrida actual se desvía > 5 %
del baseline. Como `until_month` está congelado, el volumen debería ser estable entre corridas
(≈ 7.204); un desvío grande señala que cambió la config o la fuente. Es observabilidad, no un
criterio de rechazo.

### Qué pasa si lo corrés de nuevo — ¿sale el mismo archivo?
**Sí, sale el mismo dataset**, por dos motivos que se refuerzan:
- **Ventana temporal congelada:** `config.yaml` fija `download.until_month: "2026-08"`, así que
  se ignoran los archivos mensuales posteriores a agosto de 2026. Aunque Chess.com es una
  **fuente viva** (cada mes entran partidas nuevas arriba de la pila), el tope neutraliza eso:
  incluso **borrando `data/raw/` y descargando de cero** se obtiene el mismo conjunto de
  partidas que la corrida validada.
- **Idempotencia + determinismo:** si el JSON ya existe en `data/raw/`, la descarga se saltea;
  y limpieza + features son deterministas (la muestra CSV usa `random_state=42`).

El único caso en que cambiaría es si alguien **mueve `until_month` o lo pone en `null`**: ahí
tomaría hasta el mes actual e incorporaría partidas nuevas. Es el mecanismo previsto para
retomar la ingesta en las próximas entregas, no un bug.

### Dónde guardás el dato crudo (bronce vs. plata)
- **Bronce:** los JSON en `data/raw/` (`chesscom_<cuenta>_raw.json`), guardados **tal como
  llegan de la API**, sin transformar. Si mañana descubrimos que interpretábamos mal una
  columna, se corrige el parseo y se regenera **sin volver a pegarle a la API**.
- **Plata:** lo que entregamos — `partidas_ajedrez_clean.parquet` + la muestra CSV +
  `data_summary.json`.

> Nota: `data/` está en `.gitignore` (no se versiona) **a propósito**: es regenerable
> corriendo el pipeline. Lo que se versiona es el **código que lo produce**.

---

## 5. La confesión: dónde el dataset se aparta del ideal "tidy"

Un grupo que sabe dónde su dataset se aparta del ideal está mejor parado que uno que
recita la definición de memoria. Tenemos **tres** concesiones honestas para poner sobre la
mesa antes de que las encuentren:

1. **`moves_text` no es atómica (concesión tidy).** Guarda **toda** la secuencia de jugadas
   de la partida en una sola celda (`"1. e4 c5 2. Nf3 ..."`). Es el análogo exacto al
   `player_positions` del dataset canónico de la cátedra: viola "cada celda un valor".
   **Por qué se decidió así:** separar cada jugada en su propia fila rompería la unidad
   "una fila = una partida" y explotaría el volumen; separarlas en columnas daría cientos
   de columnas de ancho variable. La concesión es deliberada, y por eso además derivamos
   `cantidad_jugadas` (un solo valor, numérico), que es la que se usa para modelar la
   duración — igual que la cátedra deriva `best_position`.

2. **Fuga de información del ELO hacia `resultado` (limitación de la fuente).** Chess.com
   entrega el rating **posterior** a la partida (ya ajustado por el resultado), no el previo.
   Entonces `WhiteElo`, `BlackElo` y todo lo derivado contienen una fuga chica pero
   sistemática hacia el target, concentrada en partidas parejas. **No se parchea a lo bruto:**
   se documenta como limitación conocida para tenerla en cuenta en el modelado de la
   Entrega 3.

3. **La muestra no es aleatoria (limitación de representatividad).** Las 8 cuentas van de
   nivel club a élite mundial (varias streamers); el 100 % de las filas contiene al menos
   una de ellas y la mediana de `WhiteElo` es ~2778 (nivel GM). Las conclusiones valen para
   "jugadores de nivel intermedio a élite en Chess.com", no para "el ajedrez online" en
   general.

---

## 6. Preguntas dirigidas — banco de respuestas rápidas

La pregunta sobre el scraping le puede caer a quien escribió la transformación. Todos
deberían poder contestar esto:

- **"¿Qué parte del grafo es paralela y qué parte es lineal?"** La **descarga es paralela por
  cuenta**: `descarga_usuario` es una tarea mapeada con `.expand()` (una instancia por usuario,
  hasta 3 en paralelo), porque las 8 cuentas son independientes. Después `consolidar_descarga`
  cierra el fan-out y el resto es **lineal**, porque cada tarea consume el output de la anterior
  (no podés limpiar lo que no descargaste ni exportar lo que no validaste).
- **"¿Cómo garantizás que una corrida verde = dataset bueno?"** `verificar_calidad` hace
  `assert` de los 7 criterios (más el rango de ELO) **antes** de exportar; si alguno falla, el
  DAG queda en rojo y `exportar_dataset` ni siquiera corre. Verde implica que todo pasó y que los
  artefactos en disco corresponden a un dataset válido.
- **"¿Cuál es la clave y cómo sabés que no repite?"** `GameUrl`; `df["GameUrl"].is_unique`
  da `True`; la tarea 2 deduplica por esa columna.
- **"¿Por qué filtran partidas con menos de 5 jugadas?"** Son abandonos o resultados
  administrativos inmediatos (no partidas jugadas); distorsionan la cola baja de
  `cantidad_jugadas` y no aportan señal.
- **"¿Por qué normalizan `Termination`?"** El crudo trae el username del ganador embebido
  ("erik won by resignation"), lo que la vuelve casi un identificador (cardinalidad ~ nº de
  filas). Se reduce al motivo puro (`resignation`, `time`, `checkmate`, …) para que sirva
  como categórica.
- **"¿Y si la API está caída el día de la defensa?"** No importa: la corrida ya está hecha y
  en verde en el historial, y el crudo está en `data/raw/`. La descarga es idempotente.
- **"¿Y si una de las 8 cuentas falla al descargar?"** El pipeline **tolera fallos por
  usuario**: cada cuenta es una tarea mapeada aparte, así que si una da 404, no tiene partidas o
  hay error de red, esa instancia devuelve un estado "falló" y **no rompe el fan-out**. Recién
  `consolidar_descarga` corta con error si quedan menos de `min_users_ok: 6` cuentas o menos de
  `min_total_games: 4000` partidas crudas. Una cuenta caída no tira abajo la corrida, pero un
  dataset demasiado chico sí se rechaza.
- **"¿Sale el mismo dataset si lo corrés de nuevo?"** Sí: la **ventana congelada**
  (`until_month: "2026-08"`) hace que incluso una descarga desde cero reproduzca el mismo
  conjunto; y con el crudo presente la descarga se saltea (idempotente). Ver §4.
- **"¿Dónde está el rate-limiting / cómo respetás a Chess.com?"** Sesión identificada con
  `User-Agent`, requests en serie por cuenta con `request_delay` y reintentos con backoff ante
  429/5xx (`src/download_data.py`). El fan-out corre **como mucho 3 cuentas en paralelo**
  (`max_active_tis_per_dag=3`) justo para no exceder el rate-limit al paralelizar.
- **"¿Es reproducible la muestra CSV?"** Sí, `df.sample(n=5000, random_state=42)`.

---

## 7. Cómo se aprueba (la vara, para autochequeo)

- [x] Hay una corrida completa **en verde**, hecha por nosotros, visible en la UI.
- [x] Sabemos explicar **qué hace cada tarea y por qué está ahí** (sección 2).
- [x] El pipeline produce un CSV que **cumple los criterios medibles** (sección 3).
- [x] Sabemos **defender las decisiones** de las secciones 4 y 5.
- [x] Las respuestas **no vienen de una sola persona**: repartir quién contesta qué, pero
      que todos entiendan todo.

**No hacer:** llegar sin el entorno levantado · correr el pipeline en vivo (si querés mostrar
una ejecución, que sea sobre una muestra chica **además** de la que ya está) · que hable uno
solo.
