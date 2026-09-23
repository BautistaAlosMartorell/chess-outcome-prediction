# Guía de defensa — Entrega 2 (Ajedrez online, Chess.com)

> **La pregunta de fondo de esta entrega es una sola:**
> ¿sabés qué tiene adentro tu dataset, y podés defender con un número cada decisión
> que tomaste sobre él? Todo lo que salga de acá — qué columnas entran, cuál es el
> objetivo, qué hay que transformar — es la materia prima de la Entrega 3.

Fuente de los números: `data/processed/partidas_ajedrez_clean.parquet` (corrida del
22-23/09/2026 con la selección por bandas de `listar_jugadores`, 100 jugadores y
76.803 partidas) y `notebooks/02_eda_hipotesis.ipynb`, ejecutado de punta a punta con
kernel limpio. Todos los números de este documento salen de una celda ejecutada de ese
notebook — no hay ningún valor puesto a mano.

**Metodología:** las cuatro hipótesis usan las tres plantillas de la cátedra
(comparación / asociación / composición) con los cortes y el semáforo de la cátedra
(`CORTES` + `semaforo()`), no cortes propios del grupo. Ver la sección 4 del notebook.

**Fecha de la entrega: miércoles 23/09/2026**, 20 minutos privados con el docente.

---

## 0. Antes de entrar al aula (checklist físico)

- [x] **Notebook de EDA ejecutado de punta a punta**, con salidas guardadas:
      `notebooks/02_eda_hipotesis.ipynb` (`jupyter nbconvert --to notebook --execute
      --inplace`, sin errores).
- [x] Los gráficos de las cuatro fichas de hipótesis y de sus movimientos generados a
      partir de ese notebook.
- [ ] Este documento impreso o abierto en una pestaña aparte, para no tener que
      recalcular nada en vivo.
- [ ] Airflow **no** hace falta levantarlo para esta entrega (a menos que el docente
      pregunte por el pipeline de la Entrega 1) — el dataset ya existe en
      `data/processed/`.

> Antes de entrar, abrir el notebook ya ejecutado y esta guía en pestañas separadas. No
> hace falta recalcular nada durante los 20 minutos.

---

## 1. Qué cambió (min 0–2) — dos oraciones

**Del pipeline:** la lista de jugadores dejó de ser manual. `listar_jugadores` sortea
candidatos de las listas públicas de la PubAPI (titulados FM/CM/NM para `avanzado`,
GM/IM para `experto` y `top_mundial`, jugadores de ocho países para `principiante` e
`intermedio`), los valida y llena `target_per_band: 20` en cada una de las 5 bandas, y
congela la lista en `data/raw/seleccion/jugadores_seleccionados.yaml`. Esta corrida
seleccionó **100 jugadores, 20 por banda**, y produjo **76.803 partidas** finales sobre
**77.229** descargadas (99,45 % de retención, 0 nulos reales — sección 2). El detalle
está en `criterio-seleccion-jugadores.md`.

**De la pregunta:** no cambió. Sigue siendo qué combinación de ELO, apertura, modalidad
de ritmo y color predice `resultado` (clasificación) y `cantidad_jugadas` (regresión);
esta entrega agrega qué predictores sobreviven al chequeo de fuga (sección 6).

---

## 2. El perfil del dataset (min 2–7) — con números

Comando base:

```python
import pandas as pd
df = pd.read_parquet("data/processed/partidas_ajedrez_clean.parquet")
```

| Qué | Cómo se verificó | Resultado |
|---|---|---|
| **Tamaño** | `df.shape` | `(76803, 25)` — 76.803 partidas, 25 columnas |
| **Qué es una fila** | — | Una partida individual de ajedrez rated (bullet/blitz/rapid) |
| **Tipos** | `df.dtypes.value_counts()` | Mezcla real: texto (`GameUrl`, `White`, `Black`, `ECO`, `Opening`, `moves_text`, `TimeControl`), enteros (`WhiteElo`, `BlackElo`, `tiempo_base_seg`, `cantidad_jugadas`), categóricas (`resultado`, `TimeClass`, `Termination`, `nivel_promedio`, `familia_apertura`, `Event`, `Variant`), un `datetime64` (`Date`), un `bool` (`Rated`) más `es_sorpresa` como `int8`, y un `float`/`Float64` (`incremento_seg`, por el control `10+0.1`). Ninguna numérica quedó atrapada como texto. |
| **Nulos por columna** | `df.isna().mean().sort_values(ascending=False)` | **0,0 en las 25 columnas.** Detalle de qué se descartó y por qué en la sección 3 de abajo — no es que la fuente nunca falle, es que el pipeline descarta antes. |
| **Columnas sin información** | `df.columns[df.nunique() <= 1]` | `Event`, `Variant`, `Rated` — constantes después del filtro (`Live Chess`, `Standard`, `True`). Se van del modelo. |
| **Duplicados de la clave** | `df["GameUrl"].duplicated().sum()` | `0` (`df["GameUrl"].is_unique == True`) |
| **Distribución del objetivo** | `df["resultado"].value_counts(normalize=True)` | Gana Blancas **48,8 %** · Gana Negras **45,1 %** · Empate **6,2 %** |
| **Asimetría de las numéricas** | `df.select_dtypes("number").skew().sort_values()` | Ver tabla abajo |

### La distribución del objetivo (el número que más importa)

Ninguna clase se come todo (no hay un 92 % como advierte la consigna), pero **Empate
sigue siendo claramente minoritaria: 6,18 %**. Consecuencia directa para la Entrega 3: si
se mide sólo *accuracy* global, un modelo que nunca predice empate puede parecer bueno
sin serlo. Hay que reportar métricas por clase (precision/recall/F1 de Empate en
particular) o considerar balanceo. `cantidad_jugadas` tiene media 74,3 y mediana 69
plies (rango 5–375, percentil 95 en 136).

### Asimetría — cuáles tienen cola larga

| Columna | Skew | Lectura |
|---|---:|---|
| `incremento_seg` | **6,03** | Muy sesgada a la derecha: casi todo el volumen en controles frecuentes, con una cola larga de incrementos poco comunes. Candidata a discretizar o tratar junto con `tiempo_base_seg` en vez de como continua pura. |
| `tiempo_base_seg` | **4,09** | Sesgada a la derecha por la misma razón: pocos controles concentran mucho volumen (bullet/blitz dominan sobre rapid). Candidata a escala logarítmica si entra como continua. |
| `es_sorpresa` | 1,25 | Es un indicador binario (0/1) con 23,49 % de unos: el skew alto es esperable en una binaria minoritaria, no señal de outliers. Además **es fuga** — ver sección 6.2. |
| `cantidad_jugadas` | 0,73 | Sesgo leve a la derecha (media 74,3, mediana 69, máximo 375): hay partidas largas que estiran la cola, pero no es extremo. |
| `diferencia_elo` | −0,31 | Prácticamente simétrica. |
| `WhiteElo` / `BlackElo` / `elo_promedio` | −0,58 | Sesgo leve a la izquierda. Los cupos iguales por banda reparten el ELO de forma pareja: la distribución es ancha en vez de amontonarse arriba. |

### `nivel_promedio` — la mejora del selector por bandas

`df["nivel_promedio"].value_counts(normalize=True)`: `top_mundial` 20,72 % ·
`intermedio` 20,53 % · `principiante` 20,05 % · `avanzado` 19,48 % · `experto` 19,22 %.
Las cinco bandas quedan dentro de un rango de 1,5 puntos porcentuales.

**Ojo con cómo se defiende esto:** el equilibrio es consecuencia del diseño del muestreo
(20 jugadores por banda), no un dato sobre cómo se reparten los ratings en Chess.com.
Sirve para que el modelado vea todos los niveles; no habilita a decir nada sobre la
población general.

### La anomalía del límite mensual UTC

`until_month: "2026-08"` limita el archivo mensual consultado, pero Chess.com incluyó en
sus archivos de agosto **99 partidas (0,13 % del dataset) fechadas el 1 de septiembre
UTC** (59 rapid, 38 blitz, 2 bullet). Se investigó y no es un error de parseo: es el
límite horario del archivo mensual. Se conservan porque son casos reales trazables.

---

## 3. Nulos: reales vs. estructurales, y qué se descartó (min 7–9)

"0 nulos" es el resultado de un filtro, no de una fuente perfecta. De las **77.229**
partidas descargadas, **426** (0,55 %) no llegaron al Parquet final:

| Motivo | Tipo | Filas | % del crudo |
|---|---|---:|---:|
| Duplicado entre usuarios (GameUrl repetido) | Estructural / fuera del universo | 6 | 0,01 % |
| Sin resultado (partida abortada o en curso) | Faltante real | 0 | 0,00 % |
| Sin ELO válido | Faltante real | 0 | 0,00 % |
| Fecha inválida | Faltante real | 0 | 0,00 % |
| Variante no estándar | Estructural / fuera del universo | 0 | 0,00 % |
| Modalidad fuera de alcance | Estructural / fuera del universo | 0 | 0,00 % |
| No rated | Estructural / fuera del universo | 0 | 0,00 % |
| Menos de 5 medio-movimientos | Estructural / fuera del universo | 420 | 0,54 % |

En esta corrida los **tres motivos de faltante real dieron 0**: no es que Chess.com
nunca falle en informar resultado/ELO/fecha, es que en esta muestra concreta no ocurrió.
Los dos motivos que sí actuaron son estructurales (duplicado entre cuentas y partidas
demasiado cortas para ser "jugadas"). Tampoco hay nulos disfrazados: `familia_apertura =
"Desconocida"` y `Termination = "otro"` dan **0 filas (0 %)** cada uno.

---

## 4. Rango de fechas 2013–2026 (min 9–10)

El dataset arranca en 2013. `src/download_data.py::download_user_games` recorre los
archivos mensuales de cada jugador del más reciente al más antiguo hasta reunir 1.000
partidas elegibles; un jugador con poca actividad rated tiene que remontarse años atrás
para llegar a ese número. Los 100 jugadores aportan entre 16 y 1.001 partidas cada uno
(media 768, mediana 994). Los 10 jugadores con la partida más vieja mezclan niveles
(`intermedio`, `avanzado`, `experto`, `top_mundial`, ninguno `principiante`): confirma
que las partidas viejas se explican por **actividad baja de la cuenta**, no por una
banda de ELO — varias son cuentas tituladas (FM/IM/GM) que juegan menos online que un
aficionado activo.

**Implicancia para la Entrega 3:** un corte de fecha global mezclaría del lado de test
partidas recientes de cuentas muy activas con la escasa actividad de cuentas inactivas.
La partición temporal debe verificarse **por jugador**, no asumir que un corte global es
neutral entre cuentas.

---

## 5. Las cuatro fichas de hipótesis (min 10–16)

El docente elige dos de las cuatro y hay que recorrerlas enteras: afirmación → qué
esperaba ver → medida y gráfico → resultado con zona → movimiento (si hizo falta) → qué
se hace con eso. Se cubre una pregunta de **responder** (H1, H3 — dominio) y una de
**predecir** (H2, H4 — decide sobre una columna del modelo). De las cuatro, sólo H3 se
confirma (y sólo en parte): H2 y H4 quedan **refutadas** y H1 queda **inconclusa** — lejos
de "cuatro confirmadas".

### H1 — Diferencia de ELO y resultado (responder / dominio)

| Campo | Contenido |
|---|---|
| **Afirmación** | `diferencia_elo` (blancas − negras) explica el `resultado`: cuando es positiva tiende a ganar blancas, cuando es negativa tiende a ganar negras. |
| **Qué esperaba ver** | Que el promedio de `diferencia_elo` fuera claramente distinto entre partidas ganadas por blancas y por negras. |
| **Medida y gráfico** | Comparación (3 grupos): `eta2(diferencia_elo, resultado)`, con la tabla por bandas y barras apiladas como apoyo. |
| **Resultado (zona)** | **η² = 0,094 — 🟡 amarilla.** La tabla por bandas muestra la transición esperada (9,6 % de victorias blancas con diferencia ≤ −301 hasta 88,5 % con diferencia ≥ 301), pero el número queda lejos del corte verde (0,25). |
| **Movimiento (1 de 2)** | Se compararon dos particiones: por `TimeClass` (0,079 a 0,099 según modalidad, sin diferenciar nada) y por `nivel_promedio` (0,084 en principiante a 0,144 en experto). Se elige `nivel_promedio`, que sí separa el comportamiento; las **cinco bandas** quedan en amarillo. El número que resume el movimiento no es la banda más alta sino el η² controlado por nivel (sumas de cuadrados pooleadas dentro de cada banda): **0,101, también amarilla**. |
| **Decisión** | **Inconclusa.** El efecto sigue en zona amarilla banda por banda y en la versión controlada, y no hay una tercera variable ni un cambio de escala que el gráfico sugiera para un segundo movimiento. Corrigiendo la fuga del rating con el lado reconstruido (sección 6.1), este mismo η² baja a 0,065: parte de la señal observada es artefacto de esa fuga. |

### H2 — Paridad de ELO y duración (predecir)

| Campo | Contenido |
|---|---|
| **Afirmación** | Las partidas con menor `abs_diferencia_elo` (rivales más parejos) se mueven junto con `cantidad_jugadas`. |
| **Qué esperaba ver** | Correlación negativa entre `abs_diferencia_elo` y `cantidad_jugadas`. |
| **Medida y gráfico** | Asociación: Pearson, Spearman y brecha. Gráfico: puntos + mediana por bandas de 50 puntos. |
| **Resultado (zona)** | **Pearson = −0,012 (🔴), Spearman = 0,060 (🔴), brecha = 0,071 (🟡).** Ambas correlaciones rojas — ni siquiera coinciden en signo sobre 76.803 partidas. |
| **Movimiento** | No hace falta: rojo termina la hipótesis. La brecha amarilla es informativa (hay algo de no linealidad) pero irrelevante frente a un efecto lineal y monótono ambos nulos. |
| **Decisión** | **Refutada.** `abs_diferencia_elo` no entra como predictor de `cantidad_jugadas`. |

### H3 — Ritmo y terminación por tiempo (responder / dominio)

| Campo | Contenido |
|---|---|
| **Afirmación** | Bullet está sobrerrepresentado en terminar por tiempo frente a la proporción global; Rapid está subrepresentado. |
| **Qué esperaba ver** | Orden Bullet > Blitz > Rapid, separado de la proporción global. |
| **Medida y gráfico** | Composición: proporción de `Termination == "time"` por `TimeClass` contra la global (25,0 %), con `eta2` como medida de apoyo (la composición no tiene corte propio en `CORTES`). |
| **Resultado (zona)** | Bullet 43,6 % (+18,6 pp), Blitz 24,0 % (−1,0 pp), Rapid 6,8 % (−18,1 pp). **η² = 0,090 — 🟡 amarilla.** |
| **Movimiento (1 de 2)** | Partir por `nivel_promedio`: el orden se sostiene en las 5 bandas sin excepción, pero el efecto se desploma con el nivel: 0,265 (principiante, 🟢) → 0,136 (intermedio, 🟡) → 0,064 (avanzado, 🟡) → 0,020 (experto, 🔴) → 0,025 (top_mundial, 🔴). |
| **Decisión** | **Confirmada en niveles bajos, refutada en niveles altos.** No es una sola decisión para todo el dataset: en `principiante` cruza a verde (se confirma), en `intermedio`/`avanzado` queda en amarillo, y en `experto`/`top_mundial` cae a rojo (se refuta ahí). `Termination` sigue sin poder usarse para predecir pre-partida en ningún nivel (se completa cuando la partida ya terminó). |

### H4 — Familia de apertura y duración (predecir)

| Campo | Contenido |
|---|---|
| **Afirmación** | Las aperturas Cerradas producen partidas más largas que las Semiabiertas. |
| **Qué esperaba ver** | Separación clara de `cantidad_jugadas` entre esos dos grupos específicos. |
| **Medida y gráfico** | Comparación (2 grupos, tal como está escrita la afirmación): `separacion(Cerrada, Semiabierta)`. El `eta2` sobre las 5 familias se deja como dato complementario. Boxplot por familia. |
| **Resultado (zona)** | **separación = 0,087 — 🔴 roja** (Cerrada 76,7 plies vs. Semiabierta 73,8 — la dirección se sostiene, la magnitud no). Complementario: η² sobre 5 familias = 0,008, también roja. La familia más larga es India (81,4 plies) y la más chica (3.676 partidas contra 23.451 de Semiabierta). |
| **Movimiento** | No hace falta: rojo termina la hipótesis. |
| **Decisión** | **Refutada.** `familia_apertura` no entra al baseline — además de conocerse sólo después de jugarse la apertura (sección 6). |

### Resumen

| Hipótesis | Pregunta | Plantilla | Medida | Zona | Decisión |
|---|---|---|---|---|---|
| H1 | Responder | Comparación (3 grupos) | η² = 0,094; controlado por nivel = 0,101 (0,084–0,144 por banda) | 🟡 | Inconclusa |
| H2 | Predecir | Asociación | Pearson −0,012 / Spearman 0,060 | 🔴 | Refutada |
| H3 | Responder | Composición + comparación | η² = 0,090 (0,020–0,265 por nivel) | 🟡 | Confirmada en niveles bajos, refutada en niveles altos |
| H4 | Predecir | Comparación (2 grupos) | separación = 0,087 | 🔴 | Refutada |

---

## 6. Fugas cuantificadas (min 16–18)

### 6.1 · La fuga del rating

El proyecto afirma que Chess.com informa el rating **posterior** a la partida. Se
verificó, no se asumió:

1. **Test directo con los crudos** (100 jugadores seleccionados, ordenados por
   `end_time` dentro de cada `time_class`): el signo del cambio de rating propio
   coincide con el resultado de **esa misma partida** en el **99,91 %** de 71.186
   partidas decisivas. La hipótesis alternativa (coincide con la partida *anterior*)
   sólo da **52,13 %** — indistinguible de azar. **Confirmado sin ambigüedad.**
2. **Tamaño del efecto en el dataset:** entre las 14.487 partidas con
   `|diferencia_elo| <= 10`, ganan blancas 52,91 % cuando `diferencia_elo > 0` contra
   43,95 % cuando `< 0` — brecha de 8,96 puntos porcentuales. Efecto moderado, no
   extremo, pero presente incluso en la banda "pareja".
3. **Reconstrucción parcial:** se reconstruyó el rating previo del lado del jugador
   seleccionado (su rating en su partida anterior del mismo `time_class`), cubriendo el
   99,7 % de las partidas. El η² de H1 baja de **0,093 → 0,065** al usar esa versión (las
   dos siguen en zona amarilla). El lado del rival —cuando no es también uno de los 100
   seleccionados— **no se pudo reconstruir** con los datos descargados: **queda
   inconcluso** eliminar la fuga por completo; haría falta el historial propio de cada
   rival.

**Consecuencia:** `diferencia_elo`, `elo_promedio`, `nivel_promedio` y
`WhiteElo`/`BlackElo`, tal como están en el Parquet hoy, **no existirían al momento de
predecir**. Sólo la versión reconstruida previa a la partida (y sólo del lado seguido)
es defendible.

### 6.2 · `es_sorpresa`: fuga por construcción

`src/feature_engineering.py::FeatureEngineer.add_upset_flag` define `es_sorpresa`
directamente a partir de `resultado` y `diferencia_elo`. Se verificó de forma
determinística: coincide con esa regla en el **100,0000 %** de las 76.803 filas. No es
una asociación fuerte, es una identidad — la respuesta escrita de otra forma. Es el
ejemplo más limpio de fuga del dataset.

---

## 7. La tabla de columnas candidatas (min 18–20)

Chequeo de fuga aplicado a **las 25 columnas del Parquet** más `abs_diferencia_elo`
(derivada en H2, no vive en el Parquet): *¿esta columna existiría en el momento de
predecir, antes de que la partida ocurra?* La columna **Zona** es la del semáforo de la
cátedra contra el objetivo correspondiente; "—" donde no aplica (claves, constantes,
fuga por diseño, objetivos).

| Columna | Qué mide | Zona | Decisión | ¿Existiría al predecir? |
|---|---|---|---|---|
| `GameUrl` | Identificador único de partida | — | Sale — es la clave, no aporta señal | Sí, pero no aporta señal |
| `Date` | Fecha de la partida | — | No entra como predictor crudo; se usa para partición temporal | Sí, sólo para partición |
| `White` / `Black` | Usuario por color | — | Salen del modelo general | Existirían, pero no son las 100 cuentas seleccionadas: 50.326 usuarios distintos aparecen como White/Black |
| `WhiteElo` / `BlackElo` | Rating crudo por color | — | Salen si entran `diferencia_elo` y `elo_promedio` (redundancia) | No, tal como está — es el rating posterior (6.1); sólo la versión reconstruida previa del lado seguido sería válida |
| `Result` | Resultado en formato PGN | — | Sale por fuga | No — es el objetivo en otro formato |
| `resultado` | Objetivo de clasificación | — | Es el objetivo, no un predictor | No aplica |
| `cantidad_jugadas` | Objetivo de regresión (duración) | — | Es el objetivo, no un predictor | No aplica |
| `TimeClass` | Modalidad oficial | 🔴 (η² duración = 0,004) | Entra por la pregunta de investigación, no por el EDA | Sí |
| `TimeControl` | Control de tiempo crudo (texto) | — | Sale — se descompone en `tiempo_base_seg`/`incremento_seg` | Sí, pero redundante una vez parseado |
| `tiempo_base_seg` | Segundos base | 🔴 (r duración = −0,027/−0,041) | Entra por dominio; evaluar aporte incremental | Sí |
| `incremento_seg` | Segundos de incremento | 🔴 (r duración = −0,002/−0,021) | Entra por dominio; evaluar aporte incremental | Sí |
| `ECO` | Código de apertura (alta cardinalidad) | — | Sale del baseline | No — se conoce después de iniciar la partida |
| `Opening` | Nombre de apertura (alta cardinalidad) | — | Sale del baseline | No — se conoce después de iniciar la partida |
| `familia_apertura` | Familia ECO (5 categorías) | 🔴 (separación = 0,087; η² 5 familias = 0,008) | Sale del baseline (H4 refutada) | No — se conoce después de iniciar la partida |
| `Termination` | Motivo de finalización | 🟡 (η² duración = 0,175) | Sale por fuga **temporal**, no por tamaño de efecto — el efecto es el más fuerte de la tabla y aun así se descarta | No — se completa cuando la partida termina |
| `moves_text` | Secuencia completa de jugadas | — | Sale del modelo pre-partida | No — contiene toda la partida |
| `diferencia_elo` | Balance de rating por color | 🟡 (η² resultado = 0,094) | Entra con advertencia; sólo la versión reconstruida es defendible | No, tal como está — hereda el resultado (6.1) |
| `elo_promedio` | Nivel general de la partida | 🟡 (r duración = 0,249/0,257) | Entra con advertencia | No, tal como está — misma fuga que `diferencia_elo` |
| `nivel_promedio` | Banda categórica de `elo_promedio` | — | Mismo problema de fuga, del que se deriva | No, tal como está — hereda la fuga |
| `es_sorpresa` | Indicador de upset | — | **Sale — fuga: se calcula con el resultado de la partida (6.2)** | No — es la respuesta escrita de otra forma |
| `abs_diferencia_elo` (derivada, no en el Parquet) | Diferencia absoluta de ELO | 🔴 (H2: Pearson = −0,012) | No entra — H2 refutada | Se derivaría de `diferencia_elo`; misma fuga si se reconstruyera |
| `Event` / `Variant` / `Rated` | Campos de auditoría | — | Salen — varianza cero tras el filtro del universo | Sí, pero no aportan información |

### Dos escenarios que no deben mezclarse

1. **Baseline pre-partida:** modalidad, control de tiempo y ratings reconstruidos
   previos a la partida (6.1 — la versión posterior no es válida). No usa apertura,
   terminación, jugadas ni resultado PGN.
2. **Experimento post-apertura:** puede incorporar `ECO`, `Opening` o
   `familia_apertura`, pero debe formularse como otra pregunta y compararse contra el
   baseline.

---

## 8. Lo que hay que saber explicar (se pregunta, no se mide)

**Cuál es la variable objetivo y cómo está distribuida.** `resultado` (clasificación:
Gana Blancas 48,8 % / Gana Negras 45,1 % / Empate 6,2 %) y `cantidad_jugadas`
(regresión: media 74,3 plies, mediana 69, rango 5–375). Empate es la clase a vigilar.

**Por qué hay nulos donde hay nulos (y por qué esta vez no hubo faltantes reales).**
0 nulos en las 25 columnas, pero el desglose de la sección 3 muestra que en esta corrida
los tres motivos de "faltante real" (sin resultado, sin ELO, fecha inválida) dieron 0
filas: todo lo descartado (426 partidas) fue estructural (6 duplicadas + 420 demasiado
cortas). El mecanismo de faltante real existe en el pipeline y hay que poder explicarlo
aunque esta muestra no lo haya activado.

**Qué hipótesis salió mal, y qué se hizo con eso.** H2 (partidas parejas duran más) se
refutó de punta a punta: Pearson y Spearman ni coinciden en signo. H1 (diferencia de ELO
explica el resultado) da amarillo y, al controlar por `nivel_promedio`, sigue amarillo en
las cinco bandas y en la versión controlada (0,101): no hay un segundo movimiento que el
gráfico justifique, así que queda **inconclusa** — un resultado amarillo sin movimiento
que lo resuelva no se declara confirmado. H4 (Cerrada más larga que Semiabierta) se
refuta con `separacion` (0,087, roja): la dirección de la afirmación se sostiene pero la
magnitud es chica frente al desvío de cada grupo.

**Qué columna se descartó por fuga, y en qué momento se completa en la realidad.**
`es_sorpresa` es el caso más limpio: coincide al 100,0000 % con una regla derivada de
`resultado` y `diferencia_elo` — es la respuesta en otra forma, se descarta por
construcción, no por tamaño de efecto. `Termination` es el caso donde el tamaño de
efecto es el más grande de toda la tabla (η² = 0,175) y aun así se descarta, porque sólo
existe cuando la partida ya terminó. `familia_apertura`/`ECO`/`Opening` se completan
recién después de jugarse los primeros movimientos.

**Qué quedó inconcluso y qué haría falta para resolverlo.**
1. La reconstrucción del rating previo del lado seguido (sección 6.1) ya baja el η² de
   H1 de 0,093 a 0,065, pero el lado del rival sigue sin reconstruirse porque no está en
   los crudos descargados. Eliminar la fuga por completo requeriría descargar también el
   historial propio de cada rival (que no son necesariamente ninguna de las 100 cuentas
   seleccionadas).
2. La banda `avanzado` (1800–2200) se arma con titulados de nivel bajo (FM, CM, NM),
   porque la PubAPI no publica ninguna lista de jugadores por rating. Resolverlo
   requeriría otra fuente o muestrear por oponentes, que reintroduce sesgo de red.
3. Sección 4: si las partidas viejas se concentran en cuentas de baja actividad (no en
   una banda de ELO), la partición temporal de la Entrega 3 debería verificarse por
   jugador; no se implementó todavía, sólo se dejó como nota (sección 9.4 del notebook).

---

## 9. Lo que nos marcaron en la Entrega 1

Devolución del docente (grupo 5K10-11, Ajedrez online — ELO, apertura y ritmo):

> **"Automatizar la elección de los jugadores y agregar variabilidad."**

| Observación | Estado | Cómo se resolvió |
|---|---|---|
| Automatizar la elección de los jugadores | **Resuelto** | La lista fija de 8 cuentas (`chess_com.usernames`) se reemplazó por la tarea `listar_jugadores` (`src/player_selection.py`, commit `4868218` — "feat(datos): agregar selector reproducible de jugadores"). Ya no depende de ninguna cuenta elegida a mano: sortea candidatos de las listas públicas de la PubAPI (titulados FM/CM/NM, GM/IM, y jugadores por país), los valida contra `min_eligible_games` y llena `target_per_band` por banda de ELO. El resultado queda congelado en `data/raw/seleccion/jugadores_seleccionados.yaml`, así que la selección es reproducible (`random_state: 42`) sin ser manual. |
| Agregar variabilidad | **Resuelto** | La muestra pasó de **8 cuentas fijas concentradas en `top_mundial`** a **100 jugadores, 20 por cada una de las 5 bandas de ELO** (principiante a top_mundial), con las bandas quedando entre 19,2 % y 20,7 % del dataset (sección 2) — antes más de la mitad de las partidas eran `top_mundial` y `principiante` casi no existía. También se amplió el rango temporal observado (2013–2026, sección 4) y la cantidad de partidas (7.204 → 76.803). Lo que **no** varía: la banda `avanzado` sigue armándose con titulados de nivel bajo (FM/CM/NM) porque la PubAPI no publica listas por rating entre 1800–2200 — variabilidad de nivel de juego sí, pero no de "cómo se llega" a esa banda; queda anotado como limitación (sección 8). |

---

## 10. Cómo se aprueba (la vara, para autochequeo)

- [x] El notebook corre entero con kernel limpio y las salidas están guardadas.
- [x] El grupo puede describir el dataset con números, no con adjetivos (sección 2).
- [x] Las cuatro fichas están completas, con los seis campos de la cátedra, y cada una
      termina en una decisión (sección 5).
- [x] La tabla de columnas candidatas cubre las 25 columnas del Parquet y tiene columna
      `Zona` (sección 7).
- [x] Al menos una hipótesis de responder (H1, H3) y una de predecir (H2, H4); al menos
      una refutada o inconclusa (H2 y H4 refutadas, H1 inconclusa — tres de cuatro);
      ninguna hipótesis usa más de dos movimientos (H1 y H3 usan uno cada una).
- [x] La sección 9 (devolución de la Entrega 1) está completa: los dos puntos que marcó
      el docente están resueltos.
- [ ] Las respuestas no vienen de una sola persona — el docente elige **2 de las 4**
      fichas para recorrer en la reunión (no las 4), así que repartir entre las/los 6
      quién explica cada ficha (con margen para ajustar una hipótesis si hace falta,
      avisando al resto) y cada fila de la tabla de columnas antes de entrar. Alguien
      del grupo tiene que llevar abiertos **los dos notebooks**: `01_data_ingestion_verification.ipynb`
      (la corrida del DAG) y `02_eda_hipotesis.ipynb` (este).

---

## 11. Tres formas de perder los 20 minutos (y cómo no caer)

1. **El EDA de checklist.** No mostrar veinte histogramas sin conclusión — cada gráfico
   de la sección 5 responde una ficha concreta, no es un catálogo.
2. **Forzar una confirmación sobre un número amarillo.** H1 se queda en amarillo incluso
   después de controlar por nivel — no hay ningún movimiento adicional que la justifique
   como confirmada, así que la respuesta correcta es "inconclusa", no estirar el dato.
3. **Que hable uno solo.** La pregunta sobre una ficha puede caerle a quien no la armó —
   repartir antes de entrar quién puede explicar cada sección de punta a punta, no sólo
   quién la escribió.
