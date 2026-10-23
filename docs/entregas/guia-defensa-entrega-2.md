# Guía de defensa — Entrega 2 (Ajedrez online, Chess.com)

Cifras vigentes de la corrida `manual__2026-10-22T18:56:28` del 22/10/2026:
120 cuentas, 100.396 partidas y 547.555 filas en los seis cortes de referencia.
El notebook 02 ejecutado es la evidencia; la hoja común está en `plan-coherencia.md`.
La entrega fue el 23/09; esta guía se actualiza para defender el estado vigente.

## 0. Antes de entrar

Abrir el notebook 02 con sus salidas guardadas y esta guía. No hace falta levantar
Airflow ni recalcular durante la defensa. Cualquier integrante debe poder explicar
las hipótesis, las fugas y la partición; la nota es individual.

## 1. Qué cambió (min 0–2)

La elección pasó de ocho cuentas manuales a una lista automática, congelada y versionada
en `config/jugadores_seleccionados.yaml`: 20 cuentas por cada una de seis bandas.
Los pools son países, FM/CM/NM, GM/IM y rankings para élite. La ampliación conserva
las 100 originales; `extensions` la deja auditada. La corrida produce 101.094 registros
→ 100.396 partidas (99,31 %), 35 columnas y 1.559.622 cortes del ply 0 al 120.

La pregunta ahora es predecir resultado y duración restante antes y durante la partida.
La Parte A tiene una fila por partida; la Parte B, una fila por partida y corte.

## 2. Perfil, calidad y objetivos (min 2–7)

```python
import pandas as pd
df = pd.read_parquet("data/processed/partidas_ajedrez_clean.parquet")
df.shape  # (100396, 35)
df["GameUrl"].is_unique  # True
df.isna().sum().loc[lambda s: s > 0]
df["resultado"].value_counts(normalize=True)
df.select_dtypes("number").skew()
```

Texto, categorías, booleanos, enteros, flotantes y fechas conviven en el Parquet;
ninguna numérica quedó como texto. Los nulos son 89.256 en `TournamentUrl` y 1.620
en cada tasa histórica; las columnas críticas tienen cero por el filtro explícito.
Hay 54.998 usuarios distintos incluyendo rivales.

**Lectura de calidad.** Las columnas críticas no tienen nulos por las reglas explícitas de filtrado. Los nulos presentes son estructurales: `TournamentUrl` (88,9 %) corresponde a partidas fuera de torneo y las tres `tasa_*_hist` (1,6 %) a matchups con menos de 30 partidas previas. `Event`, `Variant` y `Rated` son constantes y salen del modelo.

La fecha máxima necesita explicación: los archivos de agosto incluyen 93 partidas (0,093 %) fechadas el 1 de septiembre UTC: 66 blitz, 15 rapid y 12 bullet. `until_month` filtra archivos mensuales, no la fecha individual de cada PGN. Se conservan y se documentan como un límite horario de la fuente.

Blancas y negras concentran 48,80 % y 44,40 % de las partidas; Empate es 6,81 %. Hay que informar métricas por clase, especialmente recall y F1 de Empate. La duración tiene media 78,2 y mediana 73 plies, con cola derecha hasta 646: no se eliminan partidas largas válidas.

### Asimetría y cobertura por nivel

`tiempo_base_seg` (asimetría 4,114) e `incremento_seg` (6,452) tienen colas largas. Para modelos lineales se puede evaluar una transformación; los árboles no la necesitan. Las seis bandas representan entre 14,8 % y 19,8 % de las partidas. `elite` cubre [3000, 4000) y `top_mundial`, [2600, 3000): son cortes del proyecto, no categorías oficiales de Chess.com. Los cupos de 20 cuentas por banda no implican igual número de partidas por nivel.

## 3. Qué se descartó y por qué (min 7–9)

De los 101.094 registros descargados, 698 (0,69 %) no llegaron al Parquet: 273 duplicados entre cuentas y 425 partidas de menos de 5 plies. Ambos motivos son estructurales o de alcance. Los motivos de faltante real (sin resultado, sin ELO válido o fecha inválida) dieron cero filas en esta corrida. También dieron cero las categorías de respaldo `familia_apertura="Desconocida"` y `Termination="otro"`. Esto describe esta muestra, no garantiza que la fuente nunca tenga faltantes.

| Motivo | Tipo | Filas |
|---|---|---:|
| Duplicado entre cuentas | Estructural | 273 |
| Menos de 5 plies | Fuera del universo | 425 |
| Sin resultado, sin rating o fecha inválida | Faltante real | 0 cada uno |
| Variante, ritmo o rated fuera de alcance | Fuera del universo | 0 cada uno |

## 4. Fechas y cuentas repetidas (min 9–10)

El descargador recorre archivos mensuales del más nuevo al más viejo hasta reunir
1.000 partidas elegibles por cuenta. Por eso las de baja actividad se remontan a 2013.

Las 120 cuentas seleccionadas aparecen entre 16 y 1.204 veces (media 843,0; mediana 996), contando ambos colores. El máximo puede superar las 1.000 descargas propias porque también entran partidas por el historial de otros seleccionados; cada `GameUrl` se conserva una vez. Para el cuadro de antigüedad se asigna cada partida a una sola cuenta (blancas si ambas son seleccionadas).

Las 10 cuentas con partidas más antiguas abarcan cinco de las seis bandas; ninguna es `elite`. Siete son `experto` o `top_mundial`. La antigüedad depende de la actividad y la ventana necesaria para reunir partidas, sin demostrar una causa por nivel.

**Implicancia.** Un corte temporal global concentra en test las cuentas con actividad reciente. El notebook 03 usa esa partición para predecir partidas futuras; el 04 agrega una comparación por jugador para evaluar la limitación.

## 5. Las cuatro hipótesis (min 10–16)

La metodología usa comparación, asociación y composición, con el semáforo de la
cátedra (§4 del notebook). η² <0,05 es rojo y >0,25 verde; correlación absoluta <0,20
es roja y >0,60 verde. La separación de dos grupos usa cortes 0,20 y 0,80. Amarillo
habilita hasta dos movimientos justificados por el gráfico. No autoriza elegir
la banda con el valor más favorable.


### H1 · Diferencia de ELO y resultado

| Campo | Contenido |
|---|---|
| **Afirmación** | `diferencia_elo` (blancas − negras) explica el `resultado`: cuando es positiva tiende a ganar blancas, cuando es negativa tiende a ganar negras. |
| **Qué espero ver** | Que el promedio de `diferencia_elo` sea claramente distinto entre las partidas donde ganaron blancas y las que ganaron negras. |
| **Medida y gráfico** | Comparación (3 grupos): `eta2(df["diferencia_elo"], df["resultado"])` — cuánto de la variación de la diferencia de ELO se explica por qué color ganó. Se acompaña con la tabla por bandas de diferencia (composición/apoyo visual) y barras apiladas. |

**Resultado: η² = 0,116, zona 🟡.** La victoria blanca pasa de 8,36 % con diferencia ≤ −301 a 89,70 % con diferencia ≥ 301. El rating ordena el resultado, sin explicarlo por sí solo.

**Movimiento: controlar por `nivel_promedio`.** Las seis bandas van de 0,078 (`intermedio`) a 0,190 (`elite`), todas amarillas. Por ritmo, los valores van de 0,087 a 0,137. El η² controlado por nivel, con sumas de cuadrados agrupadas, es 0,126: sigue amarillo.

**Decisión: inconclusa.** No se justifica otro movimiento. La reconstrucción parcial del rating en §9.1 baja el η² de 0,115 a 0,087 sobre el mismo subconjunto; el lado rival sigue con rating posterior en ese diagnóstico, por lo que tampoco es una estimación sin fuga.

### H2 · Paridad de ELO y duración

| Campo | Contenido |
|---|---|
| **Afirmación** | Las partidas con menor `abs_diferencia_elo` (rivales más parejos) se mueven junto con `cantidad_jugadas`: a menor diferencia, mayor duración. |
| **Qué espero ver** | Correlación negativa entre `abs_diferencia_elo` y `cantidad_jugadas`. |
| **Medida y gráfico** | Asociación: `asociacion(abs_diferencia_elo, cantidad_jugadas)` → Pearson, Spearman y brecha (Spearman − Pearson). Gráfico: muestra reproducible de puntos y mediana por bandas de 50 puntos. |

**Resultado: Pearson −0,020 (🔴), Spearman 0,056 (🔴), brecha 0,076 (🟡).** Ambas correlaciones son débiles y tienen signos distintos sobre 100.396 partidas. La brecha no habilita una conclusión útil cuando ambas correlaciones son rojas.

**Decisión: refutada.** La paridad de rating no aporta una relación lineal o monótona útil con la duración; no hace falta un movimiento adicional.

### H3 · Ritmo y terminación por tiempo

| Campo | Contenido |
|---|---|
| **Afirmación** | Bullet está sobrerrepresentado en terminar por tiempo (`Termination == "time"`) frente a la proporción global; Rapid está subrepresentado. |
| **Qué espero ver** | Orden Bullet > Blitz > Rapid, y las tres proporciones separadas de la proporción global. |
| **Medida y gráfico** | Composición: proporción de `Termination == "time"` en cada `TimeClass` contra la proporción global (barras + línea de referencia). Como esta plantilla no tiene un corte propio en `CORTES`, se cuantifica el efecto con la medida de comparación equivalente: `eta2` de la indicadora `Termination == "time"` agrupada por `TimeClass`. |

**Resultado:** por tiempo terminan 39,35 % de bullet, 21,30 % de blitz y 7,22 % de rapid, contra 24,65 % global. η² = 0,060 (🟡).

**Movimiento por nivel.** η²: principiante 0,130 · intermedio 0,095 · avanzado 0,049 · experto 0,022 · top_mundial 0,044 · elite 0,026. Sólo las dos primeras quedan amarillas; las otras cuatro son rojas. Bullet > blitz > rapid se sostiene en las cinco bandas con los tres ritmos observados. En `elite` no hay rapid: sólo se puede contrastar bullet (30,0 %) contra blitz (16,3 %).

**Decisión: inconclusa en principiante e intermedio, refutada en las otras cuatro bandas.** El efecto es débil en niveles altos; esto no demuestra que administren igual el reloj en todos los ritmos. La ausencia de rapid en `elite` es una limitación de cobertura. `Termination` queda fuera del modelo por fuga temporal en cualquier nivel.

### H4 · Familia de apertura y duración

| Campo | Contenido |
|---|---|
| **Afirmación** | `cantidad_jugadas` difiere entre partidas de apertura Cerrada y Semiabierta: Cerrada produce partidas más largas. |
| **Qué espero ver** | Separación clara de `cantidad_jugadas` entre esos dos grupos específicos. |
| **Medida y gráfico** | Comparación (2 grupos): `separacion(cantidad_jugadas Cerrada, cantidad_jugadas Semiabierta)` — la afirmación compara exactamente dos familias, así que la medida de la plantilla es `separacion`, no `eta2` sobre las cinco familias. El `eta2` de duración explicada por las 5 familias se deja como dato complementario. Gráfico: boxplot por familia, sin ocultar el tamaño de cada grupo. |

**Resultado: separación(Cerrada, Semiabierta) = 0,074, zona 🔴.** Sus medias son 80,1 y 77,5 plies. El η² sobre las cinco familias es 0,007 (🔴): explica menos del 1 % de la variación. India es la más larga (85,6 plies) y la menos numerosa (5.269 partidas, contra 31.435 de Semiabierta).

**Decisión: refutada.** No hay separación suficiente para usar esta familia como predictor de duración. Además, el ECO mira jugadas futuras en cortes tempranos.

## 6. Fugas cuantificadas

**Evidencia del rating posterior.** El signo del cambio coincide con el resultado de esa misma partida en el 99,93 % de 92.515 partidas propias decisivas. Con el resultado anterior coincide en 52,78 % de 90.665 casos. La asociación con el resultado actual es casi determinística; las excepciones no se atribuyen a una causa sin verificarlas. El rating posterior y sus derivadas no entran al modelo.

Entre las 16.502 partidas con `|diferencia_elo| ≤ 10`, ganan blancas el 51,92 % cuando la diferencia es positiva y el 45,25 % cuando es negativa: 6,68 puntos porcentuales. Es coherente con la fuga, aunque esta comparación sola no la prueba.

Se reconstruye el rating previo del lado seleccionado desde su historial. En este diagnóstico el rival conserva su rating posterior cuando no puede reconstruirse: es una corrección parcial y conserva fuga; no es la matriz que se usa para entrenar.

La reconstrucción cubre al menos un lado en 100.112 de 100.396 partidas (99,7 %). Sobre ese mismo subconjunto, el η² baja de 0,115 a 0,087, ambos amarillos.

La fuga del rating posterior está documentada. Para modelar, `src/rating_history.py` usa el rating previo reconstruido y deja NaN del lado sin historial; nunca lo rellena con el posterior del rival. Reconstruir ambos lados requeriría más historiales. *(Actualización posterior, Entrega 3: el rating del rival sí está en cada partida descargada donde aparece; el 04 lo usa como rating previo con cierre anterior al inicio y conoce los dos lados en el 41,7 % de train.)*

`es_sorpresa` coincide al 100 % con una regla de `resultado` y `diferencia_elo`:
es identidad, no una asociación aprovechable. `Result` es el target en otro formato.
`Termination`, `EndTime` y duración total se conocen al final. ECO y sus derivadas
pueden mirar hasta 40 plies de la línea, así que tampoco sirven en cortes tempranos.

## 7. Columnas candidatas y disponibilidad

| Grupo | Decisión para el modelado |
|---|---|
| Ritmo, base, incremento, torneo | Candidatas antes de empezar |
| Rating previo, forma y estilo | Sólo con historial causal; el 04 los deriva dentro del Pipeline |
| Material, reloj y calidad de posición | Sólo lo observado hasta el corte |
| Matchup e historial | Disponibles desde el ply 2; se evalúan por ablación |
| Usuarios, URL de partida o torneo | Identificadores, fuera del modelo general |
| Date, StartTime | Orden y auditoría, no predictores crudos |
| Rating posterior y derivados, resultado PGN, terminación y duración total | Fuera por fuga |
| ECO, Opening, familia_apertura | Fuera por disponibilidad temporal |
| Event, Variant, Rated | Fuera por constantes |

La tabla §9 del notebook cubre las 35 columnas y una derivada. Es una propuesta
del EDA; las decisiones finales las toma el notebook 04 con validación cruzada.

## 7b. Durante la partida

**Lectura.**

- **Tamaño:** 547.555 filas × 35 columnas en seis cortes de referencia de 100.396 partidas; la tabla completa tiene 1.559.622 filas. Hay 99.762 partidas al ply 10 y 66.413 al 60.
- **Tipos y nulos:** las ocho columnas de calidad de posición son conteos sin nulos. Los 200.792 nulos de cortes son los dos gastos recientes en el corte 0. En el tidy, `TournamentUrl` falta en el 88,9 % y las tasas históricas en el 1,6 %, conforme a sus condiciones estructurales.
- **Constantes:** `turno_blancas` es constante en estos cortes pares. En la tabla completa varía por los cortes impares. No hay claves duplicadas.
- **Objetivo:** 48,8 % Gana Blancas, 44,4 % Gana Negras, 6,8 % Empate. Al ply 60 las tablas pesan 9,4 %: es selección de partidas largas.
- **Asimetría:** promociones 25,23; gastos recientes 6,51–7,25; relojes en segundos 4,33–4,34. Material y fracciones de reloj tienen cola a la izquierda. Una asimetría alta no justifica filtrar partidas válidas.

### Resultado de la entrega — Parte B

547.555 filas de referencia de 100.396 partidas, clave única; sólo hay nulos de gasto reciente en el corte 0. Sobre las 66.413 partidas que llegan al ply 60:

- **H1′:** material η² 0,108 al ply 60; señal amarilla y tardía, parcialmente confirmada.
- **H2′:** reloj η² 0,097, controlado 0,101; candidata con señal propia, modulada por ritmo.
- **H3′:** material con signo contrario al esperado en todos los ritmos; refutada para material. El reloj se asocia sobre todo en bullet (Spearman 0,431).
- **H4′:** ventaja blanca de 4,40 pp, sin variación relevante por ritmo; mayor brecha descriptiva en top_mundial (6,58 pp), seguida de elite (5,78).

Las decisiones se mantienen. Las asociaciones bivariadas no prueban el aporte conjunto del modelo ni generalización a jugadores nuevos.

## 8. Matchmaking y torneos

**Lectura.** De 61.719 partidas sujetas al límite, 5.311 (8,61 %) superan ±200: el 91,39 % lo cumple. Son una cota inferior de partidas incompatibles con el emparejamiento automático documentado.

La dirección ahora es la esperada en los tres ritmos: fuera del grupo sujeto al límite hay más brechas grandes. En bullet: 8,84 % contra 20,01 % (OR 2,58); blitz: 9,76 % contra 13,33 % (OR 1,42); rapid: 5,14 % contra 25,54 % (OR 6,33).

El bootstrap por jugador mantiene incertidumbre en bullet [−0,65; 24,83] y blitz [−2,82; 9,68] pp. El global [1,35; 14,05] y rapid [4,62; 33,14] excluyen cero. Cambia la conclusión global respecto de la corrida anterior, pero no la falta de robustez por jugador en bullet y blitz. Los p-valores por partida no resuelven esa dependencia.

**Los torneos explican la mayor parte de las excepciones.** Hay 11.140 partidas de torneo, y 3.300 de las 5.311 excepciones sujetas al límite (62,1 %) son de torneo. Dentro de torneos, entre 63,62 % y 84,36 % del grupo sujeto supera ±200; fuera, entre 3,31 % y 3,83 %.

Sin torneos, el global es 3,54 % fuera en el grupo sujeto contra 10,37 % en el no sujeto; la diferencia ya no desaparece. En rapid persiste (3,74 % contra 25,70 %). La composición de torneos explica parte del patrón, sin agotar las diferencias entre grupos.

### Conclusión

El límite documentado es ±200 para ratings menores a 2500 en bullet/blitz o 2000 en rapid. En la muestra lo cumple el 91,39 % de las partidas sujetas. El 62,1 % de las excepciones son de torneo, mecanismo identificado en la fuente.

La comparación está en la dirección esperada en los tres ritmos, pero sólo el global y rapid conservan intervalos bootstrap por jugador que excluyen cero. Bullet y blitz siguen siendo inciertos. No se debe interpretar el χ² por partida como evidencia de observaciones independientes.

**Limitaciones.** La regla se aplica como referencia al período 2013–2026; no identifica el mecanismo de cada partida. El rating del Parquet es posterior, los jugadores se repiten y no se conoce el motivo de las excepciones no ligadas a torneo. No es evidencia causal.

## 9. Qué cambió con la banda élite

Las decisiones H1–H4 y H1′–H4′ se mantienen. Cambian sus magnitudes y aparece
la falta de rapid en élite, que impide comprobar allí el orden de tres ritmos.
En matchmaking cambia la comparación global: el intervalo por jugador ya excluye cero;
bullet y blitz siguen siendo inciertos. No se fuerza ninguna conclusión.

## 10. Devolución anterior y puente al modelado

La elección de jugadores está automatizada; hay seis niveles y la lista se versiona.
Se declara el sesgo de titulados en avanzado y el de rankings en élite. Las cuentas
y las partidas se repiten: el 04 valida por tiempo y por partida, y contrasta por jugador.
La muestra permite estudiar este universo, no estimar la distribución de Chess.com.

Durante la integración del historial al Pipeline se encontró que `shift()` por cierre
no garantizaba `EndTime < StartTime`. El 04 cuantifica la anomalía; el transformador
causal excluye cierres simultáneos y solapamientos. El diagnóstico parcial del 02
se conserva como evidencia de fuga, sin presentarlo como una matriz válida de entrenamiento.
