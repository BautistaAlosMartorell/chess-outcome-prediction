# Plan de la Entrega 3 · Modelado (28/10/2026)

Qué hay, qué falta y cómo armar el notebook de modelado para que cumpla la consigna. Se
escribió el 22/10/2026 contrastando la consigna de la cátedra contra lo que ya está en
`main` (PRs #17–#24).

## La respuesta corta

**Sí: con los datos actuales se puede entrenar un modelo que predice durante la partida.**
`data/processed/partidas_cortes.parquet` ya es el dataset de entrenamiento: una fila por
`(GameUrl, corte_ply)` con lo que un observador veía en ese momento (material, jaques,
capturas, enroques, movilidad, relojes) y los targets `resultado` y `plies_restantes`.
Son 1.216.417 filas de 80.697 partidas, con un corte cada 5 plies del 0 (antes de
mover) al 120. El contexto fijo de la partida (ritmo, control de tiempo, torneo, rating
previo) se une desde el Parquet tidy por `GameUrl`.

Lo que **no** está es el modelado que pide la consigna. `notebooks/03_prediccion_en_vivo.ipynb`
es un **avance exploratorio**: un solo `HistGradientBoosting` por corte, con una única
partición train/test, sin validación cruzada, sin `Pipeline`, sin regresión logística,
sin `DummyClassifier` y sin ajuste de hiperparámetros. Sirve como evidencia de que hay
señal, pero no alcanza para aprobar.

## Consigna contra estado actual

| Pide la consigna | Estado | Qué falta |
|---|---|---|
| Métrica declarada antes de elegir | 🟡 nb03 usa log-loss + F1 macro | Declararla al principio del notebook nuevo, con el porqué |
| Piso con `DummyClassifier` / `DummyRegressor`, misma validación | 🟡 M0 = frecuencias por ritmo, sin CV | `DummyClassifier(strategy="prior")` dentro de la CV |
| Validación que imita el uso | 🟡 split temporal único | CV temporal **por partida** sobre train (ver abajo) |
| Todo dentro de un `Pipeline` | ❌ | `ColumnTransformer` + modelo; imputación, escalado y one-hot adentro |
| Regresión logística como referencia | ❌ | Agregar |
| ≥ 2 familias más, media y desvío | ❌ (solo HGB, sin desvío) | Árbol / random forest + HGB, con media ± desvío por fold |
| Ajuste de hiperparámetros con tabla completa | ❌ | Grilla chica sobre el elegido |
| Decisión sobre clases desparejas y su costo | ✅ nb03 §5.1 (pero medido en test) | Repetir la comparación en CV |
| Columnas probadas que no sirvieron | ✅ matchup (nb03 §7, medido en test) | Repetir la ablación en CV |
| Test mirado **una sola vez** | ❌ nb03 miró el test muchas veces | Ver "El test de nb03 ya se usó" |
| Matriz de confusión normalizada por fila y por columna + reporte por clase | ❌ | Agregar |
| Importancia por permutación / coeficientes | ✅ nb03 §6 | Rehacer sobre el modelo final |
| Notebook con semilla y salidas guardadas | ✅ nb03 | Igual en el nuevo |
| Modelo guardado para la app de la Entrega 4 | ❌ | `joblib.dump` del pipeline final + función de inferencia |

## Decisiones a tomar antes del primer modelo

### 1. Objetivo principal: `resultado` en cada corte, del 0 (antes de empezar) al 60

Clasificación de 3 clases (Gana Blancas / Empate / Gana Negras). `plies_restantes`
(regresión, MAE en plies) queda como segundo objetivo **si hay tiempo**: misma
validación, con `DummyRegressor(strategy="median")`, `LinearRegression` y HGB.

### 2. Un modelo para todos los cortes, con `corte_ply` como columna (recomendado)

La consigna dice que el modelo elegido es el que usa la app de la Entrega 4, y la app
necesita **un** artefacto. Se entrena un solo pipeline con todas las filas y `corte_ply`
como feature, y se **reporta** la métrica por corte (la curva de nb03 sigue siendo el
gráfico central). El corte 0 es la predicción antes de empezar: la pregunta "antes y
durante" se responde con una sola curva. La alternativa, un modelo por corte, son 25
artefactos y 25 tablas de comparación: más trabajo para la misma pregunta.

### 3. Métrica: log-loss principal, F1 macro y recall de Empate como secundarias

- **Log-loss**, porque la app muestra **probabilidades** en vivo y lo caro es mostrar
  80 % de victoria blanca en una partida que se pierde. La accuracy no ve eso.
- **F1 macro**, porque Empate es ~6 %: la accuracy premia no predecirlo nunca, y el F1
  macro sí lo ve.
- **Recall de Empate**, para que esa clase se vea explícitamente.

Ojo con la trampa ya encontrada en nb03: `log_loss` asume las columnas de probabilidad en
orden alfabético de etiqueta (`PROBA_ORDER`). Usar `model.classes_` siempre.

### 4. Validación: temporal y por partida

Las filas se repiten por partida (hasta 25 cortes) y por jugador (hasta 1.000 partidas), y el
uso es predecir partidas **futuras**. Entonces:

- **Test:** el mismo corte temporal de nb03 (percentil 80 de `StartTime`): train = partidas
  que terminaron antes, test = las que empezaron después, se descartan las que cruzan.
- **CV dentro de train:** `TimeSeriesSplit` (5 folds) **sobre partidas ordenadas por
  `StartTime`**, no sobre filas, y después se expande a sus cortes. Así todas las filas
  de una partida caen en el mismo fold y siempre se valida con partidas posteriores. Un
  splitter propio de pocas líneas que devuelva índices de filas alcanza; se le pasa a
  `cross_validate(cv=...)`.
- **Mostrar el contraste que pide la consigna:** el mismo modelo con `KFold` al azar
  sobre filas. Si da mejor, la diferencia es la fuga por compartir partidas entre
  pedazos. Es la respuesta lista para "¿qué pasaría si los armaras al azar?".
- Los jugadores aparecen en train y test: es el caso de uso (predecir las próximas
  partidas de jugadores conocidos). No mide generalización a jugadores nuevos; se
  declara como limitación.

### 5. Columnas y fugas

Entran: features del corte (`src/live_features.py`), `corte_ply`, `TimeClass`,
`tiempo_base_seg`, `incremento_seg`, `EsTorneo`, `elo_blancas_previo`,
`elo_negras_previo`.

Quedan afuera por fuga (ya justificado en nb03 §5): `WhiteElo`, `BlackElo`,
`diferencia_elo` (rating posterior), `Termination`, `cantidad_jugadas`, `EndTime`, ECO /
`familia_apertura` (el ECO de Chess.com mira hasta 40 plies).

**Features calculadas fuera del pipeline.** La consigna dice que lo calculado sobre el
dataset entero ya vio el test. El rating previo y las tasas históricas del matchup se
calculan afuera, pero **sólo con partidas terminadas antes de que empiece la actual**:
es lo mismo que tendría la app en ese momento, no ven el futuro. Hay que poder explicarlo
así en la defensa. Las features de posición y reloj se calculan dentro de cada partida,
sin mirar otras filas.

## El test de nb03 ya se usó

nb03 eligió `class_weight`, descartó el matchup y comparó modelos **mirando el test**.
Para la Entrega 3 eso cuenta como test gastado. Qué hacer:

- En el notebook nuevo, **todas** las decisiones (modelo, hiperparámetros, columnas,
  `class_weight`) se toman con la CV sobre train, y el test se mira una vez al final.
- En la defensa, decirlo de frente: "el notebook 03 fue exploratorio sobre el mismo
  período; en el 04 rehicimos las decisiones con CV y miramos el test una sola vez".
  Ocultarlo es peor que admitirlo.

## Estructura propuesta: `notebooks/04_modelado.ipynb`

1. **Planteo.** Objetivo, métrica y porqué, validación y porqué. Semilla
   (`config["processing"]["random_state"]`) pasada a todo lo que la acepte.
2. **Datos.** Cargar cortes + contexto + rating previo (reusar las celdas de nb03 §3–4);
   partición train/test temporal; splitter temporal por partida para la CV.
3. **Piso.** `DummyClassifier(strategy="prior")` en la CV: media ± desvío.
4. **Comparación** (mismas columnas, misma CV, media ± desvío de log-loss, F1 macro y
   recall de Empate):
   - `LogisticRegression` con `SimpleImputer(add_indicator=True)` + `StandardScaler` +
     `OneHotEncoder(TimeClass)`: la referencia.
   - `RandomForestClassifier` (o `DecisionTreeClassifier` si el bosque tarda demasiado
     con ~1 millón de filas de train: probar con `max_samples`).
   - `HistGradientBoostingClassifier` (maneja NaN de forma nativa; el imputador sobra pero
     no molesta).
   - Regla de la consigna: si el complejo no le gana al simple por más que el desvío, se
     queda el simple.
5. **Contraste de validación.** El elegido con `KFold` al azar sobre filas contra la CV
   temporal por partida.
6. **Ajuste.** Grilla chica sobre el elegido (para HGB: `learning_rate`, `max_leaf_nodes`,
   `min_samples_leaf`, `l2_regularization`), con la tabla completa.
7. **Clases desparejas.** Con y sin `class_weight="balanced"` en la CV: cuánto sube el
   recall de Empate y cuánto empeora la log-loss. Decidir según la métrica declarada.
8. **Columnas que no sirvieron.** Ablación en CV: sin rating previo, sin relojes, con
   matchup + tasas históricas. Tabla con y sin cada grupo.
9. **Modelo final, test una vez.** Métricas globales y **por corte** (la curva), matriz
   de confusión normalizada por fila y por columna, `classification_report`, importancia
   por permutación. Una confusión concreta explicada desde el ajedrez (p. ej. Empate
   confundido con victoria del bando con ventaja de material mínima).
10. **Guardar.** `joblib.dump(pipeline, "models/modelo_en_vivo.joblib")` (agregar
    `models/` al `.gitignore` o regenerarlo desde el notebook).
11. **(Si hay tiempo)** `plies_restantes`: mismo esquema con MAE.

## Para la Entrega 4 (dejar preparado)

- Función `predecir(pgn_parcial)` en `src/`: calcula las features con
  `game_cut_features()` en el ply actual y llama al pipeline guardado.
- Los cortes ya están densificados: uno cada 5 plies del 0 al 120 (corrida del
  22/10/2026). Un modelo con `corte_ply` como columna se puede **evaluar** en cualquier
  ply, y para la app (ply 47, por ejemplo) hay que mostrar en el notebook que en plies
  intermedios rinde como en los cortes vecinos.

## Qué contar en los minutos 0–2 ("qué cambió desde la Entrega 2")

- El profe marcó que no había features reales: ahora hay features de posición y reloj en
  cada corte, rating **previo** reconstruido (sin la fuga del rating posterior) y la
  marca de torneo.
- La unidad de modelado pasó de "una partida" a "(partida, corte de plies)". El Parquet
  tidy de la Entrega 1 sigue siendo una partida por fila; la tabla de cortes se deriva de
  él.
- Se respondió la pregunta del ELO máximo (±200, anexo del notebook 02) y se probó el
  histórico de matchups de apertura, que no aportó (resultado negativo documentado).

## Preguntas que van a caer, con dónde está la respuesta

| Pregunta | Respuesta / dónde |
|---|---|
| ¿Por qué esa métrica? | Decisión 3 |
| ¿Cuánto le gana al piso? | nb04 §3–4; en nb03 −20 % de log-loss al ply 60, empate hasta el ply 20 |
| ¿Por qué la validación así? ¿Y al azar? | Decisión 4 + nb04 §5 |
| ¿Por qué ese modelo y no uno más complejo? | nb04 §4, media ± desvío |
| Una confusión concreta | nb04 §9 |
| La columna que más pesa, ¿no es fuga? | Balance de material y relojes: se calculan sólo con jugadas hasta el corte, y hay un test que lo garantiza (`tests/test_live_features.py`) |
| ¿Qué probaron que no anduvo? | Matchup de apertura y sus tasas históricas; la predicción en el corte 0 (antes de empezar), que sin el rating del rival no le gana al piso |

## Limitaciones a declarar

- Sólo se conoce el rating previo de la cuenta seleccionada; el del rival queda NaN.
- Mismos jugadores en train y test: no mide generalización a jugadores nuevos.
- Muestra de 100 cuentas elegidas por banda de ELO, no Chess.com en general.
- Los cortes tardíos sólo describen partidas que llegan hasta ahí (sesgo de
  supervivencia; usar la población común de nb03 §5 al presentar la curva).
