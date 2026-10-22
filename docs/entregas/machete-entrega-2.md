# Machete — Entrega 2

Todos los números salen de `notebooks/02_eda_hipotesis.ipynb` ejecutado con kernel
limpio sobre la corrida oficial del 22/10/2026 (100 jugadores, 80.697 partidas). Nada de
esto está puesto a mano — si algo no coincide con el notebook, manda el notebook.

El notebook tiene dos partes: **A · antes de la partida** (una fila por partida) y
**B · durante la partida** (una fila por partida y corte).

## Tamaño y tipos (Parte A)

- `df.shape` → **(80.697, 35)**
- Duplicados de `GameUrl` → **0**
- Nulos → sólo estructurales: `TournamentUrl` **74.477** (no es de torneo) y las tres
  `tasa_*_hist` **1.620** cada una (matchup sin 30 partidas previas)
- Usuarios distintos (`White`+`Black`) → **54.251**
- Columnas constantes (`nunique <= 1`) → **`Event`, `Variant`, `Rated`**

## Distribución del objetivo

- `resultado`: Gana Blancas **49,0 %** · Gana Negras **44,9 %** · Empate **6,1 %**
- `cantidad_jugadas`: media **75,2**, mediana **71**, min **5**, p25 **51**, p75 **96**,
  p95 **136**, max **375**

## Columnas críticas sin nulos, pero 397 descartadas (81.094 crudas → 80.697 finales)

| Motivo | Tipo | Filas |
|---|---|---:|
| Duplicado entre usuarios | Estructural | 5 |
| Sin resultado | Faltante real | 0 |
| Sin ELO válido | Faltante real | 0 |
| Fecha inválida | Faltante real | 0 |
| Variante no estándar | Estructural | 0 |
| Modalidad fuera de alcance | Estructural | 0 |
| No rated | Estructural | 0 |
| Menos de 5 medio-movimientos | Estructural | 392 |

Los 3 motivos de faltante real dieron 0 en esta corrida. `familia_apertura="Desconocida"`
y `Termination="otro"` (nulos disfrazados) → **0 filas cada uno**.

## Asimetría (skew)

| Columna | Skew |
|---|---:|
| `elo_promedio` | −0,464 |
| `BlackElo` | −0,454 |
| `WhiteElo` | −0,453 |
| `diferencia_elo` | −0,359 |
| `cantidad_jugadas` | 0,660 |
| `es_sorpresa` | 1,211 |
| `tiempo_base_seg` | 3,850 |
| `incremento_seg` | 5,957 |

## `nivel_promedio` (cobertura por banda de ELO)

`intermedio` 21,78 % · `principiante` 21,10 % · `top_mundial` 19,52 % · `experto`
19,20 % · `avanzado` 18,40 % — rango de 3,4 pp entre bandas.

## Anomalía UTC del 1/9

56 partidas (0,07 %) fechadas 2026-09-01 (29 blitz, 15 rapid, 12 bullet) — límite horario
del archivo mensual, no error.

## Rango de fechas y actividad por jugador

- Años: 2013→1, 2014→549, 2015→157, 2016→560, 2017→744, 2018→2.005, 2019→1.439,
  2020→5.692, 2021→4.640, 2022→3.601, 2023→6.797, 2024→7.387, 2025→13.633, 2026→33.492
- Partidas por jugador seleccionado: n=100, media 807, mediana 994,5, min 16, max 1.001
- Las partidas más viejas las aportan cuentas de **baja actividad**, no de una banda de
  ELO: entre las 10 más viejas aparecen las cinco bandas

---

## Parte A — las cuatro fichas antes de la partida

### H1 · Diferencia de ELO y resultado (Responder / dominio)

- Medida: `eta2(diferencia_elo, resultado)` = **0,091** → 🟡 amarilla
- Movimiento (1/2): controlar por `nivel_promedio`
  - Por banda: principiante 0,081 · intermedio 0,079 · avanzado 0,095 · experto 0,141 ·
    top_mundial 0,120 — **las 5 quedan amarillas**
  - Controlado (SS pooleadas, no la banda más alta): **η² = 0,099** → sigue 🟡
  - (Candidato descartado: `TimeClass` → 0,082–0,098, no diferencia nada)
- **Decisión: INCONCLUSA** — amarillo en las 5 bandas y en la versión controlada, sin
  un segundo movimiento que el gráfico justifique
- Dato extra: con el rating reconstruido (sin fuga, sólo lado seguido) el η² baja a
  **0,062** (sección 9.1 del notebook)

### H2 · Paridad de ELO y duración (Predecir)

- Medida: `asociacion(abs_diferencia_elo, cantidad_jugadas)`
  - Pearson = **−0,027** → 🔴 · Spearman = **0,030** → 🔴 · brecha = **0,057** → 🟡
- Movimiento: no hace falta, rojo termina la hipótesis
- **Decisión: REFUTADA**

### H3 · Ritmo y terminación por tiempo (Responder / dominio)

- Medida: proporción `Termination=="time"` por `TimeClass` vs. global (**25,1 %**)
  - Bullet **41,2 %** (+16,1 pp) · Blitz **22,6 %** (−2,5 pp) · Rapid **7,2 %** (−17,9 pp)
  - `eta2` de apoyo = **0,068** → 🟡 amarilla
- Movimiento (1/2): partir por `nivel_promedio` (las 5 bandas, orden Bullet>Blitz>Rapid
  se sostiene siempre)
  - principiante **0,130** 🟡 · intermedio **0,095** 🟡 · avanzado **0,049** 🔴 ·
    experto **0,021** 🔴 · top_mundial **0,026** 🔴
- **Decisión: REFUTADA en niveles medios y altos, INCONCLUSA en niveles bajos** (no es
  una sola decisión para todo el dataset; ninguna banda llega a verde)

### H4 · Familia de apertura y duración (Predecir)

- Medida: `separacion(Cerrada, Semiabierta)` = **0,054** → 🔴 roja
  - Cerrada 76,8 plies vs. Semiabierta 75,0 (dirección se sostiene, magnitud no)
  - Complementario: `eta2` sobre 5 familias = **0,008** → también 🔴
  - India es la más larga (81,6 plies) y la más chica (3.635 partidas)
- Movimiento: no hace falta, rojo termina la hipótesis
- **Decisión: REFUTADA**

**Mezcla exigida por la consigna:** responder = H1, H3 · predecir = H2, H4 · refutadas o
inconclusas = las cuatro, en todo o en parte · movimientos usados ≤ 2 en todas. ✓

---

## Parte B — las cuatro fichas durante la partida

Sobre la población común: **51.266 partidas** que llegan al ply 60 (cortes 10 a 60; el
corte 0 no entra porque material y relojes son iguales en la posición inicial).

| Hipótesis | Medida | Zona | Decisión |
|---|---|---|---|
| H1′ · material → resultado, según el corte | η² 0,000 · 0,004 · 0,012 · 0,033 · **0,118** (plies 10 a 60); en el 60, rapid 0,205 | 🟡 sólo en el ply 60 | Parcialmente confirmada |
| H2′ · reloj más allá del material | η² ply 60 = **0,086**; controlado por material = **0,092**; bullet 0,145 · rapid 0,021 | 🟡 | Entra, modulada por el ritmo |
| H3′ · estado de la partida → plies restantes | Spearman ply 60: material **−0,155** (signo al revés), reloj **0,241** (bullet 0,453) | 🔴 / 🟡 | Refutada para el material |
| H4′ · ventaja de las blancas | brecha **4,1 pp** (±0,7), igual en los tres ritmos; **7,0 pp** en `top_mundial` | 🔴 (η² por ritmo = 0,000) | Ventaja confirmada; no cambia con el ritmo |

---

## Fugas cuantificadas (sección 9 del notebook)

**Rating de Chess.com (posterior a la partida):**
- Test directo (100 jugadores, propio rating por `end_time`): coincide con la partida
  **ESA** en **99,92 %** (n=74.835) vs. con la partida **ANTERIOR** en **51,75 %**
  (n=73.194, ≈ azar) → confirmado, sin ambigüedad
- Efecto en partidas parejas (`|diferencia_elo|<=10`, n=15.442): 52,47 % Blancas si
  diff>0 vs. 44,94 % si diff<0 → brecha **7,53 pp**
- Reconstrucción parcial (99,7 % de filas cubiertas): η² de H1 baja **0,091 → 0,062**
  (lado seguido reconstruido; lado del rival **queda inconcluso**, sin datos)

**`es_sorpresa`:** coincide **100,0000 %** con una regla derivada de `resultado` +
`diferencia_elo` → identidad, no asociación. Fuga por construcción.

---

## Tabla de columnas candidatas, Parte A — decisión por fila (35 columnas + 1 derivada)

| Columna | Decisión |
|---|---|
| `GameUrl` | Sale — clave, sin señal |
| `Date` | No entra cruda — partición temporal |
| `White`/`Black` | Salen del modelo general |
| `WhiteElo`/`BlackElo` | Salen — rating posterior; los reemplaza el rating previo reconstruido |
| `Result` | Sale — es el target en otro formato |
| `resultado` | Es el objetivo |
| `cantidad_jugadas` | Es el objetivo |
| `TimeClass` | Entra (pregunta de investigación, no por el EDA — η² duración = 0,009) |
| `TimeControl` | Sale — se descompone |
| `tiempo_base_seg` | Entra por dominio (r duración = −0,085/−0,076) |
| `incremento_seg` | Entra por dominio (r duración = −0,033/−0,035) |
| `ECO` | Sale — alta cardinalidad + fuga (se asigna mirando la línea completa) |
| `Opening` | Sale — alta cardinalidad + fuga |
| `familia_apertura` | Sale (H4 refutada + fuga) |
| `Termination` | Sale por fuga temporal (η² duración = 0,195 — de los más fuertes, y aun así sale) |
| `moves_text` | Sale — contiene toda la partida |
| `diferencia_elo` | Sale (η² resultado = 0,091, inflado por la fuga); la reemplaza el rating previo |
| `elo_promedio` | Sale — misma fuga (r duración = 0,229/0,224) |
| `nivel_promedio` | Misma fuga que `elo_promedio`, del que se deriva |
| `es_sorpresa` | Sale — fuga por construcción (100 % identidad con el target) |
| `abs_diferencia_elo` (derivada) | No entra — H2 refutada |
| `Event`/`Variant`/`Rated` | Salen — varianza cero |
| `TournamentUrl`/`EsTorneo` | `EsTorneo` entra como contexto; `TournamentUrl` es un identificador |
| `StartTime`/`EndTime` | No son predictores; ordenan el historial y la partición |
| `matchup_apertura` + historial | Se prueba durante la partida (notebook 03): no aporta |

**Regla para defender cualquier fila:** ¿esta columna existiría en el momento de
predecir? Si la respuesta ya está adentro (rating posterior, terminación, apertura de
Chess.com), no es una feature — es la respuesta escrita de otra forma.

**Parte B** (sección 10.8 del notebook): entran `balance_material` (η² 0,118) y
`dif_reloj_frac` (0,086); se evalúan en el modelo movilidad, capturas, jaques y
`material_no_peon_frac`; salen `turno_blancas` (constante) y `promociones` (casi
constante).

---

## Devolución de la Entrega 1 (resuelta)

> "Automatizar la elección de los jugadores y agregar variabilidad."

- Automatizar → `listar_jugadores` (`src/player_selection.py`), sin cuentas a mano,
  congelada y versionada en `config/jugadores_seleccionados.yaml`.
- Variabilidad → de 8 cuentas fijas (concentradas en `top_mundial`) a 100 jugadores,
  20 por banda, 18,4–21,8 % cada una; rango temporal 2013–2026; 7.204 → 80.697 partidas.
