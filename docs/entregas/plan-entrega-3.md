# Entrega 3 · Modelado (28/10/2026)

Mapa de la [consigna](consigna-entrega-3.md) al notebook 04 y respuestas para la defensa.
Dataset vigente: DAG `manual__2026-10-22T18:56:28`, 120 cuentas, 100.396 partidas,
1.559.622 cortes. Los números de modelado salen de las celdas ejecutadas del 04;
la hoja de datos está en `plan-coherencia.md`.

## La respuesta corta

Un **random forest de 40 columnas** predice el resultado antes y durante la partida.
Usa la base de contexto, posición y reloj más la forma reciente. En test da log-loss
**0,804 frente a 0,936 del piso: 14,09 % menos**. Antes de mover la mejora es modesta:
0,866 frente a 0,900 (3,79 %); al ply 60 llega a 18,84 % y al 120 a 38,66 %.
Sobre las mismas partidas que llegan al ply 60 también mejora desde el corte 0
(0,917 frente a 0,940, 2,45 %), sin confundir progreso con cambio de población.

El modelo se guarda en `models/modelo_en_vivo.joblib` (132,1 MB), sin versionarlo.
`predecir()` lo aplica a cada ply; el primer paso del Pipeline calcula el historial
con cierres estrictamente anteriores al inicio actual.

## Consigna → notebook 04

| Pide la consigna | Dónde | Resultado |
|---|---|---|
| Métrica antes de elegir | §1 | Log-loss por mostrar probabilidades; F1 macro y recall de Empate como secundarias |
| Piso con la misma validación | §3 | DummyClassifier prior: 0,938 ± 0,009 |
| Validación que imita el uso | §1–2 | Cinco folds temporales por partida; mismos jugadores permitidos; asserts de separación de partidas e inicio posterior al último cierre de train |
| Test con el mismo criterio | §2 | 80.314 partidas de train, 20.080 de test, dos cruzadas excluidas; corte 04/07/2026 01:29 UTC |
| Todo el historial dentro del objeto entrenado | §1–3 | PlayerHistoryTransformer → preprocesamiento → estimador; ventanas causales, sin conservar historiales en fit |
| Simple + dos familias más, media y desvío | §3 | Logística 0,857 ± 0,027; bosque 0,836 ± 0,025; boosting 0,868 ± 0,064 |
| Complejidad justificada por diferencias pareadas | §3 | Bosque − logística: −0,0205 ± 0,0058; boosting no supera la regla |
| Otras validaciones | §4 | Por partida 0,823; filas al azar 0,811; por cuenta ancla 0,828 |
| Grilla completa del elegido | §5 | max_features=0.3, min_samples_leaf=20; 0,8301 ± 0,0231 (desvío de sklearn) |
| Clase chica: decisión y costo | §6 | Balanced sube recall de Empate 0,026 → 0,451, pero cuesta +0,1387 ± 0,0156 de log-loss; queda sin balancear |
| Columnas con y sin cada grupo | §7 | Entra forma; se conservan rating y relojes; no entran posición adicional, estilo ni matchup |
| Test de la versión final | §8 | Log-loss 0,804 frente a 0,936; F1 macro 0,449; recall de Empate 0,036. Ver nota sobre reutilización del período |
| Confusión por fila/columna y reporte por clase | §8 | Recall Empate 3,60 %, precisión 49,42 %; recall blancas 71,94 %, negras 61,94 % |
| Importancia por permutación | §8 | Material: +0,0713 ± 0,0011; diferencia de reloj: +0,0428 ± 0,0003 de log-loss. Se permuta después de derivar el historial |
| Uso en cada jugada y guardado | §9, §11 | Paridad entre predecir y el camino de evaluación en los cortes, interpolación y round-trip del artefacto |
| Duración restante | §10 | Boosting: MAE 22,934 frente a 28,357 plies del piso (19,13 % menos error); sin grilla propia |
| Notebook limpio y semilla | todo | Restart & Run All; random_state=42 del config; 37,3 minutos medidos en la última celda |

La grilla muestra el desvío de sklearn (ddof=0); las tablas de resumen usan el muestral
de pandas (ddof=1). Las decisiones pareadas usan el desvío muestral de las diferencias.
Superar un desvío es la regla heurística declarada, no una prueba de significancia.

## Qué columnas quedaron y por qué

Las 40 columnas son `PRE_GAME + LIVE + FORM` de `src/predict.py`:

- **Antes de mover:** ritmo, base, incremento, torneo, rating previo por lado y las diez
  columnas de forma: media de diez resultados, racha, tendencia del rating, minutos
  desde la anterior y partidas de sesión, por color.
- **Durante:** ply, turno, jaque, movilidad del bando que mueve, material, capturas,
  jaques acumulados, promociones, enroques/derechos y relojes/gasto reciente.

La forma mejora log-loss global en 0,0034 ± 0,0031 y corte 0 en 0,0083 ± 0,0065.
Quitar relojes cuesta 0,0407 ± 0,0057 global. Quitar rating no mejora por más que el
desvío, así que se conserva; no se afirma que su aporte incremental esté demostrado.

**No entran los cuatro grupos adicionales de posición.** Material colgado y movilidad
por bando mejoran globalmente, pero empeoran el corte 0 más que su desvío permitido:
+0,0009 ± 0,0007 y +0,0003 ± 0,0002, respectivamente. Son constantes en la posición
inicial, pero agregarlas cambia los árboles y el muestreo de columnas del modelo global.
Se respeta la regla de no empeorar una parte de la pregunta para mejorar la otra.
Ataques al rey y peones pasados tampoco la superan. Esto no prueba ausencia de señal.

Estilo: Δ global +0,0005 ± 0,0023, dentro de la variación. Matchup:
+0,0017 ± 0,0011, sin mejora. Ambos quedan fuera. Las features de calidad y estilo
siguen implementadas y verificadas como candidatas, sin presentarlas como seleccionadas.

## Historial dentro del Pipeline y corrección temporal

`player_history_payloads` lee observaciones individuales por cuenta. El primer paso del
Pipeline deriva rating, forma y estilo al consultar `StartTime`, y sólo admite cierres
**menores** a ese inicio. Ni la partida actual, ni una solapada, ni un cierre simultáneo
pueden aportar resultado, rating o reloj final. Los agregados de cobertura se calculan
fuera sólo para describir los datos; CV y entrenamiento reciben las derivadas vacías
más los payloads. El transformador no aprende del target de fit ni guarda los historiales.

La reconstrucción anterior sólo ordenaba por cierre y aplicaba shift. Eso excluía la
partida actual por orden, pero no garantizaba disponibilidad al inicio. La sección 2
cuantifica 1.345 observaciones propias con cierre anterior simultáneo o posterior al inicio actual; se repitió la selección completa con la condición estricta.
Los tests cubren ventanas, igualdad de horarios, solapamientos, futuro, serialización y
la conexión de predecir con el transformador. El 03 también pasa los inicios al helper.
El diagnóstico parcial del 02 se conserva como evidencia de fuga, sin usarlo para entrenar.

El matchup se probó como candidato causal del pipeline de datos y quedó descartado:
sus tasas no forman parte del objeto final. El rating posterior y derivados,
Termination, duración total, EndTime como predictor y ECO/Opening/familia_apertura
quedan fuera por fuga o indisponibilidad temporal.

## Qué se puede afirmar del test

El 03 fue exploratorio y tomó decisiones mirando este período. También se ejecutó una
versión anterior del 04 antes de corregir el historial. **No es un holdout nuevo**.
La versión actual rehace familia, grilla, balance y columnas con CV; tras congelarlas,
el test mide esa versión. No se cambia una regla ni se recupera una columna por su
resultado en test. La repetición por corregir el cálculo se declara, no se presenta
como una evaluación nunca observada.

## Preguntas para los minutos 16–22

| Pregunta | Respuesta |
|---|---|
| ¿Por qué log-loss? | Mostrar una probabilidad muy segura y equivocada es el error caro de la app. Accuracy no distingue acertar con 51 % de acertar con 99 % |
| ¿Cuánto mejora el piso? | 14,09 % de log-loss global; 3,79 % antes de mover y 18,84 % al ply 60. No son puntos de accuracy |
| ¿Por qué temporal y por partida? | Se predicen partidas futuras y sus cortes no son independientes. Al azar todas las filas comparten partida con train; se observa 0,811 frente a 0,823 por partida |
| ¿Y jugadores nuevos? | Agrupar por cuenta ancla da 0,828, pero no excluye rivales repetidos: es un diagnóstico limitado, no garantía universal |
| ¿Por qué el bosque? | Mejora a la logística por 0,0205 ± 0,0058; boosting por defecto no supera la regla y tiene una brecha de train/validación |
| Una confusión concreta | Desde ply 60, 20,3 % de errores de ganador en filas decisivas; en 56,3 % el predicho iba arriba en material. 50,15 % de esos errores terminan por tiempo, frente a 40,90 % global |
| ¿Qué no funcionó? | Balancear, estilo, matchup y las posiciones adicionales bajo la regla conjunta global/corte 0; no se dice que antes de mover no haya señal |
| ¿Y la diferencia de rating? | Quitar rating no mejora por más que el desvío, y se dice. Sólo 185 de 80.314 partidas de train (0,23 %) tienen el rating previo de los dos lados: se descargan las partidas de 120 cuentas, no las de sus rivales. La auditoría posterior muestra que la diferencia de rating mueve la probabilidad al revés; es la mejora pendiente, sin reentrenar antes de la entrega |
| ¿El historial vio el resultado actual? | No: sólo cierres estrictamente anteriores al inicio; agregar futuro no altera los valores pasados |

## Pruebas del artefacto y límite pendiente

`python -m unittest discover -s tests` ejecuta 94 tests sin red: **93 pasan y uno falla
en dos subcasos**. Proporciones iniciales, menos reloj, ganador cerca del final en
promedio y calibración por clase pasan. El test de dama ganada exige una subida de
más de 15 puntos de probabilidad para cada color. Obtiene +9,02 y +10,34 puntos en
aperturas legales: material correctamente extraído (0 → +9 / −9) y dirección correcta,
pero sensibilidad insuficiente para ese contrato. Se conserva el umbral y el fallo;
no se ajusta el modelo mirando estos ejemplos ni se declara la suite en verde.

Los tests que usan el artefacto se saltean si no está regenerado; los de población y
calibración requieren además Parquets e historiales crudos. La prueba de ganador
compara las mismas 1.000 partidas decisivas, con corte tardío ≥60 y hasta diez plies
restantes; la calibración usa 5.000 filas y tolerancia ECE de ocho puntos por clase.
No reemplazan la evaluación temporal ni garantizan cada posición individual.

## Limitaciones y continuidad

- Cupos de 120 cuentas, con sesgos de titulados/rankings; no representa toda Chess.com.
  No hay rapid en las partidas de banda elite de esta corrida.
- Rating y forma suelen conocerse sólo para un lado. Los faltantes llegan al imputador
  ajustado en train; no se rellenan con el rating posterior del rival.
- Se ponderan filas de cortes, por lo que una partida larga pesa más que una corta.
- El modelo se entrenó hasta el ply 120: más allá extrapola. Cada corte tardío cambia
  la población; se muestra también población común.
- Las ablaciones prueban grupos contra la base, no una búsqueda de todas las combinaciones.
  La regla conjunta puede rechazar mejoras globales pequeñas por deterioros del corte 0.
- Duración es secundaria y no tiene ajuste propio de hiperparámetros; los errores por
  tramo se leen en §10. El período de test fue reutilizado, según la nota anterior.
- La app (PR #31, mergeado) usa este artefacto y pasa historiales e inicios al
  Pipeline. La auditoría posterior (ratings de ambos lados casi nunca disponibles y
  respuesta invertida a la diferencia de rating) y su plan están en
  [`plan-mejora-modelo-app.md`](plan-mejora-modelo-app.md); no cambian el artefacto.
