# Entrega 3 · Modelado (28/10/2026)

Cómo cumple el proyecto la consigna de la cátedra (transcripta en
[`consigna-entrega-3.md`](consigna-entrega-3.md)): qué se decidió, dónde está cada cosa en
`notebooks/04_modelado.ipynb` y qué dio. Empezó el 22/10/2026 como plan, contrastando la
consigna contra lo que había en `main`; quedó ejecutado ese mismo día.

## La respuesta corta

Un **random forest** predice el resultado de una partida en cualquier momento, a partir de
la posición y los relojes, con un solo modelo para todos los cortes (`corte_ply` es una
columna). En el test le gana al piso por un 12 % de log-loss (0,799 contra 0,909). La
ganancia es nula antes de mover y crece con la partida: 19 % al ply 60 y 40 % al 120. Es
el modelo que va a usar la app de la Entrega 4: se guarda en `models/modelo_en_vivo.joblib`,
y `predecir()` (`src/predict.py`) lo aplica jugada a jugada.

`notebooks/03_prediccion_en_vivo.ipynb` queda como **avance exploratorio**: un modelo por
corte, una sola partición y decisiones tomadas mirando el test. El 04 rehízo todas las
decisiones con validación cruzada y miró el test una sola vez.

## Consigna → notebook 04

| Pide la consigna | Dónde | Qué dio |
|---|---|---|
| Métrica declarada antes de elegir | §1 | Log-loss (la app muestra probabilidades); F1 macro y recall de Empate como secundarias |
| Piso, con la misma validación | §3 | `DummyClassifier(strategy="prior")`: 0,923 en validación cruzada |
| Validación que imita el uso, y el test con el mismo criterio | §1–2 | `TimeSeriesSplit` sobre partidas ordenadas por inicio (`src/model_validation.py`); test = partidas posteriores al percentil 80 de `StartTime` |
| Qué pasa si los pedazos se arman al azar | §4 | Filas al azar 0,810 contra 0,821 por partida: 0,011 de fuga. Por jugador, 0,824 |
| Todo adentro de un pipeline | §1, §3 | Imputación, escalado y one-hot adentro. Rating previo, forma y matchup se calculan afuera sólo con partidas anteriores |
| Modelo simple primero + ≥ 2 familias, media y desvío | §3 | Logística 0,854 ± 0,018 · random forest 0,835 ± 0,017 · gradient boosting 0,890 ± 0,099 |
| Si el complejo no le gana al simple por más que el desvío, queda el simple | §3 | El bosque le gana a la logística por 0,019 ± 0,0035 pedazo a pedazo: queda el bosque |
| Ajuste del elegido, tabla completa | §5 | `GridSearchCV`: `max_features=0.3`, `min_samples_leaf=20`, 0,829 ± 0,016 |
| Clases desparejas: qué se decidió y qué costó | §6 | `class_weight="balanced"` sube el recall de Empate de 0,01 a 0,39 y empeora la log-loss en 0,137: no se balancea |
| Columnas que no sirvieron, con y sin | §7 | Relojes: +0,036 sin ellos. Rating previo, forma reciente y matchup: dentro del ruido |
| Test mirado una vez | §8 | Log-loss 0,799 contra 0,909 del piso |
| Matriz por fila y por columna + reporte por clase | §8 | El empate casi no se predice (recall 4 %); sesgo hacia blancas en los cortes tempranos |
| En qué se apoya | §8 | Importancia por permutación: `balance_material`, después `diferencia_reloj_seg` |
| Notebook con semilla y salidas guardadas | todo | `random_state` del config en muestras, modelos y `KFold`; ~20 minutos |
| El modelo es el de la app | §9, §11 | `predecir()` reproduce las predicciones del dataset; los plies intermedios rinden igual que los cortes |

La duración restante (`plies_restantes`) está en §10 como objetivo secundario: MAE de 21
plies contra 26 del piso, con lo real contra lo predicho y el tramo donde más se erra.

## Decisiones

### 1. Objetivo: `resultado` en cada corte, del 0 (antes de empezar) al 120

Clasificación de 3 clases (Gana Blancas / Empate / Gana Negras). `plies_restantes` es el
objetivo secundario (regresión, MAE en plies).

### 2. Un modelo para todos los cortes, con `corte_ply` como columna

La app necesita **un** artefacto. Se entrena un solo pipeline con todos los cortes y se
**reporta** la métrica por corte: la pregunta "antes y durante" es una sola curva. Los
cortes son uno cada 5 plies del 0 al 120; §9 muestra que en los plies intermedios el modelo
rinde como en los vecinos, así que la app puede predecir en cada jugada.

### 3. Métrica: log-loss principal, F1 macro y recall de Empate como secundarias

- **Log-loss**, porque la app muestra **probabilidades** en vivo y lo caro es mostrar
  80 % de victoria blanca en una partida que se pierde. La accuracy no ve eso.
- **F1 macro**, porque Empate es ~6 %: la accuracy premia no predecirlo nunca, y el F1
  macro sí lo ve.
- **Recall de Empate**, para que esa clase se vea explícitamente.

`log_loss` asume las columnas de probabilidad en el orden de `model.classes_`: el notebook
usa siempre `classes_` (o `labels=` explícito en los scorers).

### 4. Validación: temporal y por partida

Las filas se repiten por partida (hasta 25 cortes), en el tiempo y por jugador (hasta
1.000 partidas), y el uso es predecir partidas **futuras** de jugadores con historial:

- **Test:** partidas que empiezan después del percentil 80 de `StartTime`; train, las que
  terminaron antes; se descarta la que cruza.
- **Validación cruzada dentro de train:** `TimeSeriesSplit` (5 pedazos) sobre partidas
  ordenadas por `StartTime`, expandido a sus cortes, pasado a `cross_validate` y
  `GridSearchCV` como `cv=`. Sobre una muestra del 25 % de las partidas de train, por costo.
- **El mismo jugador puede estar de los dos lados, a propósito** (es el caso de uso). §4
  mide qué pasa con jugadores nuevos (`GroupKFold` por jugador): 0,824 contra 0,821, casi
  igual.

### 5. Columnas y fugas

Entran: features del corte (`src/live_features.py`), `corte_ply`, `TimeClass`,
`tiempo_base_seg`, `incremento_seg`, `EsTorneo`, `elo_blancas_previo`,
`elo_negras_previo` (`PRE_GAME + LIVE` en `src/predict.py`). Se probaron y no entraron: la
forma reciente (`src/rating_history.py`) y el matchup de apertura.

Quedan afuera por fuga: `WhiteElo`, `BlackElo` y sus derivadas (rating posterior),
`Termination`, `cantidad_jugadas`, `EndTime`, ECO / `familia_apertura` (el ECO de
Chess.com mira hasta 40 plies).

**Features calculadas fuera del pipeline.** La consigna dice que lo calculado sobre el
dataset entero ya vio el test. El rating previo, la forma reciente y las tasas del
matchup se calculan afuera, pero **sólo con partidas terminadas antes de que empiece la
actual**: no usan ninguna estadística de la tabla entera, darían lo mismo sin el test y
son lo mismo que tendría la app en ese momento. Lo garantizan
`test_prior_rating_is_the_rating_after_the_previous_own_game` y
`test_recent_form_only_looks_at_earlier_games`.

## El test de nb03 ya se usó

nb03 eligió `class_weight`, descartó el matchup y comparó modelos **mirando el test**. En
la defensa, decirlo de frente: "el notebook 03 fue exploratorio sobre el mismo período; en
el 04 rehicimos las decisiones con validación cruzada y miramos el test una sola vez".
Ocultarlo es peor que admitirlo.

## Qué contar en los minutos 0–2 ("qué cambió desde la Entrega 2")

- El profe marcó que no había features reales: ahora hay features de posición y reloj en
  cada corte, rating **previo** reconstruido (sin la fuga del rating posterior), la marca
  de torneo y la forma reciente de cada jugador.
- La unidad de modelado pasó de "una partida" a "(partida, corte de plies)". El Parquet
  tidy de la Entrega 1 sigue siendo una partida por fila; la tabla de cortes se deriva de
  él.

## Preguntas que van a caer, con la respuesta

| Pregunta | Respuesta (notebook 04) |
|---|---|
| ¿Por qué esa métrica? | La app muestra probabilidades; el error caro es una probabilidad muy segura y equivocada, y la log-loss lo castiga (§1) |
| ¿Cuánto le gana al piso? | 12 % en todo el test; nada antes de mover; 19 % al ply 60 y 40 % al 120 (§8) |
| ¿Por qué la validación así? ¿Y al azar? | Filas que se repiten por partida y uso futuro → temporal por partida. Al azar da 0,011 mejor de lo real (§4) |
| ¿Por qué ese modelo y no uno más complejo? | El bosque le gana a la logística por 0,019 ± 0,0035; el boosting por defecto memoriza y no le gana (§3) |
| Una confusión concreta | El bando con más material que pierde: el 65 % de los errores de ganador desde el ply 60; la mitad terminan por tiempo (52 %, contra 43 % del total) (§8) |
| La columna que más pesa, ¿no es fuga? | `balance_material`: se calcula sólo con las jugadas hasta el corte (`test_features_ignore_everything_after_the_cut`), y en el corte 0 el modelo empata con el piso (§8) |
| ¿Qué probaron que no anduvo? | Predecir antes de empezar, la forma reciente, el rating previo, el matchup, balancear el empate y el boosting por defecto (§12) |

## Limitaciones a declarar

- Sólo se conoce el rating previo (y la forma) de la cuenta seleccionada; el del rival
  queda NaN.
- Muestra de 100 cuentas elegidas por banda de ELO, no Chess.com en general.
- Entrenado con cortes hasta el ply 120; más allá extrapola (el 10 % de las partidas dura
  más).
- Los cortes tardíos sólo describen partidas que llegan hasta ahí (sesgo de
  supervivencia): la comparación justa es la población común de §8.
