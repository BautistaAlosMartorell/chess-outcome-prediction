# Guía de defensa · Entrega 4

La consigna dice que esto "no lo mide ningún script: se pregunta". Esta guía tiene una
respuesta para cada punto de "Lo que hay que saber explicar", leída del código. Los
números no se copian acá: salen de la app (`web/public/app/resumen.json`) y de los
notebooks.

## Cómo llega todo a la app

```
DAG de Airflow ──► data/raw/*.json, partidas_ajedrez_clean.parquet, partidas_cortes.parquet
notebook 02    ──► data/processed/reporte_eda.json      (hipótesis, η² por corte)
notebook 04    ──► models/modelo_en_vivo.joblib, models/reporte_modelado.json
                          │
python -m src.build_app ◄─┘  limpia los JSON otra vez (embudo), arma train/test como el 04,
                             predice el test con el modelo guardado y falla si la log-loss
                             no da lo mismo que el 04
                          │
                          ▼
web/public/app/resumen.json            números del texto (portada, «Cómo lo sabemos»)
web/public/app/graficos/*.json         specs de Vega-Lite generadas con Altair
                          │
                          ▼
Next.js: /proyecto importa resumen.json al compilar; GraficoAltair dibuja cada spec con
vega-embed tal cual. Jugar y Analizar llaman a la API (FastAPI), que carga el mismo modelo.
```

**Si cambian los datos:** DAG → notebooks 02 y 04 → `python -m src.build_app`. Los textos
que citan números se actualizan solos, porque leen `resumen.json`. Lo que no se actualiza
solo es el **sentido** de cada título: si un hallazgo cambiara de signo, hay que reescribir
la oración.

## Los gráficos, componente por componente

Código: `src/app_charts.py`. Los colores se definen una vez (`COLOR_RESULTADO`,
`COLOR_RITMO`, `COLOR_MODELO`, `COLOR_PISO`) y son los tokens de `web/app/globals.css`.
Un test (`tests/test_build_app.py`) verifica que coincidan.

### Los datos: `partidas_crudas`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | 100 partidas reales por ritmo, ordenadas por duración y tomadas a intervalos iguales (`muestra_cruda`) | Reproduce la forma completa: «67 de cada 100» se puede contar en el gráfico |
| Marca | Rectángulo finito (una línea por partida) y una regla punteada en el ply 60 | Se ve el dato crudo, no un resumen |
| x | Posición dentro del ritmo (sin eje) | Sólo ordena |
| y | Plies que duró, 0 a 160 (las más largas se cortan ahí) | La duración |
| color / opacidad | Ritmo (`ESCALA_RITMO`) / si pasa el ply 60 | La silueta oscura es lo que queda para los cortes tardíos |

### Lo que encontramos: `mosaico_resultado`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | Las 66.413 partidas que llegan al ply 60, en los plies 10, 30 y 60 (`segmentos_mosaico`) | Siempre las mismas: no mezcla «avanzó» con «quedaron las largas» |
| Marca | Rectángulo (mosaico) | Dos cantidades a la vez: cuántas y cómo terminaron |
| x / ancho | Tramo de ventaja, de negras muy arriba a blancas muy arriba; el ancho es la parte de las partidas | Se ve que al principio están todas en el medio |
| y / altura | Parte de cada resultado, apilada a 100 % | Se ve cuándo el color se inclina |
| color | Resultado, `ESCALA_RESULTADO` | El mismo en toda la app |
| Transformación | El reloj sólo con el material parejo (hasta 2 puntos) | Es la versión visible del η² controlado |

### Los aciertos: `acierto_de_cien`

Cien cuadrados por tramo (rectángulos, x/y = columna y fila). El color separa lo que ya acierta decir
siempre «blancas», lo que suma el modelo y lo que falla. Son conteos: no dice que sean las mismas
posiciones. Antes eran tres líneas con el eje cortado (35 % a 80 %), que agrandaban la diferencia.

### En qué se fija: `importancia_por_tramo`

Tres facetas (rating, material, reloj), mismo eje y: aciertos de cada 100 que se pierden al desordenar la
columna. Opacidad llena = la que más pesa en ese tramo, o las que empatan (a menos de 0,05). Antes
eran cinco áreas en log-loss, que nadie sabe leer en voz alta.

### Los errores: `acierto_por_situacion` y `como_terminan`

Mapa de calor (tramo × situación, color y número = aciertos) y barras enfrentadas: a la izquierda cómo
terminan 100 aciertos, a la derecha 100 errores.

### El modelo: `modelo_contra_piso`

Son dos vistas, una arriba de la otra (`vconcat`), con el mismo dominio de `x`:

| Componente | Arriba: «Error que evita el modelo» | Abajo: el error en crudo |
|---|---|---|
| Datos | `mejora` por corte: qué fracción del error del piso evita el modelo (solo la serie Modelo) | Log-loss de test por corte del modelo y del piso, recalculada por el build y verificada contra el 04 |
| Marca | Barra | Punto (piso y modelo) y segmento entre los dos |
| x | `corte_ply`, cuantitativa (dominio −3 a 123, igual que abajo) | `corte_ply`, cuantitativa |
| y | `mejora`, formato %, **arranca de cero** | `log_loss`, sin cero (`zero=False`): la diferencia entre las líneas es lo que importa |
| color | Verde del modelo | `serie` (Modelo / Piso), `ESCALA_SERIE` |
| Tooltip | Menos error que el piso y partidas de test del corte | Log-loss, mejora sobre el piso y partidas de test |

Va primero la vista de arriba porque arranca de cero y se lee como un logro. El error en
crudo, con el eje sin cero, hace subir al piso al final (las partidas largas terminan
distinto) y a primera vista parece que el modelo empeora.

### Explorá: `explora`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | Dos tablas: `filas` (una por partida y corte: material, diferencia de reloj y las tres probabilidades) y `partidas` (una por partida: jugadores, ritmo, nivel, resultado y `dif_rating`). Se unen con `transform_lookup` por `id` | La tabla de partidas va una sola vez (dataset con nombre): el archivo pesa ~4 MB en lugar de 17 |
| Marca (arriba) | Círculo | Una partida = un punto |
| x | `x_valor` (`transform_calculate`), según el param `eje_x`: **Material** (material + un desplazamiento fijo por partida), **Reloj** (`dif_reloj`, % del tiempo base) o **Rating** (`dif_rating`, puntos). Dominios ±15, ±100 % y ±400; los puntos sin valor se sacan con `isValid(datum.x_valor)` | El material es entero: sin desplazamiento, los puntos se apilan en columnas. Un solo canal cambia de variable: el modelo queda fijo en `y` |
| y | `ventaja` = P(blancas) − P(negras) (`transform_calculate`), de −100 % a +100 % | Lo que dice el modelo en un solo eje |
| color | `resultado` real, `ESCALA_RESULTADO` | Los mismos colores que la barra de Jugar y Analizar |
| tamaño | Condición: más grande si es la partida elegida | |
| Tooltip | Jugadores, ritmo, nivel, corte, material, reloj, rating previo (o «sin dato»), las tres probabilidades, lo que elige el modelo, resultado y cómo terminó | Detalle a pedido, con el modelo |
| Marca (abajo) | Área apilada normalizada de las tres probabilidades de la partida elegida, a lo largo de todos los cortes (`transform_fold`), y una regla en el corte del deslizador | Es la barra de la app, desplegada en el tiempo |

## Qué toca cada control

| Control | Param de Altair | Componente que toca |
|---|---|---|
| Deslizador "Plies jugados" | `corte` (`binding_range`, 0–120, paso 5) | El **filtro** del panorama (`datum.corte_ply == corte`) y la posición de la regla ámbar del detalle |
| Menú "Ritmo" | `ritmo` (`binding_select`) | El **filtro** del panorama (`ritmo == 'todos' \|\| datum.TimeClass == ritmo`) |
| Menú "Nivel" | `nivel` (`binding_select`) | El **filtro** del panorama, igual con `nivel_promedio` |
| Botones "Eje horizontal" | `eje_x` (Material / Reloj / Rating) | El **canal x** del panorama: qué variable, su dominio y las etiquetas del eje (`x_valor`). Con Rating, además, el **filtro** `isValid`: solo quedan las partidas con rating previo de los dos jugadores |
| Botones "Partidas" | `acierto` (Todas / Acertó / Se equivocó) | El **filtro** del panorama: compara la clase más probable con el resultado real en el corte elegido |
| Clic en un punto | `elegida` (`selection_point` sobre `id`) | El **filtro** del gráfico de abajo y el **tamaño** del punto elegido. Doble clic la suelta |

La página no usa los controles que Altair dibuja: `web/components/ExploraGrafico.tsx` los
reemplaza por controles propios (incluido «Reproducir», que avanza el corte solo) y escribe
cada valor en el param correspondiente de la vista de Vega.

## Una decisión de diseño que cambió

- **Explorá, primera versión:** el clic en un punto llevaba a `/analizar` con esa partida.
  No funcionaba por dos razones. Analizar sólo encuentra las *últimas* partidas de un
  usuario en Chess.com, y una de julio podía no estar. Además, Analizar arma el historial
  con lo que Chess.com devuelve *hoy*, así que la curva no coincidía con la del notebook.
  Ahora el detalle es un segundo gráfico de Altair, con las probabilidades del modelo tal
  como las mide el 04.
- **«El modelo», orden de las vistas:** la primera versión mostraba arriba el error en crudo
  (log-loss, eje sin cero). Como el error del piso sube al final, el gráfico parecía decir
  que todo andaba mal, y el profesor lo marcó. Ahora van primero las barras de «error que
  evita el modelo», que arrancan de cero, y el error en crudo queda abajo, sin retocar.
- **Explorá, ejes:** la primera versión sólo mostraba el material. El profesor pidió cambiar
  los ejes, con lo que dice el modelo fijo, para ver si algo explica los errores. Ahora el
  eje horizontal es material, reloj o rating previo. Con el rating se ven 951 de las 2.000
  partidas, las que tienen el rating previo de los dos jugadores (a la otra mitad le falta
  alguno: `diferencia_rating` en `src/build_app.py`), y la página lo avisa.
- **Peso de Explorá:** la primera spec pesaba 17,6 MB, porque Altair repetía los datos
  dentro de cada capa. Con la tabla de partidas como dataset con nombre y los campos de
  la partida fuera de cada fila, quedó en ~4 MB (430 KB comprimido).

## Cómo llega el modelo a la app, y qué pasa con un caso raro

- **El tallo y Explorá** no ejecutan el modelo en el navegador. Las predicciones de test
  se calculan en el build con `models/modelo_en_vivo.joblib` y viajan con los datos.
- **Probá el modelo** (Jugar y Analizar) llama a la API, que carga el mismo artefacto y
  usa `src.predict.predecir`, verificado contra el camino de entrenamiento a 1e-9 (sección
  9 del 04).
- **Caso raro:** si un rating cae fuera del rango que vio el modelo (`rango_rating` del
  artefacto), o si la diferencia entre los dos supera los 400 puntos (el doble de lo que
  empareja Chess.com), `web/components/AvisoRango.tsx` lo avisa arriba de la barra.

## Pendiente

- Publicar en una URL. Propuesta: API en Hugging Face Spaces y web en Vercel; ver la fase 5 del plan.
  Confirmar con el docente que Next.js + FastAPI vale en lugar de HTML o Streamlit.
- Completar `devolucion-entrega-3.md` después del 28/10.

La configuración del despliegue está preparada en `deploy/README.md`: API Docker,
`CORS_ORIGINS`, web con `NEXT_PUBLIC_API_URL` y exportador del paquete del Space.
No se publica en el cierre del 23/10 por decisión del usuario. La verificación local,
incluido el recorrido de la trivia, está en
[`cierre-app-entrega-4-2026-10-23.md`](../auditorias/cierre-app-entrega-4-2026-10-23.md).

## Cierre participativo: 90 segundos

1. Abrir `/trivia?modo=expo` antes de la exposición. La posición está sorteada sin
   filtrar por acierto del modelo; puede fallar.
2. Dar 30 segundos para observar tablero, turno y relojes. Votar Blancas / Tablas /
   Negras a mano alzada; registrar la mayoría y confirmar.
3. Pulsar **Ver pronóstico**: leer las tres probabilidades, no prometer certeza.
4. Pulsar **Ver resultado**: comparar el pronóstico del curso y el del modelo con lo
   que ocurrió. Finalizar con **Ver marcador**.
5. Si queda tiempo, abrir el análisis local y **Ver resumen animado**. No necesita
   acceder a Chess.com ni cargar el modelo en ese momento.

El marcador ilustra un caso, no estima calidad global. La evidencia de calidad sigue
siendo la validación temporal y las métricas del notebook 04. Un cambio en la curva es
un cambio en el pronóstico; no prueba que esa jugada causara el desenlace.

## Decisión de diseño adicional

La app adopta fondo crema, verde y acentos coral/amarillo, con tarjetas redondeadas,
inspirada en Kizupi (https://onepagelove.com/kizupi). El tallo y sus evidencias se
conservan. Blancas, tablas y negras mantienen el mismo significado y paleta en la
barra, las curvas y Altair. La trivia oculta los resultados hasta la revelación y usa
botones con texto, sin depender solamente del color. El resumen permite pausa,
navegación manual y movimiento reducido.


## Entrada y navegación

La bienvenida (`/`) presenta una posición real y dos accesos: **Jugar la trivia** y
**Conocer el proyecto**. Este último abre `/proyecto`, donde se conservan la pregunta,
la idea central, los tres números y el tallo con las evidencias de las entregas.
En la trivia individual, cada posición se resuelve completa antes de continuar:
respuesta propia → pronóstico del modelo → resultado real → siguiente posición.
