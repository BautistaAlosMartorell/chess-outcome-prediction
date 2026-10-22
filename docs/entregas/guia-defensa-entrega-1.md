# Guía de defensa — Entrega 1 (Ajedrez online, Chess.com)

> **La pregunta de fondo de esta entrega es una sola:**
> ¿tenés un pipeline que produce tu dataset sin que nadie lo toque a mano?
> Todo lo demás son formas de responderla. Este documento es para que **cualquier
> integrante** pueda contestar **cualquier** pregunta, porque la nota es individual y
> las preguntas van dirigidas.

Fuente única de verdad del código: `README.md`, `config/config.yaml`, `dags/pipeline_ajedrez_dag.py`
y `src/`. Esta guía traduce todo eso a "qué decir y qué mostrar". Los números son los de la
**corrida oficial del 22/10/2026** (`docs/entregas/plan-coherencia.md`, hoja de datos).

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

1. **La pregunta.** ¿Qué tan bien se puede predecir quién gana una partida de ajedrez
   online, y cuánto le falta para terminar, **antes de que empiece y a medida que avanza**?
2. **La fuente.** La **PubAPI pública de Chess.com** (solo lectura, sin cuenta ni API key),
   consultada de forma automatizada. La primera tarea del DAG (`listar_jugadores`)
   **selecciona sola**, en la primera corrida, ~120 cuentas repartidas en 6 bandas de ELO,
   tomadas de listas públicas por país, titulados y rankings, y deja esa lista congelada y
   versionada en `config/`.
3. **Qué es una fila.** *Una fila es **una partida en un momento dado**: la partida vista
   después de 0, 5, 10, …, 120 medio-movimientos (plies), uno cada 5.* El pipeline produce dos
   tablas: la base, con **una fila por partida** (rated, bullet/blitz/rapid, de alguna de
   las cuentas seleccionadas), y la de cortes, derivada de la base, con **una fila por
   (partida, corte)**. La de cortes es la que se modela.

> **"Una fila es un ___" → una partida en un momento dado (partida × corte).** Coincide con
> la pregunta: queremos predecir el resultado en distintos momentos de la partida, y cada
> fila es justamente la partida en uno de esos momentos, con sólo lo que se veía ahí. El
> corte 0 (antes de mover) es la predicción pre-partida. Si alguien pregunta "¿y no es una
> partida, como al principio?": la tabla base lo sigue siendo, y de ahí se deriva la de
> cortes. Si pregunta "¿y no es una jugada?": no — un corte es una foto de la posición y
> los relojes en un ply fijo, no cada jugada (ver la "concesión" en la sección 5).

---

## 2. La corrida (min 2–7) — recorrer el grafo tarea por tarea

El DAG es `pipeline_ajedrez_chesscom` (`dags/pipeline_ajedrez_dag.py`). La descarga se **abre
en paralelo por cuenta** (una task instance por usuario, con dynamic task mapping `.expand()`)
y se **cierra** en una tarea que consolida; de ahí en adelante el grafo es **lineal** porque
cada etapa consume lo que produjo la previa.

```
listar_jugadores → descarga_usuario (×N, .expand) → consolidar_descarga → limpieza_y_parseo → ingenieria_de_caracteristicas → verificar_calidad → exportar_dataset → construir_dataset_cortes
```

| # | Tarea (task_id) | Módulo | Qué hace | Por qué está ahí |
|---|---|---|---|---|
| 1 | `listar_jugadores` | `src/player_selection.py` | **Selecciona una sola vez** los jugadores a descargar: en la primera corrida arma cuatro pools de candidatos (FM/CM/NM → avanzado; GM/IM → experto y top_mundial; jugadores por país → principiante e intermedio; rankings → elite). Los baraja con semilla fija, valida cada candidato y junta 20 por banda de ELO. Guarda el avance en un checkpoint por si se corta. Congela el resultado en `config/jugadores_seleccionados.yaml` (versionado en git), que también es el manifiesto. Si el config suma una banda, completa sólo esa y conserva las cuentas previas; en las otras corridas sólo lee ese archivo. Es la fuente del `.expand()`. | Da el input del fan-out mapeado y hace que la muestra sea **reproducible y auditable**: no cambia entre corridas ni entre máquinas. |
| 2 | `descarga_usuario` (**mapeada** por cuenta) | `src/download_data.py` | **Una instancia por cuenta** (el nombre visible es el username). Pide `.../games/archives`, recorre los archivos mensuales del más reciente al más viejo **salteando los posteriores a `until_month: "2026-08"`** (ventana congelada) y guarda hasta **1.000 partidas rated** (bullet/blitz/rapid) por cuenta en `data/raw/`. Si la cuenta falla (404, sin partidas, red) **no rompe el fan-out**: devuelve un estado "falló". Corre con **`max_active_tis_per_dag=3`** (3 cuentas en paralelo, para no exceder el rate-limit de Chess.com). | Es la **ingesta automatizada**, paralela por cuenta. Guarda el crudo **tal como llega** (capa bronce). |
| 3 | `consolidar_descarga` | `src/download_data.py` | Junta los resultados mapeados y exige los mínimos de tolerancia a fallos **después** del fan-out: corta solo si baja de `min_users_ok: 80` o `min_total_games: 1500`. | Cierra el fan-out y decide si el conjunto descargado alcanza. |
| 4 | `limpieza_y_parseo` | `src/clean_data.py` | Parsea el PGN de cada partida (headers + jugadas), **deduplica por `GameUrl`**, convierte ELOs y control de tiempo a numérico, cuenta jugadas, conserva el torneo y los horarios exactos de inicio y fin, **filtra** filas inválidas (sin resultado, sin ELO, no-rated, no-estándar, o con < 5 medio-movimientos) y ordena por `GameUrl`. | Convierte el crudo semiestructurado en una **tabla tidy**. El filtro define el universo de análisis. |
| 5 | `ingenieria_de_caracteristicas` | `src/feature_engineering.py` | Deriva características analíticas: `diferencia_elo`, `elo_promedio`, `nivel_promedio` (bandas de ELO), `es_sorpresa`, `familia_apertura` (letra ECO), `matchup_apertura` (primera jugada de blancas × respuesta de negras) y las tasas históricas de resultado de ese matchup, calculadas sólo con partidas que terminaron antes de que empiece cada una. | Agrega variables para el EDA y el modelado. Las que tienen fuga (las del rating posterior) se marcan y no entran al modelo. |
| 6 | `verificar_calidad` | inline en el DAG | Lee el parquet **intermedio** (antes de exportar) y hace `assert` de los **7 criterios** (entre ellos: mezcla de tipos **con fecha obligatoria**, nulos solo en columnas documentadas, y **ambos** targets `resultado` y `cantidad_jugadas` sin nulos), más un chequeo de **rango plausible de ELO** `[100, 4000]`. Es un límite amplio para detectar corrupción, no un supuesto récord máximo. Si algo falla, **el DAG se pone en rojo y `exportar_dataset` no llega a correr**. También registra el volumen en una Airflow Variable y avisa si se desvía > 5 % del baseline. | Garantía operativa: **toda corrida en verde ⟹ dataset válido**, y no se materializan artefactos de un dataset inválido. |
| 7 | `exportar_dataset` | `src/pipeline.py` | Escribe el **Parquet completo**, una **muestra CSV** de hasta 5.000 filas (`random_state=42`) y `data_summary.json` con métricas. | Materializa la **capa plata** (el entregable) en disco, **solo si la validación pasó**. |
| 8 | `construir_dataset_cortes` | `src/live_features.py` | Reproduce cada partida jugada a jugada con python-chess desde el PGN crudo (el único lugar con los relojes `%clk`) y escribe `partidas_cortes.parquet`: una fila por partida y corte (uno cada 5 plies, del 0 al 120) con material, jaques, capturas, enroques, movilidad y relojes en ese momento. Falla si una partida no tiene PGN, si los plies reproducidos no coinciden con `cantidad_jugadas` o si la clave `(GameUrl, corte_ply)` se repite. | Es la **tabla de modelado**: la que permite predecir antes y durante la partida. Ninguna feature de un corte mira jugadas posteriores (hay un test que lo garantiza). |

**Cómo pasan los datos entre tareas:** el DAG está escrito con la **TaskFlow API de
Airflow 3** (`@dag` / `@task` de `airflow.sdk`), con **dynamic task mapping** (`.expand()`) en
la descarga; las dependencias salen de pasar el return de una tarea como argumento de la
siguiente. Por XCom viajan solo *metadatos* (las rutas y los conteos, no los DataFrames); el
DataFrame intermedio se serializa en `data/processed/_interim_clean.parquet` y `exportar_dataset`
lo borra. Airflow corre sobre **Apache Airflow 3.3** con **CeleryExecutor**: postgres =
metadatos, redis = broker, api-server = UI/API, scheduler + dag-processor + triggerer =
orquestación, worker = ejecución.

**Frase para el grafo:** "La descarga es paralela **por cuenta** (fan-out con `.expand()`),
porque las cuentas son independientes; después el grafo es lineal, porque no podés limpiar lo
que no descargaste ni exportar lo que no validaste. La validación es un portero de calidad que
corre **antes** de exportar: si el dataset no cumple, ni siquiera se escriben los artefactos."

---

## 3. El dataset contra los 7 criterios (min 7–12) — con números

Corrida oficial del **22/10/2026** (DAG completo en **Airflow 3.3**, CeleryExecutor,
ventana congelada hasta agosto de 2026, 120 jugadores seleccionados —20 por banda de
ELO—): **101.094 registros descargados → 100.396 partidas finales** (99,31 % de retención) y
**1.559.622 filas de cortes**. Comandos para verificar **en vivo** sobre `df`:

| # | Criterio | Qué tiene que dar | Cómo se verifica | Resultado |
|---|---|---|---|---|
| 1 | **Clave sin duplicados** | `True` | `df["GameUrl"].is_unique` | ✅ `True` |
| 2 | **Volumen suficiente** | ≥ `quality.min_final_games` = **1.500** filas | `len(df)` | ✅ `100396` |
| 3 | **Ancho suficiente** | ≥ 5 columnas útiles | `df.shape` | ✅ `(100396, 35)` |
| 4 | **Mezcla de tipos** | numéricas + categóricas **+ fecha** | `df.dtypes.value_counts()` | ✅ int/float + category/object + datetime64 (las tres, fecha obligatoria) |
| 5 | **Nulos conocidos** | solo en columnas documentadas | `df.isna().mean().sort_values(ascending=False)` | ✅ sólo `TournamentUrl` y las tres `tasa_*_hist`, las dos estructurales y documentadas (ver sección 4) |
| 6 | **Sin columnas vacías** | ninguna 100 % nula | `df.columns[df.isna().all()]` | ✅ vacío |
| 7 | **Columnas objetivo** | `resultado` **y** `cantidad_jugadas` sin nulos | `df[["resultado","cantidad_jugadas"]].isna().sum()` | ✅ `0` y `0` |
| + | **Precisión de ELO** (extensión propia) | `WhiteElo`/`BlackElo` en rango plausible `[100, 4000]` | `df[["WhiteElo","BlackElo"]].agg(["min","max"])` | ✅ observado 100–3462 / 100–3459 (100 es el piso de rating de Chess.com) |
| + | **Consistencia de torneo y horarios** (extensión propia) | `EsTorneo` = `TournamentUrl` presente; `StartTime` ≤ `EndTime`; tasas nulas sólo sin historial | asserts de `verificar_calidad` | ✅ |

**La tabla de cortes** se valida en `construir_dataset_cortes`: clave `(GameUrl, corte_ply)`
única, cada partida del Parquet encuentra su PGN y los plies reproducidos coinciden con
`cantidad_jugadas` en las 100.396. Sus únicos nulos son `gasto_reciente_*` en el corte 0
(todavía no hubo jugadas).

> **El criterio 2 no usa el "1.000" heredado del ejemplo de cátedra.** Exige el mínimo
> explícito `quality.min_final_games: 1500`, porque ese es el requisito del dataset final.
> `download.min_total_games: 1500` controla por separado el volumen de la descarga cruda.
> Si la limpieza deja menos de 1.500 partidas, el DAG falla y el log muestra los conteos
> crudo y final para investigar la causa.

> **El criterio 1 (clave) es el más importante y el más subestimado.** Es el test operativo
> de la unidad de análisis: si `GameUrl` repitiera, o la unidad está mal definida o el
> pipeline está duplicando filas. Que dé `is_unique == True` prueba que "una fila = una
> partida" en la tabla base **de verdad**, no de palabra. La deduplicación por `GameUrl` en
> la tarea 4 es lo que lo garantiza (en la corrida oficial eliminó 5 partidas en las que dos
> de las cuentas seleccionadas se enfrentaron entre sí).

**La clave es `GameUrl`** en la tabla base y **`(GameUrl, corte_ply)`** en la de cortes.
**La columna objetivo es `resultado`** (categórica: *Gana Blancas / Gana Negras / Empate*),
target de clasificación en cada corte. El target de regresión es la duración: en la tabla
base `cantidad_jugadas` (plies totales) y en la de cortes `plies_restantes` (los que faltan
desde el corte, `cantidad_jugadas − corte_ply`). El criterio 7 del DAG exige que
`resultado` y `cantidad_jugadas` estén presentes y sin nulos.

---

## 4. Lo que se pregunta, no se mide (las respuestas obligadas)

### "Una fila es un ___"
**Una partida en un momento dado** (partida × corte) en la tabla de modelado, derivada de
la base, que tiene una partida por fila. (Ver sección 1.) Coincide con la pregunta del
proyecto: predecir antes y durante la partida.

### Cuál es la columna objetivo
**`resultado`** — columna concreta del CSV, no una idea. En la corrida oficial: *Gana
Blancas* 48,8 %, *Gana Negras* 44,4 %, *Empate* 6,8 %. Objetivo de regresión:
`plies_restantes` en la tabla de cortes (`cantidad_jugadas` en la base). El DAG verifica
que `resultado` y `cantidad_jugadas` estén sin nulos (criterio 7).

### Por qué hay nulos donde hay nulos
No pedimos cero nulos (no existen en datos reales); pedimos **saber cuáles y por qué**.
En las columnas críticas no hay ninguno, y eso es **una decisión, no suerte**: el filtro de
la tarea 4 **descarta** toda fila sin `resultado`, sin `WhiteElo`/`BlackElo`, no-rated o con
menos de 5 jugadas. Los nulos no se "rellenan": se eliminan las filas que los tendrían en
las columnas críticas.

Los nulos que quedan son **estructurales**, no faltantes: el dato no existe, y está bien
que no exista.
- `TournamentUrl`: nula en las 89.256 partidas que **no son de torneo** (88,9 %).
  `verificar_calidad` comprueba que coincide exactamente con `EsTorneo = False`.
- `tasa_blancas_hist`, `tasa_tablas_hist`, `tasa_negras_hist`: nulas en las 1.620 partidas
  cuyo matchup de apertura tenía **menos de 30 partidas previas** en ese ritmo (no había
  historia que mirar). Se dejan NaN a propósito, sin imputar, y `verificar_calidad`
  comprueba que sólo faltan cuando `historial_suficiente = False`.

El criterio 5 del DAG es **formal**: hay un diccionario `nulos_documentados` con esas
columnas y su explicación, y cualquier nulo en una columna **no documentada** rompe la
corrida.

**Cómo contestar si preguntan por los nulos en vivo:** correr
`df.isna().mean().sort_values(ascending=False)`, señalar `TournamentUrl` y explicar que es
nula porque la partida no es de torneo; nunca "no sé".

### Nulos "disfrazados" de categoría (completitud honesta)
Dos columnas usan una etiqueta de reemplazo cuando el crudo no trae el dato:
`familia_apertura="Desconocida"` (ECO ausente o fuera de A–E) y `Termination="otro"` (motivo de
finalización no reconocido). No son nulos técnicos, pero contra la dimensión **completitud** son
missingness disfrazada. Por eso `data_summary.json` los **reporta explícitamente** (sección
`categorias_fallback`, con filas y %): en la corrida oficial ambos dan **0 filas (0 %)**, lo que
confirma que no hay datos encubiertos. Es una decisión de diseño (no se imputan ni se descartan),
pero queda visible, no escondida.

### Cómo sabés que el volumen no se degradó entre corridas
`verificar_calidad` guarda el volumen de la última corrida exitosa en una **Airflow Variable**
(`pipeline_ajedrez_volumen_baseline`) y **avisa** (no rompe) si la corrida actual se desvía > 5 %
del baseline. Como `until_month` está congelado, el volumen debería ser estable entre corridas
(≈ 100.396); un desvío grande señala que cambió la config, la selección o la fuente. Es observabilidad, no un
criterio de rechazo.

### Qué pasa si lo corrés de nuevo — ¿sale el mismo archivo?
**Sí, sale el mismo dataset, también en otra máquina**, por tres motivos que se refuerzan:
- **Lista de jugadores congelada y versionada:** `listar_jugadores` seleccionó los 100
  jugadores una vez y los guardó en `config/jugadores_seleccionados.yaml`, que está en git.
  Las corridas siguientes, en cualquier máquina, leen ese archivo y no vuelven a
  seleccionar, así que siempre se descargan las mismas cuentas. (Antes la lista vivía en
  `data/`, ignorada por git, y cada integrante tenía la suya: por eso se movió.)
- **Ventana temporal congelada:** `config.yaml` fija `download.until_month: "2026-08"`, así que
  se ignoran los archivos mensuales posteriores a agosto de 2026. Aunque Chess.com es una
  **fuente viva** (cada mes entran partidas nuevas arriba de la pila), el tope neutraliza eso:
  con la misma lista de jugadores, **borrar los JSON de partidas y descargar de cero** da el
  mismo conjunto de partidas.
- **Idempotencia + determinismo:** si el JSON ya existe en `data/raw/`, la descarga se saltea;
  y limpieza + features son deterministas: las filas se ordenan por `GameUrl` y la muestra
  CSV usa `random_state=42`. El DAG y el notebook 01 escriben exactamente el mismo archivo.

Cambiaría solo en dos casos, y los dos son a propósito:
- si alguien **borra el archivo de selección**: se vuelve a sortear desde listas vivas y
  pueden salir otros jugadores;
- si alguien **mueve `until_month` o lo pone en `null`**: ahí se tomaría hasta el mes actual
  y entrarían partidas nuevas. Es el mecanismo previsto para retomar la ingesta en las
  próximas entregas.

### Dónde guardás el dato crudo (bronce vs. plata)
- **Bronce:** los JSON en `data/raw/` (`chesscom_<cuenta>_raw.json`), guardados **tal como
  llegan de la API**, sin transformar. Si mañana descubrimos que interpretábamos mal una
  columna, se corrige el parseo y se regenera **sin volver a pegarle a la API**.
- **Plata:** lo que entregamos — `partidas_ajedrez_clean.parquet` + la muestra CSV +
  `data_summary.json`, y la tabla de modelado `partidas_cortes.parquet`.

> Nota: `data/` está en `.gitignore` (no se versiona) **a propósito**: es regenerable
> corriendo el pipeline. Lo que se versiona es el **código que lo produce** y la
> **configuración que define la muestra** (`config/config.yaml` y
> `config/jugadores_seleccionados.yaml`).

---

## 5. La confesión: dónde el dataset se aparta del ideal "tidy"

Un grupo que sabe dónde su dataset se aparta del ideal está mejor parado que uno que
recita la definición de memoria. Tenemos **tres** concesiones honestas para poner sobre la
mesa antes de que las encuentren:

1. **`moves_text` no es atómica (concesión tidy).** Guarda **toda** la secuencia de jugadas
   de la partida en una sola celda (`"1. e4 c5 2. Nf3 ..."`). Es el análogo exacto al
   `player_positions` del dataset canónico de la cátedra: viola "cada celda un valor".
   **Por qué se decidió así:** separar cada jugada en su propia fila explotaría el volumen
   (~78 plies por partida) y la mayoría de esas filas no se usan; separarlas en columnas
   daría cientos de columnas de ancho variable. La concesión es deliberada, y de
   `moves_text` + el PGN crudo derivamos valores atómicos: `cantidad_jugadas` en la tabla
   base, y en la tabla de cortes la posición y los relojes en hasta 25 momentos fijos de la
   partida (una fila por corte, no por jugada) — igual que la cátedra deriva `best_position`.

2. **Fuga de información del ELO hacia `resultado` (limitación de la fuente).** Chess.com
   entrega el rating **posterior** a la partida (ya ajustado por el resultado), no el previo.
   Entonces `WhiteElo`, `BlackElo` y todo lo derivado contienen una fuga hacia el target:
   el signo del cambio de rating coincide con el resultado casi siempre (notebook 02,
   sección 9). **No se parchea a lo bruto:** esas columnas no entran al modelo, y
   `src/rating_history.py` reconstruye el **rating previo** de cada cuenta seleccionada desde
   su propio historial. Del rival no hay historial, así que ese lado queda NaN: se conoce
   el rating previo de al menos un jugador en el 99,7 % de las partidas, pero de los dos
   sólo en 271.

3. **La muestra no es aleatoria (limitación de representatividad).** Los jugadores se sortean
   de las listas públicas de ocho países y de titulados, con **cupos iguales por banda de
   ELO**. Las bandas avanzado, experto y top_mundial usan titulados; elite usa rankings. Las listas de titulados se usan porque en las listas por país
   casi no hay nadie de 1800 o más, y la API no publica listas por rating: queda afuera el
   amateur fuerte sin título, que es el perfil típico de 1800–2200. Entonces la distribución de niveles la fija el diseño (20 por banda) y no la
   población de Chess.com, y solo entran quienes declararon país o título. No hay cuentas
   elegidas a mano ni sesgo de red por oponentes. Las conclusiones valen para el universo de
   jugadores alcanzado por este método, no para "el ajedrez online" en general.

---

## 6. Preguntas dirigidas — banco de respuestas rápidas

La pregunta sobre el scraping le puede caer a quien escribió la transformación. Todos
deberían poder contestar esto:

- **"¿Qué parte del grafo es paralela y qué parte es lineal?"** La **descarga es paralela por
  cuenta**: `descarga_usuario` es una tarea mapeada con `.expand()` (una instancia por usuario,
  hasta 3 en paralelo), porque las cuentas son independientes. Después `consolidar_descarga`
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
- **"¿Y si una cuenta falla al descargar?"** El pipeline **tolera fallos por
  usuario**: cada cuenta es una tarea mapeada aparte, así que si una da 404, no tiene partidas o
  hay error de red, esa instancia devuelve un estado "falló" y **no rompe el fan-out**. Recién
  `consolidar_descarga` corta con error si quedan menos de `min_users_ok: 80` cuentas o menos de
  `min_total_games: 1500` partidas crudas. Una cuenta caída no tira abajo la corrida, pero un
  dataset demasiado chico sí se rechaza.
- **"¿Sale el mismo dataset si lo corrés de nuevo?"** Sí, incluso en otra máquina, por dos
  cosas congeladas. La **lista de jugadores** se seleccionó una vez y está versionada en
  `config/jugadores_seleccionados.yaml`, y la **ventana temporal**
  (`until_month: "2026-08"`) fija qué meses se bajan. Con el crudo presente, la descarga se
  saltea (idempotente). Ver §4.
- **"¿Por qué la lista de jugadores está en `config/` y no en `data/`?"** Porque define la
  muestra, igual que `until_month`: es configuración, no un dato regenerable. Cuando
  estaba en `data/` (ignorada por git) cada integrante generó la suya y llegamos a tener
  documentos con cifras de dos datasets distintos.
- **"¿Por qué la tabla de cortes y no una fila por jugada?"** Porque la pregunta es qué
  tan bien se predice en distintos momentos de la partida, y hasta 25 cortes alcanzan
  para dibujar esa curva y comparar cortes entre sí. Una fila por jugada multiplicaría el
  volumen por ~78 con filas casi idénticas entre sí.
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
