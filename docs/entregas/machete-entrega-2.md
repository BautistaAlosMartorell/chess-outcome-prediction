# Machete — Entrega 2 (23/09/2026)

Todos los números salen de `notebooks/02_eda_hipotesis.ipynb` ejecutado con kernel
limpio sobre `data/processed/partidas_ajedrez_clean.parquet` (corrida del 22-23/09,
100 jugadores). Nada de esto está puesto a mano — si algo no coincide con el notebook,
manda el notebook.

## Tamaño y tipos

- `df.shape` → **(76.803, 25)**
- Duplicados de `GameUrl` → **0**
- Nulos totales → **0**
- Usuarios distintos (`White`+`Black`) → **50.326**
- Columnas constantes (`nunique <= 1`) → **`Event`, `Variant`, `Rated`**
- `df.dtypes.value_counts()`: 7 texto (`str`), 4 `int16`, 8 `category`, 1 `datetime64[us]`,
  1 `bool`, 1 `Int16`, 1 `Float64`, 1 `float64`, 1 `int8` (`es_sorpresa`)

## Distribución del objetivo

- `resultado`: Gana Blancas **48,8 %** · Gana Negras **45,1 %** · Empate **6,2 %**
- `cantidad_jugadas`: media **74,3**, mediana **69**, min **5**, p25 **51**, p75 **94**,
  p95 **136**, max **375**

## Nulos: 0, pero 426 descartadas (77.229 crudas → 76.803 finales)

| Motivo | Tipo | Filas |
|---|---|---:|
| Duplicado entre usuarios | Estructural | 6 |
| Sin resultado | Faltante real | 0 |
| Sin ELO válido | Faltante real | 0 |
| Fecha inválida | Faltante real | 0 |
| Variante no estándar | Estructural | 0 |
| Modalidad fuera de alcance | Estructural | 0 |
| No rated | Estructural | 0 |
| Menos de 5 medio-movimientos | Estructural | 420 |

Los 3 motivos de faltante real dieron 0 en esta corrida. `familia_apertura="Desconocida"`
y `Termination="otro"` (nulos disfrazados) → **0 filas cada uno**.

## Asimetría (skew)

| Columna | Skew |
|---|---:|
| `elo_promedio` | −0,588 |
| `BlackElo` | −0,577 |
| `WhiteElo` | −0,576 |
| `diferencia_elo` | −0,313 |
| `cantidad_jugadas` | 0,731 |
| `es_sorpresa` | 1,250 |
| `tiempo_base_seg` | 4,089 |
| `incremento_seg` | 6,034 |

## `nivel_promedio` (cobertura por banda de ELO)

`top_mundial` 20,72 % · `intermedio` 20,53 % · `principiante` 20,05 % · `avanzado`
19,48 % · `experto` 19,22 % — rango de 1,5 pp entre bandas.

## Anomalía UTC del 1/9

99 partidas (0,13 %) fechadas 2026-09-01 (59 rapid, 38 blitz, 2 bullet) — límite horario
del archivo mensual, no error.

## Rango de fechas y actividad por jugador

- Años: 2013→1, 2014→535, 2015→117, 2016→555, 2017→735, 2018→1.519, 2019→1.856,
  2020→5.174, 2021→4.206, 2022→2.587, 2023→5.505, 2024→7.573, 2025→12.769, 2026→33.671
- Partidas por jugador seleccionado: n=100, media 768, mediana 994, min 16, max 1.001
- Las partidas más viejas (2013-2018) las aportan cuentas de **baja actividad**, no de
  ELO bajo (mezcla `intermedio`/`avanzado`/`experto`/`top_mundial` entre las 10 más viejas)

---

## Las cuatro fichas — medida → zona → movimiento → decisión

### H1 · Diferencia de ELO y resultado (Responder / dominio)

- Medida: `eta2(diferencia_elo, resultado)` = **0,094** → 🟡 amarilla
- Movimiento (1/2): controlar por `nivel_promedio`
  - Por banda: principiante 0,084 · intermedio 0,086 · avanzado 0,093 · experto 0,144 ·
    top_mundial 0,122 — **las 5 quedan amarillas**
  - Controlado (SS pooleadas, no la banda más alta): **η² = 0,101** → sigue 🟡
  - (Candidato descartado: `TimeClass` → 0,079–0,099, no diferencia nada)
- **Decisión: INCONCLUSA** — amarillo en las 5 bandas y en la versión controlada, sin
  un segundo movimiento que el gráfico justifique
- Dato extra: con el rating reconstruido (sin fuga, sólo lado seguido) el η² baja a
  **0,065** (sección 9.1 del notebook)

### H2 · Paridad de ELO y duración (Predecir)

- Medida: `asociacion(abs_diferencia_elo, cantidad_jugadas)`
  - Pearson = **−0,012** → 🔴 · Spearman = **0,060** → 🔴 · brecha = **0,071** → 🟡
- Movimiento: no hace falta, rojo termina la hipótesis
- **Decisión: REFUTADA**

### H3 · Ritmo y terminación por tiempo (Responder / dominio)

- Medida: proporción `Termination=="time"` por `TimeClass` vs. global (**25,0 %**)
  - Bullet **43,6 %** (+18,6 pp) · Blitz **24,0 %** (−1,0 pp) · Rapid **6,8 %** (−18,1 pp)
  - `eta2` de apoyo = **0,090** → 🟡 amarilla
- Movimiento (1/2): partir por `nivel_promedio` (las 5 bandas, orden Bullet>Blitz>Rapid
  se sostiene siempre)
  - principiante **0,265** 🟢 · intermedio **0,136** 🟡 · avanzado **0,064** 🟡 ·
    experto **0,020** 🔴 · top_mundial **0,025** 🔴
- **Decisión: CONFIRMADA en niveles bajos, REFUTADA en niveles altos** (no es una sola
  decisión para todo el dataset)

### H4 · Familia de apertura y duración (Predecir)

- Medida: `separacion(Cerrada, Semiabierta)` = **0,087** → 🔴 roja
  - Cerrada 76,7 plies vs. Semiabierta 73,8 (dirección se sostiene, magnitud no)
  - Complementario: `eta2` sobre 5 familias = **0,008** → también 🔴
  - India es la más larga (81,4 plies) y la más chica (3.676 partidas)
- Movimiento: no hace falta, rojo termina la hipótesis
- **Decisión: REFUTADA**

**Mezcla exigida por la consigna:** responder = H1, H3 · predecir = H2, H4 · refutada
= H2, H4 · inconclusa = H1 · movimientos usados ≤ 2 en las cuatro. ✓ Todo se cumple.

---

## Fugas cuantificadas (sección 6 / 9 del notebook)

**Rating de Chess.com (posterior a la partida):**
- Test directo (100 jugadores, propio rating por `end_time`): coincide con la partida
  **ESA** en **99,91 %** (n=71.186) vs. con la partida **ANTERIOR** en **52,13 %**
  (n=69.671, ≈ azar) → confirmado, sin ambigüedad
- Efecto en partidas parejas (`|diferencia_elo|<=10`, n=14.487): 52,91 % Blancas si
  diff>0 vs. 43,95 % si diff<0 → brecha **8,96 pp**
- Reconstrucción parcial (99,7 % de filas cubiertas): η² de H1 baja **0,093 → 0,065**
  (lado seguido reconstruido; lado del rival **queda inconcluso**, sin datos)

**`es_sorpresa`:** coincide **100,0000 %** con una regla derivada de `resultado` +
`diferencia_elo` → identidad, no asociación. Fuga por construcción.

---

## Tabla de columnas candidatas — decisión por fila (25 columnas + 1 derivada)

| Columna | Decisión |
|---|---|
| `GameUrl` | Sale — clave, sin señal |
| `Date` | No entra cruda — partición temporal |
| `White`/`Black` | Salen del modelo general |
| `WhiteElo`/`BlackElo` | Salen (redundantes); fuga si entraran crudas |
| `Result` | Sale — es el target en otro formato |
| `resultado` | Es el objetivo |
| `cantidad_jugadas` | Es el objetivo |
| `TimeClass` | Entra (pregunta de investigación, no por el EDA — η² duración = 0,004) |
| `TimeControl` | Sale — se descompone |
| `tiempo_base_seg` | Entra por dominio (r duración = −0,027/−0,041) |
| `incremento_seg` | Entra por dominio (r duración = −0,002/−0,021) |
| `ECO` | Sale del baseline — alta cardinalidad + fuga temporal |
| `Opening` | Sale del baseline — alta cardinalidad + fuga temporal |
| `familia_apertura` | Sale del baseline (H4 refutada + fuga temporal) |
| `Termination` | Sale por fuga temporal (η² duración = 0,175 — el más fuerte, y aun así sale) |
| `moves_text` | Sale — fuga post-partida total |
| `diferencia_elo` | Entra con advertencia; sólo versión reconstruida (η² resultado = 0,094) |
| `elo_promedio` | Entra con advertencia; misma fuga (r duración = 0,249/0,257) |
| `nivel_promedio` | Misma fuga que `elo_promedio`, del que se deriva |
| `es_sorpresa` | Sale — fuga por construcción (100 % identidad con el target) |
| `abs_diferencia_elo` (derivada) | No entra — H2 refutada |
| `Event`/`Variant`/`Rated` | Salen — varianza cero |

**Regla para defender cualquier fila:** ¿esta columna existiría en el momento de
predecir, antes de que arranque la partida? Si la respuesta ya está adentro (rating
posterior, terminación, apertura jugada), no es una feature — es la respuesta escrita
de otra forma.

---

## Devolución de la Entrega 1 (resuelta)

> "Automatizar la elección de los jugadores y agregar variabilidad."

- Automatizar → `listar_jugadores` (`src/player_selection.py`), sin cuentas a mano,
  congelada en `data/raw/seleccion/jugadores_seleccionados.yaml`.
- Variabilidad → de 8 cuentas fijas (concentradas en `top_mundial`) a 100 jugadores,
  20 por banda, 19,2–20,7 % cada una; rango temporal 2013–2026; 7.204 → 76.803 partidas.
