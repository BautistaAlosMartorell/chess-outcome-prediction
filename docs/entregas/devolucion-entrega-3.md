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
| 1 | Agrupar las filas por tiempo (tramos de movimientos) y calcular las métricas por grupo; mostrar cómo cambian | Seis tramos de plies (0, 5–20, 25–40, 45–60, 65–90, 95–120) con log-loss, accuracy, F1 macro y recall de tablas | Accuracy 54,0 % → 71,0 %; log-loss 0,854 → 0,692 | Notebook 04 §8 "Por tramo de jugadas"; `src/metricas_tramo.py`; app `/proyecto#acierta` |
| 2 | Mostrar la accuracy y métricas de decisión fija ("el modelo dijo esto, ¿acertó?") | Accuracy al lado de la log-loss en todas las tablas de test, con dos referencias: el piso (siempre gana blancas) y la regla del material | Test: 62,2 % contra 47,5 % del piso; la regla del material llega como mucho a 62,2 % al final, nueve puntos debajo del modelo | Notebook 04 §1, §8 y §12; app `/proyecto` |
| 3 | Matriz de confusión | Además de la global, una por tramo | Recall de blancas/negras 68,8 %/46,2 % antes de mover → 84,2 %/82,3 % al final; tablas 0 % → 15,9 % | Notebook 04 §8; app `/proyecto#acierta` (menú por tramo) |
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
| Columnas, con los hiperparámetros nuevos | La misma regla de ablación, rehecha | Entran material colgado, peones pasados y movilidad: 46 columnas | Notebook 04 §7 |
| Calibración de las probabilidades | Temperatura global, por tramo e isotónica, cada una ajustada con pedazos anteriores al que se mide | Ninguna pasa la regla (la mejor, −0,0012 ± 0,0018): queda sin calibrar | Notebook 04 §7b; `src/calibracion.py` |
| Resultado | — | Test: log-loss 0,791 (antes 0,795), 62,2 % de aciertos. Dama ganada: +24,1 y +24,0 puntos: **pasa**. Pasa toda la suite de pruebas. El modelo pesa 91 MB (antes 132) | `tests/test_model_realism.py` |

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
