# Guía de defensa — Entrega 2 (Ajedrez online, Chess.com)

> **La pregunta de fondo de esta entrega es una sola:**
> ¿sabés qué tiene adentro tu dataset, y podés defender con un número cada decisión
> que tomaste sobre él? Todo lo que salga de acá — qué columnas entran, cuál es el
> objetivo, qué hay que transformar — es la materia prima de la Entrega 3.

Fuente de los números: `data/processed/partidas_ajedrez_clean.parquet` (corrida con el
selector por banda de ELO `listar_jugadores`, 18/09/2026, 93.669 partidas) y
`docs/entregas/guia-columnas-y-features.md` (diccionario de columnas y primer diagnóstico
cuantitativo). Todos los números de este documento se recalcularon en vivo sobre ese
Parquet — no son estimaciones ni heredados de la corrida piloto de 8 cuentas.

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
   (`chess_com.usernames`) y ahora arma la muestra ella sola por banda de ELO: parte de 8
   seeds, extrae oponentes del Parquet previo (o los descubre por la PubAPI en la primera
   corrida), los valida y apunta a `target_per_band: 20` jugadores en cada una de las 5
   bandas. La ventana temporal sigue congelada (`until_month: "2026-08"`), así que lo único
   que crece es **quién** se descarga, no **hasta cuándo**. En la corrida real del
   18/09/2026 se seleccionaron 93 jugadores (13 `principiante` + 20 en cada una de las
   otras cuatro bandas) más los 8 seeds — la banda `principiante` quedó corta de su cupo de
   20 y el DAG **siguió igual** (warning, no error), tal como está diseñada la tolerancia.
   El resultado: **93.669 partidas** finales, casi 13× el volumen de la corrida piloto de 8
   cuentas (7.204).
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
| **Tamaño** | `df.shape` | `(93669, 25)` — 93.669 partidas, 25 columnas |
| **Qué es una fila** | — | Una partida individual de ajedrez rated (bullet/blitz/rapid) |
| **Tipos** | `df.dtypes.value_counts()` | Mezcla real: texto (`GameUrl`, `White`, `Black`, `ECO`, `Opening`, `moves_text`, `TimeControl`), enteros (`WhiteElo`, `BlackElo`, `tiempo_base_seg`, `cantidad_jugadas`), categóricas (`resultado`, `TimeClass`, `Termination`, `nivel_promedio`, `familia_apertura`, `Event`, `Variant`), un `datetime64` (`Date`), un `bool` (`Rated`, `es_sorpresa`) y un `float` (`incremento_seg`, por el control `10+0.1`). Ninguna numérica quedó atrapada como texto. |
| **Nulos por columna** | `df.isna().mean().sort_values(ascending=False)` | **0,0 en las 25 columnas.** No es casualidad: el filtro de `limpieza_y_parseo` (Entrega 1) descarta antes toda fila sin resultado, sin ELO, no-rated o con menos de 5 medio-movimientos. Detalle completo en `guia-defensa-entrega-1.md` §4. |
| **Columnas sin información** | `df.columns[df.nunique() <= 1]` | `Event`, `Variant`, `Rated` — constantes después del filtro (`Live Chess`, `Standard`, `True`). Se van del modelo. |
| **Duplicados de la clave** | `df["GameUrl"].duplicated().sum()` | `0` (`df["GameUrl"].is_unique == True`) |
| **Distribución del objetivo** | `df["resultado"].value_counts(normalize=True)` | Gana Blancas **48,94 %** · Gana Negras **45,30 %** · Empate **5,76 %** |
| **Asimetría de las numéricas** | `df.select_dtypes("number").skew().sort_values()` | Ver tabla abajo |

### La distribución del objetivo (el número que más importa)

Ninguna clase se come todo (no hay un 92 % como advierte la consigna), pero **Empate sigue
siendo claramente minoritaria (5,76 %,** bajó un poco respecto al 6,36 % de la corrida
piloto). Consecuencia directa para la Entrega 3: si se mide sólo *accuracy* global, un
modelo que nunca predice empate puede parecer bueno sin serlo. Hay que reportar métricas
por clase (precision/recall/F1 de Empate en particular) o considerar balanceo.

### Asimetría — cuáles tienen cola larga

| Columna | Skew | Lectura |
|---|---:|---|
| `incremento_seg` | **6,84** | Muy sesgada a la derecha: casi todo el volumen en 0–2 seg, con una cola larga de controles poco frecuentes (ej. `10+0.1`). Candidata a discretizar o tratar junto con `tiempo_base_seg` en vez de como continua pura. |
| `tiempo_base_seg` | **3,64** | Sesgada a la derecha por la misma razón, y más marcada que en la corrida piloto: pocos controles concentran mucho volumen (bullet 42.075 partidas + blitz 37.670 dominan sobre rapid 13.924). Candidata a escala logarítmica si entra como continua. |
| `es_sorpresa` | 1,17 | Es un indicador binario (0/1) con 24,78 % de unos: el skew alto es esperable en una binaria minoritaria, no señal de outliers. |
| `cantidad_jugadas` | 0,71 | Sesgo leve a la derecha (media 77,1, mediana 72, máximo 335): hay partidas largas que estiran la cola, pero no es extremo. |
| `diferencia_elo` | 0,10 | Prácticamente simétrica. |
| `WhiteElo` / `BlackElo` / `elo_promedio` | −0,57 a −0,58 | Sesgo leve a la **izquierda**, bastante más suave que en la corrida piloto (ahí era −0,64 a −0,76). Tiene sentido: el selector por banda de ELO ahora reparte la muestra de forma mucho más pareja entre niveles (`top_mundial` pasó de 55,82 % a **24,32 %** de las partidas — ver distribución de `nivel_promedio` abajo), así que la cola hacia el nivel bajo pesa menos sobre la media. |

### `nivel_promedio` — la mejora más visible del selector nuevo

`df["nivel_promedio"].value_counts(normalize=True)`: `top_mundial` 24,32 % · `experto`
22,82 % · `intermedio` 22,21 % · `avanzado` 19,73 % · `principiante` 10,91 %. Con la corrida
piloto (8 cuentas fijas, mayoría streamers/GM) más de la mitad del dataset era
`top_mundial`; ahora las cinco bandas están razonablemente repartidas — `principiante` es
la única floja (10,91 %), coherente con que esa banda no llegó a su cupo completo de
candidatos en esta corrida (13 de 20, ver sección 1).

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
| **Medida y gráfico** | η² de `diferencia_elo` agrupada por `resultado`; barras apiladas por banda de diferencia. |
| **Número** | **η² = 0,098** (bajó de 0,216 en la corrida piloto de 8 cuentas) |
| **Zona del semáforo** | 🟡 Amarilla — señal relevante, no aplastante: el rating explica una porción real de quién gana, pero deja bastante varianza sin explicar. Más débil que en la corrida piloto porque ahí la muestra eran casi todos jugadores de élite muy dispares entre sí; con las cinco bandas de ELO representadas, hay más partidas parejas donde el rating solo no decide. |
| **Decisión** | **Confirmada con matiz.** `diferencia_elo` entra como predictor principal de `resultado`, pero no alcanza sola: conviene complementar con `TimeClass` o `nivel_promedio` (máximo un control adicional) antes de sacar conclusiones fuertes. |

### H2 — Partidas parejas y longitud (refutada)

| Campo | Contenido |
|---|---|
| **Afirmación** | Las partidas con menor `abs_diferencia_elo` (rivales más parejos) tienden a durar más (`cantidad_jugadas`). |
| **Qué esperábamos ver** | Correlación negativa entre brecha absoluta de rating y cantidad de plies. |
| **Medida y gráfico** | Pearson y Spearman entre `abs_diferencia_elo` y `cantidad_jugadas`; scatter con suavizado. |
| **Número** | **Pearson = 0,031 · Spearman = 0,060** |
| **Zona del semáforo** | 🔴 Roja — prácticamente sin asociación (ambos coeficientes por debajo de 0,1 sobre 93.669 partidas); el signo ahora es positivo, pero es ruido, no evidencia de una relación real en ningún sentido. |
| **Decisión** | **Refutada.** Qué tan parejos son los rivales no predice la duración en esta muestra. `abs_diferencia_elo` **no** entra como predictor de `cantidad_jugadas`. (Nota: sí hay señal de nivel general: `elo_promedio` correlaciona 0,256/0,254 con `cantidad_jugadas` — más fuerte que en la corrida piloto (0,213/0,162) — es un fenómeno distinto al de esta hipótesis, y esa sí queda como candidata.) |

### H3 — Ritmo de juego y terminación por tiempo

| Campo | Contenido |
|---|---|
| **Afirmación** | Las partidas Bullet terminan por tiempo (`Termination = "time"`) en mayor proporción que Blitz y Rapid. |
| **Qué esperábamos ver** | Proporción de terminación por tiempo ordenada Bullet > Blitz > Rapid. |
| **Medida y gráfico** | Proporción de `Termination == "time"` por `TimeClass` (barras normalizadas) + η² de esa relación. |
| **Número** | Proporciones: Bullet **40,9 %** · Blitz **22,2 %** · Rapid **7,4 %** (n = 42.075 / 37.670 / 13.924). η² (TimeClass ~ indicador de tiempo) = **0,075** |
| **Zona del semáforo** | 🟡 Amarilla — cambió de zona respecto a la corrida piloto (ahí daba η² = 0,012, roja). Con 93.669 partidas y Rapid ya con 13.924 casos (antes 221), el efecto se sostiene y cruza el umbral de "moderado": esta vez el gráfico y el número están de acuerdo. |
| **Decisión** | **Confirmada.** El orden Bullet > Blitz > Rapid se sostiene con un tamaño de efecto moderado y ya no depende de una banda con pocas observaciones. `TimeClass` entra como predictor de fuga temporal / terminación, no solo de `resultado`. |

### H4 — Familia de apertura y longitud (decide sobre una columna del modelo)

| Campo | Contenido |
|---|---|
| **Afirmación** | Las aperturas cerradas (`familia_apertura = "Cerrada"`) producen partidas más largas que las semiabiertas. |
| **Qué esperábamos ver** | Separación clara de `cantidad_jugadas` entre familias de apertura. |
| **Medida y gráfico** | η² de `cantidad_jugadas` explicada por `familia_apertura`; boxplot por familia. |
| **Número** | **η² = 0,004** (Cerrada: media 78,4 plies · Semiabierta: media 76,0 plies — la dirección se mantiene pero el efecto es todavía más chico que en la corrida piloto, donde daba 0,012) |
| **Zona del semáforo** | 🔴 Roja — la familia de apertura explica muy poca variación global de la duración, y con más datos el efecto se achicó en vez de crecer (señal de que el patrón de la corrida piloto era en parte ruido de muestra chica). |
| **Decisión** | **Refutada como predictor de baseline.** `familia_apertura` **no** entra al modelo pre-partida (además de que sólo se conoce después de jugarse la apertura — ver H5/fuga en §4). Queda como candidata a un escenario aparte "post-apertura", a comparar contra el baseline sin apertura antes de incluirla. |

---

## 4. La tabla de columnas candidatas (lo que se lleva la Entrega 3)

Chequeo de fuga aplicado a cada fila: *¿esta columna existiría en el momento de predecir,
antes de que la partida ocurra?*

| Columna | Qué mide | Zona | Decisión | ¿Existiría al predecir? |
|---|---|---|---|---|
| `diferencia_elo` | Balance de rating (blancas − negras) | 🟡 | Entra como predictor principal de `resultado` | Parcial — hoy es el rating **posterior** a la partida (limitación de Chess.com, documentada desde la Entrega 1); conceptualmente sí existiría, en este dataset hereda fuga |
| `elo_promedio` | Nivel general de la partida | 🟡 | Entra, misma advertencia que `diferencia_elo` | Parcial — misma fuga temporal |
| `tiempo_base_seg` | Segundos base del control de tiempo | 🟢 | Entra, en escala log dado el skew 3,64 | Sí |
| `incremento_seg` | Segundos de incremento por jugada | 🟡 | Entra, discretizado o en log dado el skew 6,84 | Sí |
| `TimeClass` | Modalidad oficial (bullet/blitz/rapid) | 🟢 | Entra | Sí |
| `Date` | Fecha de la partida | 🟡 | No entra como feature cruda; se reserva para partición temporal train/test | Sí, pero su uso es de partición, no de predictor directo |
| `familia_apertura` | Grupo de apertura (5 categorías) | 🔴 | Sale del baseline (η² = 0,004 con `cantidad_jugadas`, ver H4); sólo en un escenario "post-apertura" aparte | No — se conoce recién tras jugarse la apertura |
| `ECO` / `Opening` | Código/nombre detallado de apertura | 🔴 | Sale del baseline (454 / 6.536 categorías, alta cardinalidad — creció respecto a la corrida piloto por la mayor diversidad de jugadores) | No — mismo motivo que `familia_apertura` |
| `Termination` | Motivo de finalización | 🔴 | Sale — η² = 0,206 con `cantidad_jugadas`, la asociación más fuerte del dataset, pero es fuga pura | No — sólo existe cuando la partida ya terminó |
| `moves_text` | Texto completo de jugadas | 🔴 | Sale como feature tabular; queda como insumo para derivar otras variables | No aplica como predictor directo — es post-partida en su totalidad |
| `GameUrl` | Identificador de partida | 🔴 | Sale — cardinalidad = número de filas | Existiría, pero no aporta señal (es el índice) |
| `White` / `Black` | Usuario por color | 🔴 | Salen del modelo general; sólo tendría sentido en un producto "por jugador" con partición que evite fuga entre entrenamiento y prueba | Existirían, pero **no** son las ~100 cuentas sembradas: `White`+`Black` tienen **53.655 usuarios distintos**, porque cada partida trae también al oponente real de cada jugador sembrado. No es memorización de un puñado de cuentas — es el sesgo de red descripto en `guia-defensa-entrega-1.md` §5 (el grafo de oponentes de 8 seeds + su expansión por banda de ELO, no una muestra aleatoria del universo Chess.com) |
| `WhiteElo` / `BlackElo` (crudos) | Rating por color | 🔴 | Salen si ya están `diferencia_elo` y `elo_promedio` (dependencia matemática exacta, ver `guia-columnas-y-features.md` §3.2) | Misma fuga temporal que `diferencia_elo` |
| `Event`, `Variant`, `Rated` | Auditoría | 🔴 | Salen — constantes tras el filtro | No aportan (varianza cero) |
| `Result` | Resultado en formato PGN | 🔴 | Sale — es el target escrito en otro formato | Es la respuesta, no un predictor |

---

## 5. Lo que hay que saber explicar (se pregunta, no se mide)

**Cuál es la variable objetivo y cómo está distribuida.** `resultado` (clasificación:
Gana Blancas 48,94 % / Gana Negras 45,30 % / Empate 5,76 %) y `cantidad_jugadas`
(regresión: media 77,1 plies, mediana 72, rango 5–335). Empate es la clase a vigilar en
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
refutó de punta a punta: Pearson 0,031, prácticamente cero. Se descartó
`abs_diferencia_elo` como predictor de `cantidad_jugadas`. H4 quedó en zona roja del
semáforo pese a mostrar una diferencia visible en las medias — ahí es donde se aplica la
regla de "el número decide, no el gráfico". H3 es el caso inverso y vale la pena tenerlo
a mano: con la corrida piloto de 8 cuentas daba roja (η² = 0,012); con 93.669 partidas
pasó a amarilla (η² = 0,075) y se confirmó — el gráfico "se veía distinto" en ambas
corridas, pero sólo en la segunda el número lo respaldó.

**Qué columna se descartó por fuga, y en qué momento se completa en la realidad.**
`Termination` es el caso más claro: η² = 0,206 con `cantidad_jugadas` (la asociación más
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
2. La banda `principiante` quedó con 13 de los 20 jugadores objetivo en esta corrida (el
   selector lo tolera y sigue, ver sección 1); es la banda con menos partidas del dataset
   (10,91 % del total) y la que menos confianza estadística tiene si se la analiza sola.

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
   pero ahora el η² (0,075) sí lo respalda. La regla no es "desconfiar del gráfico": es
   "no quedarse solo con el gráfico".
3. **Que hable uno solo.** La pregunta sobre una ficha puede caerle a quien no la armó —
   repartir antes de entrar quién puede explicar cada sección de punta a punta, no sólo
   quién la escribió.
