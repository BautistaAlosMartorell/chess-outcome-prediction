# Devolución de la Entrega 2 y cómo se resolvió

La consigna de la Entrega 3 pide traer **"lo que te marcamos en la Entrega 2, resuelto, o
con una explicación de por qué no se pudo"**, y contarlo en los minutos 0–2 ("qué cambió").
Este documento junta los cuatro pedidos de la devolución (25/09/2026), qué se hizo con
cada uno, dónde está en el repo y qué número lo respalda. Todas las cifras salen de la
corrida oficial `manual__2026-10-22T18:56:28` (100.396 partidas) y de los notebooks
ejecutados.

## Resumen para los minutos 0–2

> Nos pidieron predecir durante la partida y no sólo antes: cambiamos la unidad a
> partida × corte de plies (1.559.622 filas) y entrenamos un solo modelo que predice en
> cualquier jugada. Nos pidieron la diferencia de ELO máxima que permite Chess.com:
> el 91,39 % de las partidas sujetas al límite de ±200 lo cumple, y el 62,1 % de las
> excepciones son de torneo, un campo que el pipeline no guardaba y ahora sí. Y nos
> pidieron el histórico de quién gana según el cruce de aperturas: lo construimos sin
> fuga, lo probamos con validación cruzada y no mejoró al modelo, así que no entra.

| # | Pedido | Qué se hizo | Resultado | Dónde |
|---|---|---|---|---|
| 1 | Diferencia de ELO máxima que permite el sistema | Anexo de matchmaking; el pipeline guarda `TournamentUrl` y `EsTorneo` | 91,39 % cumple ±200; 62,1 % de las excepciones son de torneo | Notebook 02, anexo final; `src/clean_data.py` |
| 2 | Varias filas por partida, con datos a distintos tiempos, para predecir durante la partida | Tabla de cortes: una fila por partida y corte, con posición y relojes | 1.559.622 filas, 25 cortes (0 a 120 cada 5) | `src/live_features.py`, tarea `construir_dataset_cortes` del DAG |
| 3 | Cambiar qué es una fila (Entrega 1) | Unidad de modelado: partida × corte. La tabla tidy queda con una fila por partida | Un solo modelo con el corte como columna; la app predice en cada jugada | Notebooks 02 (Parte B), 03 y 04 |
| 4 | Histórico de quién suele ganar entre familias; matchup de tipo de familias | `matchup_apertura` (primera jugada × respuesta) y sus tasas históricas causales | No mejora: +0,0017 ± 0,0011 de log-loss en CV, no entra | `src/feature_engineering.py`, notebooks 03 y 04 §7 |

## 1 · Diferencia de ELO máxima que permite el sistema

**El pedido.** Analizar cuál es la diferencia de ELO máxima que permite Chess.com al armar
una partida.

**Qué se hizo.** Un anexo al final del notebook 02 ("Diferencia de ELO y matchmaking").
Chess.com documenta un límite de **±200 puntos** en el emparejamiento automático para
jugadores con rating menor a 2500 en bullet/blitz o menor a 2000 en rapid; por encima no
publica límite, y los torneos y desafíos directos no lo tienen. Se marcó cada partida como
"sujeta al límite" si al menos uno de los dos está debajo del umbral de su ritmo, y se
comparó cuántas superan ±200 contra las no sujetas (χ², odds ratio, V de Cramér y un
intervalo con bootstrap **por jugador**, porque las partidas de una cuenta no son
independientes).

**Resultado.**

- De 61.719 partidas sujetas al límite, 5.311 lo superan: **el 91,39 % lo cumple**.
- La dirección es la esperada en los tres ritmos: hay más brechas grandes en el grupo no
  sujeto (bullet 8,84 % frente a 20,01 %; blitz 9,76 % frente a 13,33 %; rapid 5,14 %
  frente a 25,54 %). El intervalo por jugador excluye cero en el global y en rapid; en
  bullet y blitz sigue siendo incierto.
- **Hallazgo:** los JSON crudos traen un campo `tournament` que el pipeline descartaba.
  Hay 11.140 partidas de torneo, y **3.300 de las 5.311 excepciones (62,1 %) son de
  torneo**, un mecanismo sin límite. Sin torneos, el grupo sujeto queda en 3,54 % fuera de
  ±200 contra 10,37 % del no sujeto.

**Qué cambió en el proyecto.** `src/clean_data.py` guarda `TournamentUrl` y deriva
`EsTorneo`; el DAG verifica que coincidan. `EsTorneo` entra al modelo como contexto previo
a la partida.

**Límites.** Es una cota inferior de partidas armadas fuera del emparejamiento automático;
el rating del Parquet es el posterior (unos pocos puntos de ruido en el corte de 200) y no
se conoce el mecanismo de las excepciones que no son de torneo. No es evidencia causal.

## 2 y 3 · Varias filas por partida y predecir durante la partida

**El pedido.** Pasar de una fila por partida a varias, con los datos en distintos momentos
(cortes por cantidad de movimientos), para predecir **durante** la partida y no sólo antes.

**Qué se hizo.**

- **Unidad de modelado: partida × corte de plies.** Un corte cada 5 plies, del 0 (antes de
  mover) al 120 (`config.yaml → live_prediction.cortes_ply`). Una partida aporta una fila
  por cada corte anterior a su final.
- **Tabla nueva, `partidas_cortes.parquet`.** La arma la tarea `construir_dataset_cortes`
  del DAG con `src/live_features.py`: reproduce cada partida con python-chess desde el PGN
  crudo (el único lugar con los relojes) y guarda la posición y los relojes en cada corte:
  material, capturas, jaques, enroques, movilidad, reloj de cada lado, gasto reciente, etc.
  Cada feature usa sólo las jugadas hasta el corte; un test comprueba que cambiar la
  continuación no las altera.
- **La tabla tidy no se rompe.** `partidas_ajedrez_clean.parquet` sigue con una fila por
  partida (clave `GameUrl`, la de la Entrega 1). La de cortes es derivada, con clave
  `(GameUrl, corte_ply)`; el DAG falla si la clave se repite o si los plies reproducidos no
  coinciden con `cantidad_jugadas`. El contexto fijo de la partida se une por `GameUrl`
  con su assert anti fan-out.
- **Objetivo durante la partida.** `resultado` en cada corte y, como secundario,
  `plies_restantes` (cuánto falta).

**Resultado.**

- 1.559.622 filas de 100.396 partidas en 25 cortes (547.555 en los cortes de referencia
  0/10/20/30/40/60).
- Notebook 02, Parte B: hipótesis sobre la tabla de cortes (material y reloj tienen señal
  tardía).
- Notebook 04: **un solo modelo** con `corte_ply` como columna. La validación separa por
  partida (los 25 cortes de una partida nunca quedan de los dos lados) y por tiempo. Mejora
  al piso en 5,17 % antes de mover, 19,58 % al ply 60 y 38,86 % al ply 120.
- La app predice en **cualquier jugada**, no sólo en los cortes: `predecir()` reproduce las
  probabilidades del dataset en los plies de corte (tolerancia 1e-9), y en los plies
  intermedios la log-loss es comparable a la de los cortes vecinos.

## 4 · Histórico de quién gana según el cruce de aperturas

**El pedido.** El histórico de quién suele ganar entre familias de apertura: un "matchup"
entre el tipo de apertura de cada lado.

**Qué se hizo.**

- **`matchup_apertura`:** la primera jugada de blancas y la primera respuesta de negras
  (`e4-e5`, `d4-Nf6`), con 17 combinaciones frecuentes más `otra` (cubren el 79,26 % de
  las partidas). La lista está congelada en `config.yaml`.
- **Tasas históricas** (`tasa_blancas_hist`, `tasa_tablas_hist`, `tasa_negras_hist`): para
  cada partida, cómo terminaron las del mismo matchup y ritmo que **terminaron antes de que
  empezara** (`EndTime < StartTime`). Con menos de 30 previas quedan vacías (1.620 partidas,
  1,61 %). Tests: solapamientos, empates de horario, orden de filas e invariancia al futuro.

**Por qué no la familia ECO.** `familia_apertura` es un único valor por partida, así que no
permite un "blancas contra negras". Además Chess.com asigna el ECO mirando la línea
completa (mediana de 10 plies, hasta 40): usarla en un corte temprano revela jugadas
futuras. El matchup sólo necesita los plies 1 y 2. Tampoco sirve el repertorio de cada
jugador: 44.729 de los 54.998 jugadores aparecen una sola vez.

**Resultado: probado y no anduvo.**

- Notebook 03 (exploración): las tasas históricas no ordenan la victoria blanca real por
  quintil, y agregarlas cambia la log-loss entre −0,003 y +0,001 según el corte.
- Notebook 04 §7 (validación cruzada, regla declarada): **+0,0017 ± 0,0011** global y
  +0,0001 ± 0,0008 en el corte 0. No mejora, así que **no entra** al modelo final.

**Cómo se defiende.** La consigna de la Entrega 3 pide "las columnas que probaste y no
sirvieron, con el número con y sin cada una". El matchup es exactamente eso: se construyó
sin fuga, se midió con la misma validación que todo lo demás y se informa que no aportó.

## Correcciones propias, posteriores a la devolución

No las pidió la devolución, pero cambian lo que se presenta y conviene contarlas:

- **Historial dentro del Pipeline.** Rating previo, forma y estilo se calculaban afuera.
  La consigna de la Entrega 3 pide que las columnas derivadas estén "adentro del objeto que
  se entrena": ahora las calcula `PlayerHistoryTransformer`, el primer paso del Pipeline.
- **Cierre estrictamente anterior al inicio.** Ordenar por cierre y usar `shift()` no
  garantizaba que la partida anterior hubiera terminado: 1.345 observaciones no cumplían.
  El transformer exige `EndTime < StartTime`.
- **Rating de los rivales** (relacionado con el punto 1). Sólo 185 de 80.314 partidas de
  train tenían el rating previo de los dos lados, y en la app más diferencia de rating
  podía bajar la probabilidad del favorito. Cada partida descargada ya traía el rating del
  rival: usándolo, 41,7 % de train tiene los dos lados, entran la diferencia, el promedio y
  la antigüedad del rating, y la respuesta a la diferencia queda en la dirección correcta.
  Detalle en [`plan-mejora-modelo-app.md`](plan-mejora-modelo-app.md) y en el antes y
  después de [`plan-entrega-3.md`](plan-entrega-3.md).
