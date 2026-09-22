# Guía de defensa — Entrega 2 (Ajedrez online, Chess.com)

> **La pregunta de fondo de esta entrega es una sola:**
> ¿sabés qué tiene adentro tu dataset, y podés defender con un número cada decisión
> que tomaste sobre él? Todo lo que salga de acá — qué columnas entran, cuál es el
> objetivo, qué hay que transformar — es la materia prima de la Entrega 3.

Fuente de los números: `data/processed/partidas_ajedrez_clean.parquet` (corrida del
22/09/2026 con la selección por bandas de `listar_jugadores`, 100 jugadores y 80.145
partidas) y `docs/entregas/guia-columnas-y-features.md` (diccionario de columnas y primer
diagnóstico cuantitativo). Todos los números de este documento se recalcularon en vivo
sobre ese Parquet.

**Fecha de la entrega: miércoles 23/09/2026**, 20 minutos privados con el docente.

---

## 0. Antes de entrar al aula (checklist físico)

- [x] **Notebook de EDA ejecutado de punta a punta**, con salidas guardadas:
      `notebooks/02_eda_hipotesis.ipynb`.
- [x] Los cuatro gráficos de las fichas de hipótesis (sección 3) generados a partir de
      ese notebook.
- [ ] Este documento impreso o abierto en una pestaña aparte, para no tener que
      recalcular nada en vivo.
- [ ] Airflow **no** hace falta levantarlo para esta entrega (a menos que el docente
      pregunte por el pipeline de la Entrega 1) — el dataset ya existe en
      `data/processed/`.

> Antes de entrar, abrir el notebook ya ejecutado y esta guía en pestañas separadas. No
> hace falta recalcular nada durante los 20 minutos.

---

## 1. Qué cambió (min 0–2) — dos oraciones

1. **Del pipeline:** la tarea `listar_jugadores` dejó de leer una lista fija de 8 cuentas
   (`chess_com.usernames`) y ahora arma la muestra ella sola por banda de ELO. En la primera
   corrida sortea candidatos de listas públicas de la PubAPI —titulados FM/CM/NM para
   `avanzado`, GM/IM para `experto` y `top_mundial`, y jugadores de ocho países para
   `principiante` e `intermedio`—, los valida y llena `target_per_band: 20` en cada una de
   las 5 bandas. Después **congela esa lista** en
   `data/raw/seleccion/jugadores_seleccionados.yaml`, así que las corridas siguientes
   descargan exactamente los mismos jugadores. La ventana temporal sigue congelada
   (`until_month: "2026-08"`). En la corrida del 22/09/2026 se seleccionaron **100
   jugadores, 20 en cada banda** (status `complete` en el manifiesto), y salieron **80.145
   partidas** finales sobre 80.521 descargadas (99,53 % de retención, 0 nulos).
   Si el docente pregunta de dónde salen los jugadores: no hay ninguna cuenta elegida a
   mano; el detalle y las mediciones que justifican cada lista están en
   `criterio-seleccion-jugadores.md`.
2. **De la pregunta:** no cambió. Sigue siendo qué combinación de ELO, apertura,
   modalidad de ritmo y color predice `resultado` (clasificación) y `cantidad_jugadas`
   (regresión). Lo que sí se precisó en esta entrega es **qué predictores sobreviven al
   chequeo de fuga** (sección 4).

---

## 2. El perfil del dataset (min 2–7) — con números

Comando base:

```python
import pandas as pd
df = pd.read_parquet("data/processed/partidas_ajedrez_clean.parquet")
```

| Qué | Cómo se verificó | Resultado |
|---|---|---|
| **Tamaño** | `df.shape` | `(80145, 25)` — 80.145 partidas, 25 columnas |
| **Qué es una fila** | — | Una partida individual de ajedrez rated (bullet/blitz/rapid) |
| **Tipos** | `df.dtypes.value_counts()` | Mezcla real: texto (`GameUrl`, `White`, `Black`, `ECO`, `Opening`, `moves_text`, `TimeControl`), enteros (`WhiteElo`, `BlackElo`, `tiempo_base_seg`, `cantidad_jugadas`), categóricas (`resultado`, `TimeClass`, `Termination`, `nivel_promedio`, `familia_apertura`, `Event`, `Variant`), un `datetime64` (`Date`), un `bool` (`Rated`, `es_sorpresa`) y un `float` (`incremento_seg`, por el control `10+0.1`). Ninguna numérica quedó atrapada como texto. |
| **Nulos por columna** | `df.isna().mean().sort_values(ascending=False)` | **0,0 en las 25 columnas.** No es casualidad: el filtro de `limpieza_y_parseo` (Entrega 1) descarta antes toda fila sin resultado, sin ELO, no-rated o con menos de 5 medio-movimientos. Detalle completo en `guia-defensa-entrega-1.md` §4. |
| **Columnas sin información** | `df.columns[df.nunique() <= 1]` | `Event`, `Variant`, `Rated` — constantes después del filtro (`Live Chess`, `Standard`, `True`). Se van del modelo. |
| **Duplicados de la clave** | `df["GameUrl"].duplicated().sum()` | `0` (`df["GameUrl"].is_unique == True`) |
| **Distribución del objetivo** | `df["resultado"].value_counts(normalize=True)` | Gana Blancas **48,95 %** · Gana Negras **44,94 %** · Empate **6,11 %** |
| **Asimetría de las numéricas** | `df.select_dtypes("number").skew().sort_values()` | Ver tabla abajo |

### La distribución del objetivo (el número que más importa)

Ninguna clase se come todo (no hay un 92 % como advierte la consigna), pero **Empate sigue
siendo claramente minoritaria: 6,11 %**. Consecuencia directa para la Entrega 3: si se mide
sólo *accuracy* global, un modelo que nunca predice empate puede parecer bueno sin serlo.
Hay que reportar métricas por clase (precision/recall/F1 de Empate en particular) o
considerar balanceo.

### Asimetría — cuáles tienen cola larga

| Columna | Skew | Lectura |
|---|---:|---|
| `incremento_seg` | **5,69** | Muy sesgada a la derecha: casi todo el volumen en 0–2 seg, con una cola larga de controles poco frecuentes (ej. `10+0.1`). Candidata a discretizar o tratar junto con `tiempo_base_seg` en vez de como continua pura. |
| `tiempo_base_seg` | **3,84** | Sesgada a la derecha por la misma razón: pocos controles concentran mucho volumen (blitz 45.403 partidas + bullet 21.387 dominan sobre rapid 13.355). Candidata a escala logarítmica si entra como continua. |
| `es_sorpresa` | 1,21 | Es un indicador binario (0/1) con 24,11 % de unos: el skew alto es esperable en una binaria minoritaria, no señal de outliers. |
| `cantidad_jugadas` | 0,66 | Sesgo leve a la derecha (media 75,2, mediana 71, máximo 375): hay partidas largas que estiran la cola, pero no es extremo. |
| `diferencia_elo` | −0,30 | Prácticamente simétrica. |
| `WhiteElo` / `BlackElo` / `elo_promedio` | −0,45 a −0,46 | Sesgo leve a la **izquierda**. Es mucho más suave que en las muestras anteriores porque los cupos iguales por banda reparten el ELO de forma pareja: la distribución es ancha (media 1.862, mediana 2.022, desvío 728) en vez de amontonarse arriba. |

### `nivel_promedio` — la mejora más visible del selector nuevo

`df["nivel_promedio"].value_counts(normalize=True)`: `intermedio` 21,84 % · `principiante`
21,24 % · `top_mundial` 19,86 % · `experto` 18,83 % · `avanzado` 18,23 %. Las cinco bandas
quedan dentro de un rango de 3,6 puntos. En las versiones anteriores de la muestra, más de
la mitad del dataset era `top_mundial` y `principiante` casi no existía.

**Ojo con cómo se defiende esto:** el equilibrio es consecuencia del diseño del muestreo
(20 jugadores por banda), no un dato sobre cómo se reparten los ratings en Chess.com.
Sirve para que el modelado vea todos los niveles; no habilita a decir nada sobre la
población general.

---

## 3. Las cuatro fichas de hipótesis (min 7–13)

El docente elige dos de las cuatro y hay que recorrerlas enteras: afirmación → medida →
número → zona → decisión. Se cubre una pregunta de dominio (H1), una que decide sobre
una columna del modelo (H4), y quedan dos refutadas/matizadas (H2 y H3) para no caer en
"cuatro confirmadas".

### H1 — Diferencia de rating y resultado (pregunta de dominio)

| Campo | Contenido |
|---|---|
| **Afirmación** | A mayor `diferencia_elo` (blancas − negras), mayor proporción de victorias blancas; a menor (más negativa), mayor proporción de victorias negras. |
| **Qué esperábamos ver** | Una transición ordenada de `resultado` al recorrer bandas de `diferencia_elo`. |
| **Medida y gráfico** | V de Cramér entre bandas de `diferencia_elo` y `resultado`; barras apiladas por banda de diferencia. |
| **Número** | **V de Cramér = 0,234** |
| **Zona del semáforo** | 🟡 Amarilla — asociación relevante, no aplastante: el resultado cambia de manera ordenada entre bandas de diferencia, pero el rating no decide por sí solo quién gana. |
| **Decisión** | **Confirmada con matiz.** `diferencia_elo` entra como predictor principal de `resultado`, pero no alcanza sola: conviene complementar con `TimeClass` o `nivel_promedio` (máximo un control adicional) antes de sacar conclusiones fuertes. |

### H2 — Partidas parejas y longitud (refutada)

| Campo | Contenido |
|---|---|
| **Afirmación** | Las partidas con menor `abs_diferencia_elo` (rivales más parejos) tienden a durar más (`cantidad_jugadas`). |
| **Qué esperábamos ver** | Correlación negativa entre brecha absoluta de rating y cantidad de plies. |
| **Medida y gráfico** | Pearson y Spearman entre `abs_diferencia_elo` y `cantidad_jugadas`; scatter con suavizado. |
| **Número** | **Pearson = −0,025 · Spearman = 0,031** |
| **Zona del semáforo** | 🔴 Roja — prácticamente sin asociación (ambos coeficientes por debajo de 0,05 sobre 80.145 partidas) y **ni siquiera coinciden en el signo**: eso es exactamente lo que se ve cuando no hay relación. |
| **Decisión** | **Refutada.** Qué tan parejos son los rivales no predice la duración en esta muestra. `abs_diferencia_elo` **no** entra como predictor de `cantidad_jugadas`. (Nota: sí hay señal de nivel general: `elo_promedio` correlaciona 0,230/0,225 con `cantidad_jugadas` — las partidas de mayor nivel duran más. Es un fenómeno distinto al de esta hipótesis, y esa sí queda como candidata.) |

### H3 — Ritmo de juego y terminación por tiempo

| Campo | Contenido |
|---|---|
| **Afirmación** | Las partidas Bullet terminan por tiempo (`Termination = "time"`) en mayor proporción que Blitz y Rapid. |
| **Qué esperábamos ver** | Proporción de terminación por tiempo ordenada Bullet > Blitz > Rapid. |
| **Medida y gráfico** | Proporción de `Termination == "time"` por `TimeClass` (barras normalizadas) + η² de esa relación. |
| **Número** | Proporciones: Bullet **40,8 %** · Blitz **22,9 %** · Rapid **7,2 %** (n = 21.387 / 45.403 / 13.355). η² (TimeClass ~ indicador de tiempo) = **0,065** |
| **Zona del semáforo** | 🟡 Amarilla — con la corrida piloto de 8 cuentas daba η² = 0,012 (roja), porque Rapid tenía apenas 221 casos. Con 80.145 partidas y 13.355 de Rapid, el efecto se sostiene y cruza el umbral de "moderado": esta vez el gráfico y el número están de acuerdo. |
| **Decisión** | **Confirmada para el mecanismo de terminación.** El orden Bullet > Blitz > Rapid se sostiene con un tamaño de efecto moderado y ya no depende de una banda con pocas observaciones. Esto no demuestra por sí solo señal de `TimeClass` sobre los dos targets del proyecto; esa asociación se informa aparte en la tabla de candidatas. |

### H4 — Familia de apertura y longitud (decide sobre una columna del modelo)

| Campo | Contenido |
|---|---|
| **Afirmación** | Las aperturas cerradas (`familia_apertura = "Cerrada"`) producen partidas más largas que las semiabiertas. |
| **Qué esperábamos ver** | Separación clara de `cantidad_jugadas` entre familias de apertura. |
| **Medida y gráfico** | η² de `cantidad_jugadas` explicada por `familia_apertura`; boxplot por familia. |
| **Número** | **η² = 0,007** (Cerrada: media 76,8 plies · Semiabierta: media 75,2 plies — la dirección de la afirmación se mantiene, pero la brecha es de 1,6 plies) |
| **Zona del semáforo** | 🔴 Roja — la familia de apertura explica menos del 1 % de la variación de la duración. Dato para tener a mano por si preguntan: la familia más larga no es Cerrada sino India (81,4 plies), que es también la más chica (3.537 partidas contra 25.359 de Semiabierta). |
| **Decisión** | **Refutada como predictor de baseline.** `familia_apertura` **no** entra al modelo pre-partida (además de que sólo se conoce después de jugarse la apertura — ver H5/fuga en §4). Queda como candidata a un escenario aparte "post-apertura", a comparar contra el baseline sin apertura antes de incluirla. |

---

## 4. La tabla de columnas candidatas (lo que se lleva la Entrega 3)

Chequeo de fuga aplicado a cada fila: *¿esta columna existiría en el momento de predecir,
antes de que la partida ocurra?*

| Columna | Qué mide | Evidencia EDA | Decisión | ¿Existiría al predecir? |
|---|---|---|---|---|
| `diferencia_elo` | Balance de rating (blancas − negras) | V resultado = 0,234 | Entra como predictor principal de `resultado` | Parcial — hoy es el rating **posterior** a la partida (limitación de Chess.com, documentada desde la Entrega 1); conceptualmente sí existiría, en este dataset hereda fuga |
| `elo_promedio` | Nivel general de la partida | r duración = 0,230 / 0,225 | Entra, misma advertencia que `diferencia_elo` | Parcial — misma fuga temporal |
| `tiempo_base_seg` | Segundos base del control de tiempo | r duración = -0,086 / -0,078; V resultado = 0,047 | Entra por la pregunta de investigación; se evalúa su aporte incremental | Sí |
| `incremento_seg` | Segundos de incremento por jugada | r duración = -0,035 / -0,037; V resultado = 0,021 | Entra por dominio, en log o discretizado; se evalúa su aporte incremental | Sí |
| `TimeClass` | Modalidad oficial (bullet/blitz/rapid) | η² duración = 0,009; V resultado = 0,030 | Entra porque forma parte explícita de la pregunta; no porque el EDA muestre señal fuerte sobre los targets | Sí |
| `Date` | Fecha de la partida | No aplica: variable de partición | No entra como feature cruda; se reserva para partición temporal train/test | Sí, pero su uso es de partición, no de predictor directo |
| `familia_apertura` | Grupo de apertura (5 categorías) | η² duración = 0,007 | Sale del baseline; sólo se considera en un escenario "post-apertura" aparte | No — se conoce recién tras jugarse la apertura |
| `ECO` / `Opening` | Código/nombre detallado de apertura | No se evalúa: alta cardinalidad | Sale del baseline | No — mismo motivo que `familia_apertura` |
| `Termination` | Motivo de finalización | No aplica: fuga post-partida | Sale aunque η² con duración sea 0,193 | No — sólo existe cuando la partida ya terminó |
| `moves_text` | Texto completo de jugadas | No aplica: fuga post-partida | Sale como feature tabular; queda como insumo para derivar otras variables | No aplica como predictor directo — es post-partida en su totalidad |
| `GameUrl` | Identificador de partida | No aplica: cardinalidad total | Sale | Existiría, pero no aporta señal (es el índice) |
| `White` / `Black` | Usuario por color | No se usa en el modelo general | Salen; sólo tendría sentido en un producto "por jugador" con partición que evite fuga | Existirían, pero **no** son las 100 cuentas seleccionadas: `White`+`Black` tienen **53.761 usuarios distintos**, porque cada partida trae también al oponente real de cada jugador seleccionado |
| `WhiteElo` / `BlackElo` (crudos) | Rating por color | Redundancia matemática | Salen si ya están `diferencia_elo` y `elo_promedio` | Misma fuga temporal que `diferencia_elo` |
| `Event`, `Variant`, `Rated` | Auditoría | Varianza cero | Salen | No aportan información |
| `Result` | Resultado en formato PGN | No aplica: duplicado del target | Sale por fuga | Es la respuesta, no un predictor |

---

## 5. Lo que hay que saber explicar (se pregunta, no se mide)

**Cuál es la variable objetivo y cómo está distribuida.** `resultado` (clasificación:
Gana Blancas 48,95 % / Gana Negras 44,94 % / Empate 6,11 %) y `cantidad_jugadas`
(regresión: media 75,2 plies, mediana 71, rango 5–375). Empate es la clase a vigilar en
la Entrega 3.

**Por qué hay nulos donde hay nulos.** No hay: 0 nulos en las 25 columnas. No es que no
existan en la realidad — es que el pipeline de la Entrega 1 los convierte en filas
descartadas antes de llegar a este Parquet (ver `guia-defensa-entrega-1.md` §4 para el
detalle de qué se descarta y por qué). Los "nulos estructurales" de este dataset son en
realidad **categorías de reemplazo explícitas**: `familia_apertura = "Desconocida"` y
`Termination = "otro"` para cuando el crudo no trae el dato — en la corrida actual, ambas
dan 0 filas (0 %), así que hoy no hay missingness disfrazada, pero el mecanismo está y
hay que poder explicarlo.

**Qué hipótesis salió mal, y qué se hizo con eso.** H2 (partidas parejas duran más) se
refutó de punta a punta: Pearson −0,025 y Spearman 0,031, que ni coinciden en el signo. Se
descartó `abs_diferencia_elo` como predictor de `cantidad_jugadas`. H4 quedó en zona roja
del semáforo pese a mostrar una diferencia visible en las medias — ahí es donde se aplica
la regla de "el número decide, no el gráfico". H3 es el caso inverso y vale la pena tenerlo
a mano: con la corrida piloto de 8 cuentas daba roja (η² = 0,012) porque Rapid tenía 221
casos; con 80.145 partidas y 13.355 de Rapid pasó a amarilla (η² = 0,065) y se confirmó.

**Qué columna se descartó por fuga, y en qué momento se completa en la realidad.**
`Termination` es el caso más claro: η² = 0,193 con `cantidad_jugadas` (la asociación más
fuerte de todo el diagnóstico), pero sólo se conoce **cuando la partida ya terminó** — no
puede usarse para predecir nada pre-partida. `familia_apertura`/`ECO`/`Opening` se
completan recién después de que se jugaron los primeros movimientos, así que tampoco
sirven en un modelo estrictamente pre-partida (sí en uno "post-apertura", declarado como
tal).

**Qué quedó inconcluso y qué haría falta para resolverlo.**
1. Chess.com informa el rating posterior a cada partida. Para eliminar esa fuga haría
   falta reconstruir cronológicamente el rating previo desde historiales completos o usar
   una fuente que exponga rating previo y variación por separado; el notebook la mantiene
   visible como limitación para la Entrega 3.
2. La banda `avanzado` (1800–2200) se arma con titulados de nivel bajo (FM, CM, NM),
   porque la PubAPI no publica ninguna lista de jugadores por rating y el amateur fuerte
   sin título no figura en ninguna lista pública. O sea que esa banda representa a
   "titulados de 1800–2200", no al jugador típico de ese rango. Resolverlo requeriría otra
   fuente o muestrear por oponentes, que reintroduce sesgo de red.

---

## 6. Cómo se aprueba (la vara, para autochequeo)

- [x] El notebook corre entero y las salidas están guardadas.
- [x] El grupo puede describir el dataset con números, no con adjetivos (sección 2).
- [x] Las cuatro fichas están completas y cada una termina en una decisión (sección 3).
- [x] La tabla de columnas candidatas existe y cada fila pasó el chequeo de fuga (sección 4).
- [ ] Las respuestas no vienen de una sola persona — repartir quién explica cada ficha y
      cada fila de la tabla de columnas antes del 23/09.

---

## 7. Tres formas de perder los 20 minutos (y cómo no caer)

1. **El EDA de checklist.** No mostrar veinte histogramas sin conclusión — cada gráfico
   de la sección 3 responde una ficha concreta, no es un catálogo.
2. **Contestar con el gráfico, no con el número.** H3 es justamente el ejemplo de que el
   número puede ir para cualquier lado: en la corrida piloto el gráfico "se veía distinto"
   pero el η² (0,012) decía que era débil; en la corrida final el gráfico se ve parecido
   pero ahora el η² (0,065) sí lo respalda. La regla no es "desconfiar del gráfico": es
   "no quedarse solo con el gráfico".
3. **Que hable uno solo.** La pregunta sobre una ficha puede caerle a quien no la armó —
   repartir antes de entrar quién puede explicar cada sección de punta a punta, no sólo
   quién la escribió.
