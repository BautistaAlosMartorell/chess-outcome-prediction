# Plan de mejora del modelo de la app

Estado al 22/10/2026. Reemplaza la primera versión de este plan (queda en el historial
de git); la evidencia sigue en [la auditoría](../auditorias/modelo-app-2026-10-22.md) y
[el avance](../auditorias/avance-mejora-modelo-app-2026-10-22.md).

**Objetivo:** que la probabilidad que muestra la app responda bien al nivel de los dos
jugadores, sin romper lo que ya funciona en vivo. Se trabaja **en una rama aparte** desde
después de la Entrega 3 (28/10) o en paralelo sin tocar `main`; la decisión de promover
se toma **a más tardar el 31/10** para llegar a la Entrega 4 (04/11) con la app integrada
y tiempo para las visualizaciones.

La Entrega 3 se presenta con el modelo actual. Si este plan mejora el modelo, en la
Entrega 4 se muestra como la corrección posterior, con el antes y el después: la consigna
dice que el modelo de la Entrega 3 es el que usa la app, así que el cambio se declara.

## Qué se sabe

| Hallazgo | Número | Consecuencia |
|---|---|---|
| Partidas de train con rating previo de los dos lados | 185 / 80.314 (0,23 %) | El modelo casi nunca vio una diferencia de rating real |
| Con ratings de rivales que ya están en los JSON descargados | 33.496 / 80.314 (41,7 %) | La mayor parte del arreglo no necesita red |
| En la app, la diferencia de rating de −200 a +200 | Baja P(gana blancas) | Inversión visible en la demo |
| Referencia logística de rating, solo cuentas propias → con rivales | 0,892 → 0,868 de log-loss CV (−0,024 ± 0,006, mejora en 5/5 folds) | Hay señal; falta probarla en el bosque y en vivo |
| Antigüedad del rating de un rival | Mediana < 1 día; p95 de 692 días (train) | Hace falta la antigüedad como columna |
| Dama ganada | +9,02 / +10,34 puntos frente a >15 exigidos | Fallo conocido; no es objetivo de este plan |

Por qué pasa: el rating que trae una partida es el posterior. El previo de una cuenta se
reconstruye con sus cierres anteriores, y sólo se descargaron los archivos de las 120
cuentas, no los de sus rivales. Pero cada partida descargada también trae el rating del
rival al terminar: es una observación del rating del rival, que hoy se descarta.

## Qué cambia respecto del plan anterior

| Plan anterior | Ahora | Por qué |
|---|---|---|
| Descargar rivales a un salto, con piloto estratificado | **Fuera**, salvo que la fase 1 deje una banda sin cobertura | Los JSON existentes ya dan 41,7 %; descargar cambia el dataset a días de la Entrega 4 |
| Evaluación temporal nueva, reservada | **Fuera** | Requiere bajar meses nuevos. Se elige sólo por CV con los mismos folds del 04 y el test se sigue declarando reusado |
| Banderas de procedencia (propio/incidental) como columnas | **No entran al modelo** | En la app los dos ratings salen de archivos propios: la bandera sería constante en uso y el modelo aprendería algo que nunca va a ver. Se usa la antigüedad, que la app sí calcula |
| Brier, calibración por subgrupo, controles ±800, tolerancias de promoción múltiples | **Fuera** | No lo pide la consigna; se usan la métrica y la regla del 04 |
| Ablación de pausas y sesión | **Se mantiene**, como una sola variante | Barata en el mismo arnés y la auditoría la marcó |
| Reentrenar primero, agregar diferencia después | **Se mantiene** | Aísla qué parte de la mejora viene de los datos y cuál de las columnas |

## Reglas

- Mismo arnés que el 04: `temporal_game_folds` de `src/model_validation.py`, cinco folds
  temporales por partida, semilla 42, log-loss como métrica y la regla del 04: una
  variante gana si mejora el log-loss global por más que el desvío de las diferencias
  pareadas **y no empeora el corte 0** por más que su desvío.
- Todo dentro del Pipeline: los ratings de rivales se derivan en `PlayerHistoryTransformer`,
  con cierres estrictamente anteriores al inicio. Nada se calcula sobre el dataset entero.
- El test del 04 no decide nada. Se mira una vez, con la variante ya elegida, y se dice que
  el período ya estaba usado.
- No se toca el dataset oficial, `config/jugadores_seleccionados.yaml`, el DAG ni
  `download.until_month`. No se baja el umbral del test de dama.
- `main` y el notebook 04 no cambian hasta que una variante se promueva.

## Fases

### 0 · Línea base reproducible (medio día)

Rama `feat/ratings-de-rivales` desde `main` con el PR #32 mergeado. Script
`src/experiment_rival_ratings.py` que arma el bosque final del 04 (40 columnas,
`max_features=0.3`, `min_samples_leaf=20`) y lo evalúa en los cinco folds.

Salida: log-loss por fold, global y en el corte 0, más la grilla de control de rating
(ver fase 3). **Criterio para seguir:** reproduce 0,830 ± 0,023 de la grilla del 04
(mismo desvío de sklearn) con diferencia menor a 0,001. Si no, se arregla el arnés
antes de comparar nada.

### 1 · Ratings de rivales dentro del historial (uno o dos días)

- En `src/rating_history.py`, una función que, además de las partidas propias, devuelva
  una observación **de sólo rating** del rival en cada partida descargada (rating al
  cerrar, ritmo, cierre, inicio, `GameUrl`). Deduplicar por cuenta y `GameUrl`.
- En `player_history_payloads` y en `_timeline`, el rating previo y su tendencia consultan
  todas las observaciones del mismo ritmo; **forma, racha, sesión y estilo siguen usando
  sólo partidas propias**, porque de un rival se ve una partida suelta, no su secuencia.
- Columna nueva por color: `antiguedad_rating_dias` (inicio actual menos el cierre de la
  observación usada). En la app se calcula igual desde `api/chesscom.historial`.
- Tests nuevos en `tests/test_history_transformer.py`: la propia partida objetivo aparece
  como observación del rival y **no** se usa (cierra después del inicio); un cierre
  simultáneo no se usa; una aparición incidental no cambia la forma; duplicados entre
  archivos se cuentan una vez; antigüedad correcta.

**Criterio para seguir:** el transformer reproduce la cobertura del piloto
(33.496 / 80.314 en train con los dos ratings) y pasan todos los tests salvo el de dama.

### 2 · Columnas de nivel relativo (medio día)

- `diferencia_elo_previa` sólo si se conocen los dos ratings; si falta uno, queda vacía
  y el imputador agrega su indicador. No se resta un rating imputado.
- `elo_promedio_previo` con los ratings conocidos.

### 3 · Comparación en los mismos folds (un día, contando corridas)

| Variante | Qué tiene |
|---|---|
| A | Bosque actual (línea base de la fase 0) |
| B | A + ratings de rivales y antigüedad |
| C | B + diferencia y promedio de rating |
| D | La mejor entre B y C, sin `minutos_desde_anterior` ni `partidas_sesion` |

Mismos hiperparámetros del 04: no se abre una grilla nueva salvo que la variante elegida
cambie de familia. Para cada variante: log-loss global y en el corte 0, diferencia pareada
contra A con su desvío, y la grilla de control:

- Posición inicial, ambos ratings conocidos, antigüedad de un día, forma vacía.
- Rating promedio 1200, 1800, 2400 y 3000; diferencia −400, −200, 0, +200 y +400; los tres
  ritmos donde haya datos.
- **Se exige que P(gana blancas) no baje al subir la diferencia.** Se informan las
  inversiones; no se fija un porcentaje esperado.

**Decisión (a más tardar el 31/10):** se promueve la mejor variante que gane a A con la
regla del 04 y pase la grilla de control. Si ninguna gana, se queda A y se documenta.

### 4a · Si se promueve (uno o dos días)

- Notebook 04: la variante entra como un grupo más en §7 (columnas con y sin) y en el
  modelo final; Restart & Run All y salidas guardadas. Se regenera `models/modelo_en_vivo.joblib`
  con una copia del anterior en `models/baselines/`.
- `api/main.py`: que la app pase la antigüedad. Test de paridad entre el camino de
  entrenamiento y la API para una partida real.
- `tests/test_model_realism.py`: agregar la grilla de control como prueba.
- Actualizar en el mismo commit README, `plan-entrega-3.md`, `plan-coherencia.md`,
  CHANGELOG, la skill de entregas y el texto de la app ("Qué mira el modelo").

### 4b · Si no se promueve (medio día)

Se documenta en el 04 como columna probada que no sirvió, con el número, y en la app se
avisa cuando el modelo no tiene el rating de uno de los dos lados.

## Riesgos que hay que mirar

- **Ratings viejos:** un rival observado hace dos años no informa su nivel actual. La
  antigüedad entra como columna; si el bosque no la aprovecha, se prueba descartar
  observaciones de más de 30 días (ya medido en la referencia: 0,874 frente a 0,868).
- **Partidas antiguas en la app:** la app baja hasta tres archivos mensuales recientes;
  al analizar una partida vieja puede no haber observaciones previas al inicio. Se declara
  en la interfaz como contexto faltante.
- **Tiempo de corrida:** el 04 tarda 37 minutos; cada variante del arnés, una fracción.
  No se corre el notebook entero hasta tener la variante elegida.

## Fuera de este plan, pero en la Entrega 4

La Entrega 4 también pide **visualizaciones que comuniquen los hallazgos**, no sólo la app.
Reservar al menos dos días para eso; este plan no las cubre.

## Para retomar en otra conversación

> Leé AGENTS.md, las skills de `skills/` y `docs/entregas/plan-mejora-modelo-app.md`.
> Empezá por la fase 0 en una rama `feat/ratings-de-rivales` desde `main`. Seguí las
> reglas del plan: mismos folds y regla del 04, todo dentro del Pipeline, sin tocar
> el dataset oficial ni el notebook 04 hasta decidir en la fase 3. Pedí confirmación
> antes de push, PR y merge.
