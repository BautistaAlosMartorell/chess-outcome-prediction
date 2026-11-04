# Devolución de la Entrega 3 y cómo se resolvió

La consigna de la Entrega 4 pide traer **"lo que te marcamos en la Entrega 3, resuelto, o
con una explicación de por qué no se pudo"**, y contarlo en los minutos 0–2 ("qué
cambió", dos oraciones). Este documento junta los pedidos de la devolución, qué se hizo
con cada uno, dónde está en el repo y qué número lo respalda.

Devolución del profesor, 30/10/2026.

## Resumen para los minutos 0–2

> Ahora medimos el modelo tramo por tramo de la partida y en decisión fija: acierta el
> 54 % antes de mover y el 71 % después del ply 95, siempre por encima del piso y de la
> regla "gana el que va arriba en material". La importancia por tramo dice en qué
> fijarse (antes de empezar, el rating; durante la partida, el material y después el
> reloj), y una búsqueda aleatoria de hiperparámetros dejó un modelo que reacciona como
> se espera cuando alguien gana la dama.

| # | Pedido | Qué se hizo | Resultado | Dónde |
|---|---|---|---|---|
| 1 | Agrupar las filas por tiempo (tramos de movimientos) y calcular las métricas por grupo; mostrar cómo cambian | Seis tramos de plies (0, 5–20, 25–40, 45–60, 65–90, 95–120) con log-loss, accuracy, F1 macro y recall de tablas | Accuracy 54,1 % → 70,9 %; log-loss 0,853 → 0,688 | Notebook 04 §8 "Por tramo de jugadas"; `src/metricas_tramo.py`; app `/proyecto#acierta` |
| 2 | Mostrar la accuracy y métricas de decisión fija ("el modelo dijo esto, ¿acertó?") | Accuracy al lado de la log-loss en todas las tablas de test, con dos referencias: el piso (siempre gana blancas) y la regla del material | Test: 62,3 % contra 47,5 % del piso; la regla del material llega como mucho a 62,2 % al final, casi nueve puntos debajo del modelo | Notebook 04 §1, §8 y §12; app `/proyecto` |
| 3 | Matriz de confusión | Además de la global, una por tramo | Recall de blancas/negras 69,4 %/45,7 % antes de mover → 84,1 %/82,2 % al final; tablas 0 % → 16,2 % | Notebook 04 §8; app `/proyecto#acierta` (menú por tramo) |
| 4 | Evolución de la importancia de las columnas a medida que avanza la partida ("en qué fijarme") | Importancia por permutación dentro de cada tramo, en log-loss y en accuracy | Rating: 0,0464 → 0,0059. Material: 0 → 0,3213. Reloj: 0 → 0,1396 | Notebook 04 §8 "Cómo cambia la importancia"; app `/proyecto#en-que-se-fija` |
| 5 | Mostrar cómo evolucionaron las hipótesis a lo largo del proyecto (Entrega 4) | Tabla por hipótesis: veredicto del EDA (Entrega 2), puesto en la importancia del modelo (Entrega 3) y puesto por tramo (Entrega 4) | H1 (rating) inconclusa en el EDA → 1.º antes de mover; H1′ (material) y H2′ (reloj) → 1.º y 2.º al final | App `/proyecto#hipotesis`; `src/build_app.py` (`hipotesis_en_el_modelo`) |

## Mejoras del modelo, a partir del diagnóstico

Al revisar si el modelo daba resultados realistas se encontró que, en promedio, las
probabilidades estaban bien, pero se quedaba corto con ventajas grandes: con 9 o más
puntos de material entre los plies 35 y 60 le daba 73,8 % al que iba arriba, y ese
ganaba el 80,2 %. El test de dama ganada fallaba (+11,6 y +6,3 puntos contra +15).

| Cambio | Qué se hizo | Resultado | Dónde |
|---|---|---|---|
| Búsqueda aleatoria de hiperparámetros | `RandomizedSearchCV` con 15 sorteos en el bosque y 15 en el boosting, con los mismos pedazos temporales; la grilla de la Entrega 3 y el boosting por defecto como candidatos fijos | Bosque: 0,8297 contra 0,8301. El boosting ajustado no le gana (−0,0006 ± 0,0082): queda el bosque, con `max_features=0.5` y `max_samples=0.2` | Notebook 04 §5 |
| Columnas, con los hiperparámetros nuevos | La misma regla de ablación, rehecha | Entran material colgado, peones pasados y movilidad: 46 columnas. Después, con las columnas de mate (abajo), quedan 48: entran los ataques al rey y salen los peones pasados | Notebook 04 §7 |
| Calibración de las probabilidades | Temperatura global, por tramo e isotónica, cada una ajustada con pedazos anteriores al que se mide | Ninguna pasa la regla (la mejor, −0,0012 ± 0,0018): queda sin calibrar | Notebook 04 §7b; `src/calibracion.py` |
| Resultado | — | Test: log-loss 0,791 (antes 0,795), 62,2 % de aciertos. Dama ganada: +24,1 y +24,0 puntos: **pasa**. El modelo pesa 91 MB (antes 132). Con la regla de mate (abajo): 0,790, 62,3 % y dama ganada +27,2 y +25,6 | `tests/test_model_realism.py` |

## Error encontrado en la app: el rey solo que "podía ganar"

**Qué se vio.** En Analizar, al final de una partida blitz 3+0 de MagnusCarlsen
(`https://www.chess.com/game/live/186517294506`), las negras tenían dama, torre y alfil contra el
rey solo de Magnus y ganaron por mate en el ply 128. Con 1,3 segundos en el reloj de las negras, el
modelo de 46 columnas les daba 37 % de ganar, 47 % de tablas y **17 % a Magnus**.

**Por qué estaba mal.** Con rey solo (o rey y una pieza menor) no se puede dar mate, y si al rival
se le cae la bandera la partida es tablas. Que gane el rey solo es imposible, no improbable: en el
dataset hay 10.400 cortes con un lado sin material para dar mate y ese lado no ganó nunca. El modelo
no tenía una columna que lo dijera. Veía "reloj casi en cero" y repetía lo que pasa en general
cuando a alguien se le acaba el tiempo, que suele perder.

**Qué no era.** No era la diferencia de rating ni el ply más allá del 120: igualar los ratings o
mover la posición al ply 120 no cambiaba nada. Darle 30 s a las negras subía su probabilidad al
60 %. Era el reloj, sin saber que el rival no podía ganar.

**Qué se hizo.**

| Cambio | Dónde |
|---|---|
| Dos columnas nuevas en la tabla de cortes, `puede_dar_mate_blancas` y `puede_dar_mate_negras`: si las piezas del tablero en ese corte alcanzan para dar mate (`python-chess`, `has_insufficient_material`). No es fuga: mira sólo la posición actual, igual que el material. | `src/live_features.py`; la tabla de cortes se rehízo con la misma función del paso `construir_dataset_cortes` del DAG (mismas 1.559.622 filas; el resto de las columnas, idéntico) |
| Un chequeo sobre todo el dataset: un lado sin material para dar mate nunca gana. Si aparece un caso, el notebook falla. | Notebook 04 §2 |
| Una regla después del modelo (`ConReglaDeMate`): la victoria imposible queda en 0 y el resto se reparte en proporción. Va dentro del modelo guardado, así el notebook, la API y la app dan lo mismo. | `src/reglas.py`; notebook 04 §8 |
| Pruebas: la columna en esta misma posición, la regla, y una de realismo que exige 0 % para el rey solo. | `tests/test_live_features.py`, `tests/test_reglas.py`, `tests/test_model_realism.py` |

**Resultado.** En las 2.417 filas de test donde un solo lado puede dar mate, la log-loss baja de
0,471 a 0,409, y lo que da el modelo se parece a lo que pasó:

| Reloj del que puede ganar | Real: gana / tablas / gana el que no puede | Sin la regla | Con la regla |
|---|---|---|---|
| menos de 2 s | 68,1 / 31,9 / 0 | 61,1 / 29,1 / 9,8 | 67,2 / 32,8 / 0 |
| 2 a 5 s | 77,3 / 22,7 / 0 | 73,9 / 19,6 / 6,5 | 78,3 / 21,7 / 0 |
| 5 a 15 s | 79,3 / 20,7 / 0 | 75,6 / 18,2 / 6,2 | 80,0 / 20,0 / 0 |
| 15 s o más | 85,1 / 14,9 / 0 | 82,5 / 13,6 / 3,9 | 85,5 / 14,5 / 0 |

En la partida de Magnus el modelo ahora le da 0 % a Magnus y entre 44 % y 47 % a las negras, con
53 % a 56 % de tablas. No sube "mucho" porque así pasa en la realidad: con un rey solo enfrente y
menos de 1 s, el que tiene el material termina en tablas el 61,7 % de las veces; con 1 a 2 s, el
39,5 %.

**Lo que cambió de rebote.** Con las dos columnas en la base se rehízo la ablación: entran los
ataques al rey (−0,0003 ± 0,0002) y salen los peones pasados (−0,0004 ± 0,0007). Los dos estaban en
el límite. El modelo queda con 48 columnas. Test: log-loss 0,790 (antes 0,791) y 62,3 % de aciertos.
Dama ganada: +27,2 y +25,6 puntos. La importancia por permutación se mide sobre el bosque sin la
regla: con la regla, desordenar `puede_dar_mate_*` le diría a quien ganó que no podía ganar, y eso
mediría la regla, no lo que aprendió el modelo.

No se usa un motor como Stockfish: el modelo aprende de partidas reales qué suele pasar
entre personas de cierto nivel, con cierto material y cierto reloj, no cuál es la mejor
jugada teórica.

## Qué no se cambió

- La métrica para decidir sigue siendo la log-loss: la app muestra probabilidades. La
  accuracy se informa siempre al lado, pero no elige modelos ni columnas.
- La variante de ratings sigue siendo la D. Los tramos y la importancia por tramo son
  mediciones sobre el test, no decisiones.
- Se descartó una mejora del modelo de duración (selección propia de columnas): en test
  quedaba prácticamente igual (22,875 contra 22,889 plies) y la duración no se usa en la
  presentación.
