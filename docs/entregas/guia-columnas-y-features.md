# Guía de columnas y features del dataset de ajedrez

## Propósito del documento

Esta guía explica las 35 columnas de
`data/processed/partidas_ajedrez_clean.parquet`: de dónde sale cada una, qué
transformación recibe, por qué algunas parecen redundantes y para qué sirven en
ingeniería de datos, EDA, modelado y una futura aplicación para usuarios finales.

El objetivo no es afirmar que las 35 columnas deban entrar juntas a un modelo. El
Parquet es una **capa plata**: reúne información limpia, trazable y cómoda para más de
un consumidor. La selección de predictores se hace después, al construir una tabla
**oro** específica para cada problema.

Las implementaciones que materializan estas columnas están en:

- `src/clean_data.py`: extracción del JSON y del PGN, limpieza y primeras derivaciones.
- `src/feature_engineering.py`: features analíticas de rating, modalidad y apertura.
- `config/config.yaml`: bandas de rating y universo de modalidades permitido.

---

## 1. Antes de hablar de features: los roles no son intercambiables

En conversación informal se suele llamar *feature* a cualquier columna. Para modelar
conviene usar un vocabulario más preciso:

| Rol | Qué significa | Ejemplos del proyecto |
|---|---|---|
| **Identificador** | Distingue una observación y permite rastrearla. | `GameUrl` |
| **Campo fuente** | Conserva un valor como lo informó Chess.com o el PGN. | `Result`, `TimeClass`, `ECO` |
| **Variable normalizada** | Representa el mismo dato con nombres y tipos consistentes. | `resultado` |
| **Feature derivada** | Calcula una representación más analizable a partir de otras columnas. | `diferencia_elo`, `elo_promedio` |
| **Segmentación para EDA** | Reduce detalle para comparar grupos comprensibles. | `nivel_promedio`, `familia_apertura` |
| **Target** | Es aquello que se intenta predecir. | `resultado`, `cantidad_jugadas`, eventualmente `es_sorpresa` |
| **Auditoría** | Demuestra qué filtros y condiciones cumplió cada fila. | `Event`, `Variant`, `Rated` |

Una columna puede tener más de un rol. `resultado`, por ejemplo, es una versión
normalizada de `Result` y también es el target principal de clasificación.

La pregunta fundamental antes de entrenar cualquier modelo es:

> ¿Esta información existiría en el momento real en que queremos hacer la predicción?

Si no existiría, o si contiene el target expresado de otra manera, usarla como predictor
produce **fuga de información**. Que una columna permita obtener una métrica excelente
no significa que sea una buena feature.

---

## 2. Qué es el PGN y qué aporta el JSON

La PubAPI entrega cada partida como un objeto JSON. Dentro de ese objeto aparecen dos
clases de información:

1. Campos estructurados de la API, por ejemplo `url`, `rated`, `time_control`,
   `time_class`, `rules`, `white` y `black`.
2. Un string `pgn` con headers entre corchetes y, debajo, el texto completo de las
   jugadas.

Ejemplo reducido:

```json
{
  "url": "https://www.chess.com/game/live/123",
  "rated": true,
  "time_control": "180+2",
  "time_class": "blitz",
  "rules": "chess",
  "white": {"username": "jugador_a", "rating": 1800},
  "black": {"username": "jugador_b", "rating": 1750},
  "pgn": "[Date \"2026.08.20\"]\n[White \"jugador_a\"]\n...\n\n1. e4 c5 2. Nf3 ..."
}
```

Los headers PGN se extraen con una expresión regular y se convierten en un diccionario.
Cuando un dato está disponible en ambas representaciones, el pipeline tiene un orden de
preferencia explícito. Por ejemplo, para `WhiteElo` toma primero el header PGN y usa el
rating estructurado del JSON como respaldo.

El texto de jugadas se conserva porque es la evidencia completa de lo ocurrido y permite
derivar nuevas variables sin volver a descargar. Sin embargo, una secuencia completa en
una celda no es una feature tabular lista para modelar.

### Ejemplo completo de separación

Partiendo de:

```text
[Result "1-0"]
[WhiteElo "1810"]
[BlackElo "1760"]
[ECO "C89"]
[TimeControl "180+2"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 ... 1-0
```

el pipeline produce, entre otras:

```text
Result             = "1-0"
resultado          = "Gana Blancas"
WhiteElo           = 1810
BlackElo           = 1760
diferencia_elo     = 50
elo_promedio       = 1785
nivel_promedio     = "intermedio"
ECO                = "C89"
familia_apertura   = "Abierta"
TimeControl        = "180+2"
tiempo_base_seg    = 180
incremento_seg     = 2
cantidad_jugadas   = cantidad de medio-movimientos del cuerpo PGN
```

Se conserva el dato fuente y, al lado, una representación más cómoda. Esto mejora la
trazabilidad: si una derivación parece incorrecta, puede compararse con el valor original.

---

## 3. Redundancia informacional versus utilidad analítica

Varias columnas representan la misma dimensión. Eso no es automáticamente un error.

### 3.1 Equivalencias exactas

| Campo fuente | Campo normalizado | Qué cambia |
|---|---|---|
| `Result` | `resultado` | Código PGN → etiqueta en español. |

Esta pareja no agrega información matemática. Agrega comodidad semántica y permite
conservar el valor fuente para auditoría.

El alias `modalidad` se eliminó porque sólo cambiaba mayúsculas de `TimeClass`. Para mostrar
`Bullet`, `Blitz` o `Rapid` alcanza con formatear `TimeClass` en la capa de presentación.

### 3.2 Descomposiciones

| Campo compuesto | Columnas derivadas | Qué se gana |
|---|---|---|
| `TimeControl` | `tiempo_base_seg`, `incremento_seg` | Dos cantidades numéricas que pueden resumirse, correlacionarse y modelarse. |
| `WhiteElo`, `BlackElo` | `diferencia_elo`, `elo_promedio` | Se separan el balance del enfrentamiento y el nivel general de la partida. |

Para un modelo lineal no deben incluirse simultáneamente los cuatro campos de rating,
porque existe dependencia matemática exacta:

```text
WhiteElo = elo_promedio + diferencia_elo / 2
BlackElo = elo_promedio - diferencia_elo / 2
```

### 3.3 Agregaciones con pérdida de detalle

| Variable detallada | Variable agregada | Información descartada | Utilidad obtenida |
|---|---|---|---|
| `elo_promedio` | `nivel_promedio` | Rating medio exacto. | Segmentos interpretables. |
| `ECO` | `familia_apertura` | Código específico de apertura. | Cinco grupos con más observaciones. |

Estas derivaciones no crean una dimensión nueva. Cambian la resolución. Son útiles para
EDA y comunicación, pero normalmente se prefiere la versión numérica o detallada en el
modelo, si hay volumen y una estrategia adecuada para manejar cardinalidad.

### 3.4 Cuándo la redundancia sí se vuelve un problema

La redundancia es problemática cuando:

- se presentan 35 columnas como si fueran 35 fuentes independientes de señal;
- se introducen todas las representaciones en el mismo modelo sin justificación;
- se produce multicolinealidad en un modelo lineal;
- una misma dimensión recibe peso varias veces;
- se interpretan como hallazgos independientes resultados que provienen del mismo dato;
- se evalúa una derivación contra el target usando información con fuga.

La decisión correcta no es borrar columnas de la capa plata. Es declarar su linaje y
seleccionar una representación coherente en cada tabla oro.

---

## 4. Diccionario completo: campos extraídos y de auditoría

### `GameUrl`

**Origen.** `game["url"]` del JSON; si falta, se usa el header PGN `Link`.

**Transformación.** No se modifica. Es la clave de deduplicación cuando una partida fue
descargada desde dos cuentas configuradas.

**Para qué sirve.** Identificar una partida, investigar anomalías, abrirla en Chess.com y
garantizar que una fila represente una partida única.

**Modelado.** Debe excluirse: tiene cardinalidad igual al número de filas y no describe el
fenómeno.

### `Event`

**Origen.** Header PGN `Event`.

**Transformación.** Se convierte a categoría.

**Para qué sirve.** Auditoría del universo retenido. Después del filtro vale siempre
`Live Chess`: **no distingue** una partida de emparejamiento automático de una de torneo o
de un desafío directo. Para eso está `TournamentUrl`/`EsTorneo`.

**Modelado.** Se excluye por ser constante.

### `Date`

**Origen.** Header PGN `Date`.

**Transformación.** Se parsea con formato `YYYY.MM.DD`. Una fecha inválida se convierte
en `NaT` y la fila se descarta porque la fecha es un campo crítico.

**Granularidad.** Sólo día, sin hora. En la corrida validada coincide en el 100 % de las
filas con el día UTC de `StartTime`, así que es el **día UTC de inicio** (no el día local
del jugador). No alcanza para ordenar causalmente dos partidas del mismo día: para eso se
usan `StartTime` y `EndTime`.

**Para qué sirve.** Análisis temporal, detección de drift, evolución de la muestra y
separación cronológica entre entrenamiento y prueba.

**Modelado.** No entra automáticamente como fecha cruda. Primero debe existir una hipótesis
temporal. Aunque no sea predictor, debe conservarse para hacer una validación temporal.

**Anomalía conocida.** La corrida validada contiene 56 partidas con
`Date = 2026-09-01` (0,07% del dataset) dentro de archivos mensuales de agosto. El patrón
aparece en varias cuentas y corresponde al límite horario UTC de Chess.com.
`download.until_month: "2026-08"` limita qué archivo mensual se consulta, pero no
garantiza estrictamente que todos sus PGN tengan fecha anterior al 1 de septiembre.

### `White`

**Origen.** Header PGN `White`; como respaldo, `game["white"]["username"]`.

**Transformación.** Se conserva como texto.

**Para qué sirve.** Perfiles por jugador, auditoría de la muestra y análisis de color.

**Modelado.** En un modelo general puede hacer que el algoritmo memorice identidades y
patrones de la red de jugadores muestreada. La corrida validada contiene 53.761 usuarios
distintos, no sólo las 100 cuentas seleccionadas, porque cada partida también incorpora al
oponente real. Sólo debe usarse en un producto explícitamente personalizado y con una
partición que impida que el mismo jugador contamine entrenamiento y evaluación.

### `Black`

**Origen.** Header PGN `Black`; como respaldo, `game["black"]["username"]`.

**Transformación y uso.** Equivalentes a `White`, para el lado negro.

### `Result`

**Origen.** Header PGN `Result`.

**Valores.** `1-0`, `0-1`, `1/2-1/2`.

**Para qué sirve.** Trazabilidad respecto del estándar PGN y validación de la conversión a
`resultado`.

**Modelado.** Es el target escrito en otro formato. No puede usarse como predictor.

### `WhiteElo`

**Origen.** Header PGN `WhiteElo`; como respaldo, `game["white"]["rating"]`.

**Transformación.** Conversión numérica; las filas no convertibles se descartan.

**Para qué sirve.** Nivel informado de blancas, distribución de fuerza, outliers y base de
las features comparativas.

**Limitación.** Chess.com informa el rating posterior al ajuste de esta partida. Contiene
una fuga pequeña pero sistemática hacia `resultado`.

**Modelado.** La versión correcta sería el rating inmediatamente anterior a comenzar la
partida. Hasta resolverlo, todo resultado predictivo que lo use debe declarar la limitación.

### `BlackElo`

**Origen.** Header PGN `BlackElo`; como respaldo, `game["black"]["rating"]`.

**Transformación, utilidad y limitación.** Equivalentes a `WhiteElo`, para negras.

### `Variant`

**Origen.** Se deriva de `game["rules"]`: `chess` se normaliza como `Standard`.

**Para qué sirve.** Hace visible por fila que el pipeline conservó ajedrez estándar.

**Modelado.** Se excluye porque es constante después del filtro.

### `TimeControl`

**Origen.** `game["time_control"]` del JSON; como respaldo, header PGN `TimeControl`.

**Formato.** Base más incremento, por ejemplo `180+2`; también puede venir sólo la base,
por ejemplo `60`.

**Para qué sirve.** Auditoría del control original y análisis de combinaciones concretas.

**Modelado.** Puede usarse como categoría, pero para generalizar a controles nuevos es más
útil separar base e incremento. No conviene incluir `TimeControl`, `tiempo_base_seg` e
`incremento_seg` juntos sin comprobar aporte marginal.

### `TimeClass`

**Origen.** `game["time_class"]` del JSON.

**Valores retenidos.** `bullet`, `blitz`, `rapid`.

**Para qué sirve.** Es la clasificación oficial de Chess.com para agrupar controles en
`bullet`, `blitz` y `rapid`. Se usa directamente en EDA, modelado y visualización.

**Modelado.** Predictor pre-partida candidato. La capitalización de sus etiquetas se resuelve
al presentar un gráfico; no requiere otra columna en el dataset.

### `ECO`

**Origen.** Header PGN `ECO`.

**Formato.** Una letra entre A y E y dos dígitos, por ejemplo `C89`.

**Para qué sirve.** Identificación relativamente precisa de la apertura, análisis de líneas
frecuentes y fuente de `familia_apertura`.

**Modelado.** Sólo está disponible después de que se jugaron los primeros movimientos. No
puede entrar en un modelo estrictamente pre-partida. En un modelo post-apertura tiene 454
categorías observadas, por lo que necesita manejo de categorías raras y validación fuera de
muestra.

### `Opening`

**Origen.** URL `game["eco"]` del JSON; como respaldo, header PGN `ECOUrl`.

**Transformación.** Se toma el último segmento de la URL, se decodifican caracteres, se
elimina la continuación ubicada después de `...` y se reemplazan guiones por espacios.

Ejemplo:

```text
https://www.chess.com/openings/Sicilian-Defense-Delayed-Alapin-Variation-3...Nf6
→ Sicilian Defense Delayed Alapin Variation 3
```

**Para qué sirve.** Es mucho más comprensible para el usuario que `B50` y permite explicar
resultados por apertura concreta.

**Limitación.** Tiene 6.796 valores distintos en 80.145 filas. Muchas etiquetas incluyen
variaciones y números de movimiento, por lo que los grupos pueden ser muy pequeños.

**Modelado.** No se recomienda en un baseline. Una asociación aparente alta puede surgir
por cardinalidad y sobreajuste. Primero habría que normalizar niveles de detalle, agrupar
categorías raras y medir desempeño fuera de muestra.

### `Termination`

**Origen.** Header PGN `Termination`.

**Problema del crudo.** Chess.com embebe el username del ganador, por ejemplo
`"jugador_a won by resignation"`. Sin normalización sería casi un identificador y revelaría
quién ganó.

**Transformación.** Se extrae el motivo final y se normaliza a categorías como
`resignation`, `time`, `checkmate`, `repetition` o `insufficient_material`.

**Para qué sirve.** EDA post-partida, explicación al usuario y análisis de cómo terminan las
partidas según modalidad o nivel.

**Modelado.** No debe predecir `resultado` ni `cantidad_jugadas` antes de la partida: sólo
existe al finalizar y está fuertemente vinculada con ambos targets.

### `Rated`

**Origen.** `game["rated"]` del JSON.

**Para qué sirve.** Evidencia de que cada fila pertenece al universo de partidas que afectan
rating.

**Modelado.** Se excluye porque después del filtro siempre vale `True`.

### `moves_text`

**Origen.** Cuerpo del PGN, una vez retirados los headers.

**Transformación.** Se eliminan comentarios entre llaves —incluidos relojes—, se normalizan
espacios y se retira el resultado ubicado al final.

**Para qué sirve.** Evidencia de la secuencia completa, cálculo de `cantidad_jugadas` y
materia prima para futuras features: capturas, jaques, enroques, promociones, fase de juego
o representación secuencial.

**Limitación tidy.** Contiene una secuencia completa en una celda. Separarla en filas rompería
la unidad actual de una fila por partida; separarla en columnas produciría un ancho variable.

**Modelado.** No es un predictor tabular pre-partida. Alimenta otro problema, la
predicción en vivo por cortes (§8.5): `src/live_features.py` la reproduce jugada a jugada
desde el PGN crudo, porque acá ya no quedan los relojes.

### `TournamentUrl`

**Origen.** Campo `tournament` del objeto de partida del JSON de la PubAPI (por ejemplo
`https://api.chess.com/pub/tournament/<slug>`). El PGN trae lo mismo en el header
`Tournament`. Sólo existe cuando la partida se jugó dentro de un torneo de Chess.com.

**Transformación.** Se copia sin modificar; queda nula cuando la partida no es de torneo.
Se guarda como `string` y no como `category`: tiene un valor por torneo.

**Para qué sirve.** Es la única traza en la fuente del mecanismo por el que se armó la
partida (`Event` vale siempre `Live Chess`). El anexo del notebook 02 mostró que el
emparejamiento automático de Chess.com limita la diferencia a ±200 puntos para jugadores
por debajo de 2500 (bullet/blitz) o 2000 (rapid), y que 3.070 de las 5.080 partidas que
violan ese límite (60,4 %) son de torneo.

**Nulos.** Es la única columna con nulos del Parquet (~92 % de las filas), y son
estructurales: "no es de torneo", no un dato faltante. Están declarados en
`nulos_documentados` del DAG (criterio 5).

**Modelado.** No entra como texto: tiene cardinalidad alta. Su versión útil es `EsTorneo`.

**Alcance.** El PGN trae además un header `Match` en 98 partidas descargadas (matches por
equipos, otro mecanismo sin el límite de ±200). No se extrae todavía; queda como candidato
si hiciera falta distinguirlo.

### `StartTime`

**Origen.** Headers PGN `UTCDate` + `UTCTime`: fecha y hora de **inicio** en UTC.

**Transformación.** Se une y se parsea como `datetime64[UTC]` con formato
`YYYY.MM.DD HH:MM:SS`. Si falta o no parsea queda `NaT` y la partida **se conserva** (a
diferencia de `Date`): ninguno de los dos targets depende de la hora. En la corrida
validada no hay faltantes.

**Para qué sirve.** Ordenar partidas en el tiempo con resolución de segundos: particiones
temporales de entrenamiento/prueba y features históricas que sólo pueden mirar partidas
**terminadas antes de que esta empezara** (`EndTime_previa < StartTime_actual`).

**Modelado.** No entra como predictor crudo. Es la columna de orden y partición.

### `EndTime`

**Origen.** Campo `end_time` del JSON (epoch Unix en segundos).

**Transformación.** Se convierte a `datetime64[UTC]`. Mismo criterio de nulos que
`StartTime`.

**Para qué sirve.** Condición causal de las features históricas y auditoría. El DAG
verifica que `StartTime <= EndTime` en todas las filas.

**Anomalías conocidas.**

- 263 partidas (0,34 %) terminan un día UTC después de `Date`: empezaron antes de la
  medianoche UTC. Es esperado, no un error.
- `EndTime − StartTime` **no es tiempo de reloj**. En 16.188 partidas (21 %, casi todas
  bullet y blitz, dos tercios terminadas por tiempo) supera el máximo que permiten los
  relojes (`2 × tiempo_base_seg + cantidad_jugadas × incremento_seg`), con un exceso
  mediano de 12 s y p99 de 44 s. Es compatible con tiempo que no corre en el reloj
  (antes de las primeras jugadas, compensación de latencia) y con la resolución de un
  segundo de `UTCTime`. No se filtra; si se necesita el tiempo consumido de verdad, está
  en los relojes `%clk` del PGN crudo.

**Modelado.** **Fuga para cualquier predicción antes del final**: la duración total
revela cuánto duró la partida. Sólo se usa como condición temporal, nunca como feature.

---

## 5. Diccionario completo: targets y features derivadas

### `resultado`

**Origen.** Mapeo de `Result`:

```text
1-0       → Gana Blancas
0-1       → Gana Negras
1/2-1/2   → Empate
```

**Para qué sirve.** Target principal de clasificación, balance de clases y presentación
comprensible.

**Modelado.** Va en `y`, nunca en `X`. En la corrida actual: 48,95 % gana blancas, 44,94 %
gana negras y 6,11 % empata. La clase empate necesita métricas que no queden dominadas por
las victorias, por ejemplo evaluación por clase además de accuracy global.

### `tiempo_base_seg`

**Origen.** Parte anterior a `+` en `TimeControl`.

**Ejemplo.** `180+2 → 180`.

**Para qué sirve.** Distribuciones numéricas, comparación con duración y generalización más
allá de las doce cadenas de control de tiempo observadas.

**Modelado.** Predictor pre-partida candidato para resultado y duración.

### `incremento_seg`

**Origen.** Parte posterior a `+` en `TimeControl`; cuando no existe se asigna cero.

**Ejemplo.** `180+2 → 2`; `60 → 0`.

**Para qué sirve.** Diferenciar partidas con igual tiempo base y distinta reposición de
reloj.

**Modelado.** Predictor pre-partida candidato. Debe documentarse como numérico decimal,
porque existe un control `10+0.1`; no siempre es entero.

### `cantidad_jugadas`

**Origen.** Conteo de tokens del cuerpo de `moves_text` que no sean números de jugada,
anotaciones NAG ni marcadores de resultado.

**Unidad real.** **Plies o medio-movimientos**, no rondas completas. Una jugada de blancas
y una de negras cuentan como dos.

**Para qué sirve.** Target de regresión y EDA de longitud ajedrecística.

**Modelado.** Va en `y` al predecir longitud. No debe entrar en un predictor pre-partida de
`resultado`, porque sólo se conoce cuando la partida terminó.

**Mejora de nomenclatura sugerida.** En una futura capa oro conviene exponer:

```text
cantidad_plies
cantidad_movimientos = ceil(cantidad_plies / 2)
```

Además, longitud en movimientos no equivale a duración de reloj. Si el producto quiere
estimar minutos reales, hace falta derivar un target `duracion_real_seg` desde timestamps.

### `diferencia_elo`

**Origen.** `WhiteElo - BlackElo`.

**Interpretación.** Positiva: blancas tienen mayor rating. Negativa: negras tienen mayor
rating. Cero: ratings iguales.

**Para qué sirve.** Balance del emparejamiento, ventaja blanca controlada por fuerza,
probabilidad de sorpresa y predictor principal del resultado.

**Modelado.** Es preferible a introducir ambos ratings por separado cuando interesa el
balance. Hereda la fuga temporal de los ratings posteriores.

**Feature complementaria sugerida.** Para duración y sorpresas puede ser útil
`abs_diferencia_elo`, porque allí interesa cuánto difieren los jugadores, no qué color tiene
la ventaja. No hace falta persistirla: se obtiene con `diferencia_elo.abs()` en ese análisis.

### `elo_promedio`

**Origen.** `(WhiteElo + BlackElo) / 2`.

**Para qué sirve.** Nivel general de la partida. Dos partidas pueden tener diferencia cero
pero enfrentar 900 contra 900 o 2800 contra 2800; no son el mismo contexto.

**Modelado.** Predictor candidato para resultado y duración, conservando el valor continuo.
Hereda la fuga temporal de los ratings posteriores.

### `nivel_promedio`

**Origen.** `pd.cut` sobre `elo_promedio`, usando las bandas de `config/config.yaml`:

```text
principiante   0–1200
intermedio     1200–1800
avanzado       1800–2200
experto        2200–2600
top_mundial    2600–4000
```

**Para qué sirve.** Segmentación comprensible para EDA, dashboards y comunicación no
técnica.

**Limitaciones.** Los cortes son una decisión del proyecto, no un estándar oficial de
Chess.com. La muestra está balanceada entre bandas (17.503 `intermedio`, 17.023
`principiante`, 15.913 `top_mundial`, 15.093 `experto`, 14.613 `avanzado`), pero ese
equilibrio es una decisión de muestreo —20 jugadores por banda— y no la distribución real
de ratings en Chess.com.

**Modelado.** Generalmente se prefiere `elo_promedio`, porque no pierde precisión. La banda
puede probarse como alternativa interpretable, no sumarse automáticamente al continuo.

### `es_sorpresa`

**Origen.** Combina `resultado` y `diferencia_elo`. Vale uno si ganan blancas con diferencia
negativa o si ganan negras con diferencia positiva. Con empate o ratings iguales vale cero.

**Para qué sirve.** KPI atractivo para el usuario, tasa de *upsets* y posible target
secundario.

**Modelado.** Nunca debe usarse para predecir `resultado`, porque fue calculada a partir de
él. Si se modela como target propio, conviene definir explícitamente si se conservan los
empates como `0` o se restringe el problema a partidas decisivas. También hereda el problema
del rating posterior.

`es_sorpresa` no depende de una columna `favorito`: compara directamente el resultado con el
signo de `diferencia_elo`. Por eso el alias redundante pudo eliminarse sin cambiar su lógica.

### `familia_apertura`

**Origen.** Primera letra de `ECO`:

```text
A → Flanco
B → Semiabierta
C → Abierta
D → Cerrada
E → India
otro o ausente → Desconocida
```

**Para qué sirve.** Reducir 457 códigos ECO a cinco grupos principales, obtener tamaños de
grupo razonables y comunicar patrones generales.

**Modelado.** Sólo post-apertura. En la corrida validada su asociación con
`cantidad_jugadas` fue débil (`eta² = 0,007`). Sale del baseline pre-partida y queda como
experimento separado: comparar modelos con y sin apertura fuera de muestra.

### `matchup_apertura`

**Origen.** Los dos primeros plies de `moves_text`: la primera jugada de blancas y la
primera respuesta de negras en notación SAN, unidas con un guion (`e4-e5`, `d4-Nf6`).

**Transformación.** Si la combinación está en la lista congelada de
`config.yaml → matchup_apertura.categorias` queda tal cual; si no, cae en `otra`. Es
categórica con 18 niveles.

**Es una taxonomía nueva definida por el equipo, no el estándar ECO.** La lista son las 17
combinaciones más frecuentes de la corrida del 26/09/2026: juntas cubren el 80,39 % de las
76.803 partidas, la menos frecuente tiene 760 y ninguna baja de 96 dentro de un mismo
`TimeClass`. De las 290 combinaciones observadas, 190 tienen menos de 30 partidas, pero
suman sólo 1.350 (1,76 %): la fragmentación está en la cola y queda en `otra` (19,6 %). La
lista se congela y no se recalcula por corrida, porque si cambiara, la categoría de una
misma partida cambiaría al entrar datos nuevos. Sesgo declarado: se eligió mirando la
frecuencia del dataset completo, no los resultados.

**Por qué no `familia_apertura`.** `familia_apertura` es un único valor por partida, así
que no permite un "blancas vs negras". Además, Chess.com asigna el ECO mirando la línea
completa jugada (mediana de 10 plies, hasta 40), mientras que `matchup_apertura` sólo
necesita los plies 1 y 2. Tampoco sirve el repertorio por jugador: 41.066 de los 50.326
jugadores aparecen una sola vez en la muestra.

**Modelado.** Se conoce en el ply 2. Es feature **en vivo o post-apertura**, nunca
pre-partida.

### `n_previas_matchup`, `historial_suficiente`, `tasa_blancas_hist`, `tasa_tablas_hist`, `tasa_negras_hist`

**Origen.** `src/feature_engineering.py` (`matchup_history`). Para cada partida se toman
las partidas del **mismo `matchup_apertura` y el mismo `TimeClass`** que **terminaron
antes de que esta empezara** (`EndTime_previa < StartTime_actual`, con igualdad excluida).
`n_previas_matchup` es cuántas son, y las tres tasas son la proporción de victorias
blancas, tablas y victorias negras entre ellas.

**Por qué `StartTime`/`EndTime` y no `Date`.** `Date` sólo tiene día. Ordenar por fin de
partida tampoco alcanza: una partida que terminó mientras esta estaba en curso no era
conocida al empezar. El cálculo es vectorizado (`searchsorted` sobre los `EndTime`
ordenados) y está verificado contra un cálculo por fuerza bruta en 300 partidas al azar
(0 diferencias). Los tests cubren partidas solapadas, empates exactos de horario,
invariancia al orden de las filas y que agregar partidas futuras no cambia ninguna
feature pasada.

**Umbral y faltantes.** Con menos de 30 previas
(`matchup_apertura.min_partidas_previas`), `historial_suficiente = False` y las tres tasas
quedan **NaN**. No se imputan: es missingness real, porque no había historia que mirar. En
la corrida validada son 1.620 partidas (2,1 %), exactamente las 30 primeras de cada uno de
los 54 grupos (18 matchups × 3 ritmos). Se concentran en los años viejos de la muestra
(316 en 2014, 267 en 2016, ninguna en 2026) y afectan más a rapid (2,96 %) y bullet
(2,70 %) que a blitz (1,40 %). Están declaradas en `nulos_documentados` del DAG, que
además verifica que las tasas sólo falten cuando `historial_suficiente = False`.

**Variante sin NaN.** Para modelos que no aceptan faltantes,
`matchup_history(df, min_prev, shrink_m=m)` devuelve la tasa contraída
`(k + m · p_previa) / (n + m)`, donde `p_previa` es la tasa del mismo ritmo, también sólo
con partidas previas. No se persiste en el Parquet: se calcula en el notebook de modelado
y siempre va acompañada de `historial_suficiente`.

**Qué representa y qué no.** Es la tasa **de la muestra** (100 jugadores seleccionados y
sus rivales), no la de Chess.com. Además arrastra el drift temporal de la muestra. La
señal esperada es débil: la victoria blanca varía poco entre familias de apertura (entre
48,4 % y 49,8 %). Entra a la Entrega 3 como experimento con ablación (modelo con y sin),
no como feature garantizada.

### `EsTorneo`

**Origen.** Derivada: `TournamentUrl.notna()`.

**Transformación.** Booleana. Se deriva en `parse_timestamps` y no se lee aparte del crudo,
para que no pueda contradecir a `TournamentUrl`; el DAG lo verifica.

**Para qué sirve.** Separar las partidas de torneo del resto al estudiar el límite de ±200
del emparejamiento automático, y como candidata a feature: el mecanismo de emparejamiento
cambia la distribución de `diferencia_elo`. 6.261 partidas (8,2 %) en la corrida validada.

**Modelado.** Se conoce antes de empezar la partida, así que no tiene fuga. Candidata
pre-partida para la Entrega 3.

### Columnas derivadas descartadas

`modalidad` y `favorito` existieron en una versión anterior de la capa plata y se retiraron
por redundancia:

- `modalidad` era una copia de `TimeClass` con capitalización distinta;
- `favorito` era sólo el signo de `diferencia_elo` convertido en una etiqueta.

Cuando una visualización necesite esas etiquetas puede derivarlas localmente. No se pierde
información y se evita presentar alias triviales como features independientes.

---

## 6. El color de piezas está implícito

La pregunta del proyecto menciona el color, pero no existe una columna variable llamada
`color`. En una tabla con una fila por partida siempre hay un jugador blanco y uno negro.
El color ya aparece en la estructura:

- `White` y `Black` asignan los participantes a cada color;
- `WhiteElo` y `BlackElo` conservan esa orientación;
- `diferencia_elo` está orientada como blancas menos negras;
- `resultado` distingue victoria blanca, victoria negra y empate.

En un modelo de resultado por lado del tablero, la ventaja de blancas puede estimarse como
la probabilidad de victoria blanca cuando la diferencia de rating está cerca de cero. Una
columna constante `color = Blancas` no aportaría información.

Si el producto futuro quiere contestar “¿qué probabilidad tiene **este jugador** de ganar?”,
la unidad analítica debería cambiar a jugador-partida y podrían derivarse:

```text
elo_jugador
elo_oponente
diferencia_elo_jugador
juega_con_blancas
resultado_jugador
```

Eso produciría dos filas por partida. La partición de entrenamiento y prueba tendría que
hacerse agrupando por `GameUrl`, para impedir que dos perspectivas de la misma partida
queden en conjuntos diferentes.

---

## 7. Utilidad según el consumidor

### Ingeniería de datos y auditoría

Conservar:

```text
GameUrl, Event, Date, White, Black, Result,
WhiteElo, BlackElo, Variant, TimeControl,
TimeClass, ECO, Opening, Termination, Rated, moves_text,
TournamentUrl, StartTime, EndTime
```

Permiten reconstruir decisiones, investigar anomalías y verificar derivaciones.

### EDA y comunicación

Priorizar:

```text
resultado, cantidad_jugadas,
diferencia_elo, elo_promedio,
nivel_promedio, TimeClass, es_sorpresa,
ECO, Opening, familia_apertura,
Termination, Date
```

Las versiones agregadas son especialmente útiles para gráficos; las detalladas permiten
profundizar cuando los tamaños de grupo son suficientes.

### Científicos de datos

Necesitan también los campos de auditoría, pero construyen matrices `X`/`y` separadas y
controlan:

- disponibilidad temporal;
- fuga de información;
- cardinalidad;
- clases y segmentos minoritarios;
- redundancia respecto del target;
- desempeño fuera de muestra;
- estabilidad temporal y por jugador.

### Usuario final

Un jugador o entrenador puede recibir valor de:

- probabilidad de victoria, derrota y empate;
- efecto estimado de la diferencia de rating;
- comparación entre modalidades;
- longitud esperada en movimientos;
- tasa de sorpresas;
- aperturas y familias más frecuentes;
- formas de terminación;
- enlaces a partidas representativas.

Pero deben distinguirse dos productos:

1. **Predicción pre-partida:** sólo usa información disponible antes de comenzar.
2. **Análisis post-partida:** puede usar apertura, movimientos, resultado y terminación para
   explicar lo ocurrido.

---

## 8. Tablas oro recomendadas

### 8.1 Resultado pre-partida

```text
Target
  resultado

Predictores candidatos
  diferencia_elo_pre
  elo_promedio_pre
  tiempo_base_seg
  incremento_seg
  TimeClass

Partición y auditoría, no predictores automáticos
  GameUrl
  Date
```

El sufijo `_pre` es importante: los ratings actuales son posteriores y deben reconstruirse
o mantenerse con una advertencia explícita.

### 8.2 Resultado post-apertura

```text
Todo el escenario pre-partida
+ familia_apertura
o ECO agrupado
o matchup_apertura + tasa_*_hist + historial_suficiente (se conocen en el ply 2)
```

La comparación entre ambos escenarios mide cuánta información marginal aporta conocer la
apertura después de las primeras jugadas.

### 8.3 Longitud pre-partida

```text
Target
  cantidad_plies

Predictores candidatos
  abs_diferencia_elo_pre
  elo_promedio_pre
  tiempo_base_seg
  incremento_seg
  TimeClass
```

Puede construirse un segundo escenario post-apertura agregando apertura o familia.

### 8.4 Dataset descriptivo para una aplicación

```text
GameUrl, Date, White, Black,
resultado, cantidad_jugadas,
TimeClass, ECO, Opening, familia_apertura,
Termination, es_sorpresa
```

Esta tabla sirve para dashboards, explicaciones y navegación; no representa una matriz de
predictores pre-partida.

---

### 8.5 Resultado en vivo por corte

Tabla derivada `data/processed/partidas_cortes.parquet`, **no** una columna más del tidy:
una fila por `(GameUrl, corte_ply)`, con cortes en `config.yaml → live_prediction.cortes_ply`
(10, 20, 30, 40 y 60 plies). Una partida aporta una fila por cada corte estrictamente menor
que su `cantidad_jugadas`: 336.001 filas de 76.331 partidas en la corrida validada. El
contexto de la partida se une desde el tidy por `GameUrl` (muchos a uno, con assert de
conteo), así que no se duplica en disco.

```text
Clave
  GameUrl + corte_ply

Targets
  resultado            (el final de la partida)
  plies_restantes      (cantidad_jugadas − corte_ply)

Features del corte (sólo miran jugadas <= corte_ply)
  turno_blancas, en_jaque, movilidad, promociones
  material_blancas, material_negras, balance_material, material_no_peon_frac
  jaques_*, capturas_*, enroco_*, derechos_enroque_*
  reloj_*_seg, reloj_frac_*, diferencia_reloj_seg, gasto_reciente_*_seg

Contexto que se une desde el tidy
  TimeClass, tiempo_base_seg, incremento_seg, EsTorneo
  elo_blancas_previo, elo_negras_previo   (src/rating_history.py; NaN del lado sin historial)
  matchup_apertura, tasa_*_hist, historial_suficiente
  StartTime / EndTime                      (sólo para la partición temporal)

Prohibidas (fuga)
  WhiteElo, BlackElo, diferencia_elo, elo_promedio, nivel_promedio  (rating posterior)
  Termination, cantidad_jugadas, EndTime como feature, es_sorpresa
  ECO, Opening, familia_apertura    (Chess.com asigna el ECO mirando la línea completa)
  accuracies del JSON crudo         (análisis posterior a la partida)
```

Anomalías conocidas: `reloj_frac_*` supera 1 en el 5,45 % de las filas (acumulación de
incrementos) y `gasto_reciente_*` es negativo en 4 filas (se agregó tiempo en partidas sin
incremento). Se conservan. Para comparar entre cortes hay que usar la población común
(partidas que llegan al último corte): cada corte describe partidas de distinta duración.
Los resultados están en `notebooks/03_prediccion_en_vivo.ipynb`.

## 9. Diagnóstico cuantitativo de las 80.145 partidas

Estos números son un **screening inicial**, no la selección definitiva de features. Siguen
la idea de que el número sostiene una decisión y el gráfico explica su forma.

| Relación explorada | Medida | Resultado inicial | Lectura prudente |
|---|---:|---:|---|
| `diferencia_elo` y `resultado` | V de Cramér sobre bandas de diferencia | 0,234 | Zona amarilla: señal relevante, no suficiente por sí sola. |
| `elo_promedio` y `cantidad_jugadas` | Pearson / Spearman | 0,230 / 0,225 | Asociación positiva modesta y consistente. |
| `TimeClass` y `cantidad_jugadas` | η² | 0,009 | Rojo según el semáforo de la materia. |
| `TimeControl` y `cantidad_jugadas` | η² | 0,029 | Rojo; el control exacto explica poca variación global. |
| `familia_apertura` y `cantidad_jugadas` | η² | 0,007 | Rojo; las familias explican muy poca variación global. |
| `Termination` y `cantidad_jugadas` | η² | 0,193 | Asociación fuerte pero inutilizable pre-partida por fuga temporal. |

Promedios de longitud observados:

| Modalidad | Partidas | Media de plies | Mediana de plies |
|---|---:|---:|---:|
| Bullet | 21.387 | 74,90 | 71 |
| Blitz | 45.403 | 77,34 | 73 |
| Rapid | 13.355 | 68,58 | 64 |

Que Blitz tenga una media mayor no significa que la modalidad cause partidas más largas.
Las categorías están mezcladas con diferencias de jugador, rating, fecha y selección de
la muestra, y el tamaño de efecto global queda en zona roja.

Promedios de longitud por familia:

| Familia | Partidas | Media de plies | Mediana de plies |
|---|---:|---:|---:|
| Flanco | 21.506 | 77,40 | 74 |
| Semiabierta | 25.359 | 75,19 | 71 |
| Abierta | 19.119 | 70,80 | 66 |
| Cerrada | 10.624 | 76,83 | 72 |
| India | 3.537 | 81,45 | 76 |

Las diferencias visuales o de medias deben acompañarse con tamaño de efecto y control de
posibles terceras variables antes de transformarse en una conclusión.

---

## 10. Hipótesis sugeridas para Entrega 2

Las hipótesis deben escribirse antes de calcular sus medidas definitivas.

### H1 — Diferencia de rating y resultado

**Afirmación.** A mayor diferencia de rating a favor de blancas, mayor proporción de
victorias blancas; a menor diferencia, mayor proporción de victorias negras.

**Qué esperamos ver.** Una transición ordenada de resultados al recorrer bandas de
`diferencia_elo`.

**Medida y gráfico.** Proporciones por banda; gráfico de barras apiladas. Como apoyo,
comparar la distribución de la diferencia entre resultados.

**Posibles controles justificados.** Nivel promedio y `TimeClass`.

### H2 — Partidas parejas y longitud

**Afirmación.** Las partidas con menor `abs_diferencia_elo` tienden a durar más.

**Qué esperamos ver.** Asociación negativa entre brecha absoluta y cantidad de plies.

**Medida y gráfico.** Pearson y Spearman; scatter suavizado o boxplots por bandas.

### H3 — Ritmo y forma de terminación

**Afirmación.** Las partidas Bullet terminan por tiempo en mayor proporción que Blitz y
Rapid.

**Qué esperamos ver.** Mayor proporción de `Termination = time` en Bullet.

**Medida y gráfico.** Composición porcentual y barras normalizadas.

### H4 — Familia de apertura y longitud

**Afirmación.** Las aperturas cerradas producen partidas más largas que las semiabiertas.

**Qué esperamos ver.** Separación positiva de `cantidad_jugadas` entre ambos grupos.

**Medida y gráfico.** Separación estandarizada y boxplot. Si queda amarilla, controlar nivel
promedio o `TimeClass`, con un máximo de dos movimientos analíticos.

### H5 — Apertura como información marginal

**Afirmación.** Agregar apertura a las variables pre-partida mejora la predicción de
resultado o longitud fuera de muestra.

**Qué esperamos ver.** Mejora consistente de métricas entre un modelo base y el mismo modelo
con apertura.

**Decisión.** La apertura entra sólo si mejora validación fuera de muestra y el escenario se
presenta explícitamente como post-apertura.

---

## 11. Qué se conserva y qué se excluye

### En la capa plata

Se conservan las 35 columnas. La coexistencia de dato crudo, dato normalizado y agregación
es deliberada: mejora trazabilidad, EDA y comunicación.

### En una matriz de modelado

Se excluyen por identidad, constancia, fuga o rol de target:

```text
GameUrl
Event
Variant
Rated
Result
moves_text
Termination
TournamentUrl        (se usa EsTorneo)
StartTime, EndTime   (orden y partición; EndTime es fuga)
resultado, cuando no sea el target actual
cantidad_jugadas, cuando no sea el target actual
es_sorpresa, cuando no sea el target actual
```

Se elige una representación por grupo redundante:

```text
TimeControl o tiempo_base_seg + incremento_seg
WhiteElo + BlackElo o diferencia_elo + elo_promedio
elo_promedio o nivel_promedio
ECO, Opening o familia_apertura según granularidad y escenario
```

No es una regla automática que siempre deba ganar la misma representación. El modelo, la
interpretabilidad requerida y la evaluación fuera de muestra determinan la selección.

---

## 12. Cómo defender esta decisión oralmente

Una respuesta breve y rigurosa sería:

> “Nuestro Parquet es una capa plata, no la matriz final de entrenamiento. Conservamos los
> campos originales del JSON y del PGN para trazabilidad, y agregamos representaciones
> normalizadas, numéricas o agrupadas para facilitar EDA y comunicación. Sabemos que pares
> como `Result`/`resultado` y `elo_promedio`/`nivel_promedio` comparten información. No los presentamos como dimensiones
> independientes ni los introducimos automáticamente juntos a un modelo. En la capa oro
> elegimos la representación apropiada para cada target, verificamos fuga temporal y
> comparamos aporte fuera de muestra.”

Si preguntan por qué no se borraron las columnas redundantes:

> “Porque la redundancia en una tabla analítica puede ser deliberada: una columna conserva
> el dato fuente y otra facilita el consumo. El problema sería duplicarlas sin control en la
> matriz de modelado, no conservarlas documentadas en la capa plata.”

Si preguntan qué significa “generar variables útiles”:

> “Útil no significa necesariamente información matemáticamente nueva. También puede
> significar convertir un string compuesto en números analizables, traducir un código a un
> target consistente o agrupar alta cardinalidad para obtener segmentos interpretables. La
> utilidad final se valida respecto de una pregunta y un target.”

---

## 13. Conclusión

El dataset no contiene 35 predictores independientes. Contiene 35 columnas con roles
distintos y un linaje verificable:

```text
JSON + PGN
    ↓
campos fuente y de auditoría
    ↓
normalización y separación de campos compuestos
    ↓
features continuas y segmentaciones para EDA
    ↓
tablas oro específicas para cada target
```

La Entrega 1 necesita demostrar que el pipeline produce datos limpios, documentados,
reproducibles y suficientemente ricos. La Entrega 2 determina mediante hipótesis qué
relaciones tienen magnitud relevante. La Entrega 3 selecciona predictores y compara modelos
sin fuga. Conservar las distintas representaciones en plata es compatible con las tres
etapas, siempre que la redundancia sea explícita y la selección se haga antes de entrenar.
