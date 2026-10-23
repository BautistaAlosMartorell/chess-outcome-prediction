# Coherencia entre pipeline, EDA, modelado y documentación

La hoja de datos siguiente identifica la corrida vigente del 22/10/2026. README,
AGENTS, guías de defensa y notebooks se contrastan con esta corrida y con las salidas
del notebook que calcula cada métrica. Las entradas anteriores de CHANGELOG y los
estados históricos fechados de la skill de entregas se conservan como registro.

## Decisiones vigentes

- Pregunta: resultado y duración restante **antes y durante** la partida.
- Unidad de modelado: partida × corte. La tabla base conserva una partida por fila.
- Lista congelada en `config/jugadores_seleccionados.yaml`, versionada. Los snapshots y
  el checkpoint son regenerables y quedan en `data/raw/seleccion/`.
- Se sumó `elite` sin volver a elegir las 100 cuentas originales; `extensions` audita
  la ampliación. Hay seis bandas de 20 cuentas.
- Un corte cada 5 plies entre 0 y 120. El EDA y el 03 usan los seis de referencia.
- El 03 es exploratorio. El 04 decide familias, hiperparámetros y columnas por CV temporal
  y por partida. El historial del modelo se deriva dentro del Pipeline.
- Se actualizan las guías de entregas pasadas; la consigna y el material de cátedra no
  se reescriben como si fueran resultados del proyecto.

## Hoja de datos vigente

| Dato | Valor | Evidencia |
|---|---|---|
| Corrida oficial | `manual__2026-10-22T18:56:28`, DAG completo en verde | Estado del DAG informado en la continuación |
| Jugadores / cupo | 120 / 20 por banda | Manifiesto versionado |
| Bandas | principiante [0,1200), intermedio [1200,1800), avanzado [1800,2200), experto [2200,2600), top_mundial [2600,3000), elite [3000,4000) | config.yaml |
| Ventana | Archivos hasta `2026-08` | config.yaml |
| Registros → partidas | 101.094 → 100.396; 99,31 % de retención | Notebook 01 §7 y 02 §2 |
| Descartes | 273 duplicados + 425 con menos de 5 plies = 698 | Notebook 02 §2 |
| Columnas base / cortes | 35 / 35 | Esquemas de los Parquet |
| Cortes completos | 1.559.622 filas; 25 valores de corte | Notebook 04 §2 |
| Cortes de referencia | 547.555 filas | Notebooks 02 Parte B y 03 §2 |
| Filas por corte de referencia | 0: 100.396 · 10: 99.762 · 20: 98.026 · 30: 94.671 · 40: 88.287 · 60: 66.413 | Notebook 03 §2 |
| Corte 120 | 12.323 partidas | Parquet de cortes |
| Resultado Blancas / Empate / Negras | 48.989 / 6.834 / 44.573 (48,80 % / 6,81 % / 44,40 %) | Notebook 02 §3 |
| Ritmos bullet / blitz / rapid | 29.391 / 57.184 / 13.821 | Notebook 02, anexo |
| Niveles: principiante / intermedio / avanzado / experto / top_mundial / elite | 17.027 / 17.584 / 14.858 / 15.660 / 19.916 / 15.351 | Notebook 01 §8 |
| Torneos | 11.140; TournamentUrl nula en 89.256 (88,90 %) | Notebook 02 §2 y anexo |
| Sin historial del matchup | 1.620 (1,61 %), primeras 30 de 54 grupos | Notebook 03 §7 |
| Rating previo: blancas / negras / algún lado / ambos | 50,1 % / 49,9 % / 99,7 % / 271 partidas | Notebook 03 §3, con condición temporal estricta |
| Forma reciente: blancas / negras | 48,9 % / 48,8 % | Notebook 04 §2 |
| Fechas | 2013-01-06 a 2026-09-01 | Notebook 02 §1 |
| Usuarios distintos, incluidos rivales | 54.998 | Notebook 02 §2 |
| Apariciones por cuenta | media 843,0; mediana 996; mínimo 16; máximo 1.204 | Notebooks 01 §8 y 02 §2 |
| Duración | media 78,2; mediana 73; máximo 646 plies | Notebook 02 §3 |
| Partición temporal | 2026-07-04 01:29 UTC; train 80.314 partidas, test 20.080, dos cruzadas excluidas | Notebooks 03 §4 y 04 §2 |
| Filas de train / test del 04 | 1.240.306 / 319.284 | Notebook 04 §2 |
| Muestra CV | 20.078 partidas, 310.018 filas, cinco folds | Notebook 04 §2 |

## Anomalías y límites que se explican

- 93 partidas de los archivos de agosto están fechadas el 1/9 UTC (66 blitz, 15 rapid,
  12 bullet). El filtro selecciona archivos mensuales, no fechas individuales del PGN.
- Los gastos recientes faltan sólo en las 100.396 filas del corte 0: aún no hubo jugadas.
- En los cortes de referencia hay cuatro gastos recientes negativos sin incremento;
  el PGN registra un aumento de reloj, sin permitir identificar la causa.
- El reloj supera el tiempo base en el 3,86 % de las filas de referencia, todas con
  incremento. Las coronaciones permiten material mayor al inicial.
- El máximo de 1.204 apariciones no contradice el tope de 1.000 descargas por cuenta:
  algunas partidas llegan por un rival también seleccionado.
- No hay rapid en las partidas de banda `elite`. No se completa ese hueco con ceros ni
  se afirma un orden de tres ritmos que la muestra no permite evaluar.
- `shift()` por cierre no garantizaba `EndTime < StartTime`. El transformador del 04
  excluye cierres iguales, solapamientos y futuro; la sección 2 encuentra 1.345
  observaciones propias cuyo cierre anterior no estaba disponible al inicio actual.
  El diagnóstico parcial del 02 conserva el rating posterior del rival para estudiar
  fuga, mientras que el modelado deja NaN donde no tiene historial.
- En Linux el uid 50000 necesita permiso sobre config para guardar una selección nueva.

## Qué cambia en las conclusiones

H1–H4 conservan sus decisiones, con magnitudes nuevas y el diagnóstico de `elite`.
Material y reloj mantienen señal tardía en el EDA. El anexo de matchmaking cambia:
la dirección es la esperada en los tres ritmos y el intervalo global por jugador excluye
cero; bullet y blitz siguen siendo inciertos.

El 03 ahora supera modestamente al piso antes de mover, también sobre población común.
Al corregir el historial con la condición estricta, su log-loss del corte 0 es 0,880
contra 0,895: reemplaza el 0,879 previo a esa corrección. Las decisiones finales del
04 y sus cifras están en `plan-entrega-3.md`: quedan 40 columnas, con forma reciente
y el rating de los dos lados (incluidos rivales), su antigüedad, diferencia y promedio;
log-loss 0,795 frente a 0,936 y MAE de duración 22,889 frente a 28,357.
La suite de 104 tests conserva un fallo en dos subcasos de dama ganada (+11,58/+6,29
puntos frente a +15 exigidos); los otros 102 tests pasan. No equivale a suite en verde.

## Verificación de coherencia

- Contrastar todos los números de modelado con las celdas ejecutadas del 04, sin elegir
  por test ni presentar como nuevo un test ya usado durante la exploración.
- Restart & Run All de los cuatro notebooks, salidas guardadas y sin errores.
- Tests de historial, predicción y comportamiento del modelo final sin red.
- Revisar cada merge con su assert anti fan-out y el diff antes de cada commit.
- Buscar cifras viejas fuera de registros históricos; conservar entradas previas del
  CHANGELOG. No incluir data ni modelos en Git.
- Commitear por partes, en una rama por cambio. Push y merge requieren confirmación;
  el modelado (PR #30) y la app con el modelo de 120 cuentas (PR #31) ya están en main.
