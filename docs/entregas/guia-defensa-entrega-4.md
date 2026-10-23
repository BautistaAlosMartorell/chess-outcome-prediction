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

### Los datos: `partidas_vivas`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | Una fila por (ritmo, corte): cuántas partidas tienen fila en ese corte y qué fracción del ritmo es | Es la unidad de modelado (partida × corte) vista desde arriba |
| Marca | Línea + punto | Es una evolución a lo largo de un eje ordenado (los plies) |
| x | `corte_ply`, cuantitativa, 0 a 120 | El tiempo de la partida |
| y | `siguen`, cuantitativa, formato % | Fracción, para comparar ritmos de distinto tamaño |
| color | `TimeClass`, nominal, escala `ESCALA_RITMO` | Tres categorías sin orden |
| Transformación | Ninguna en el gráfico; el conteo se hace en `build_app.partidas_vivas` | |

### Lo que encontramos: `senal_por_corte`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | η² por corte (10 a 60) del material y del reloj a igual material, del notebook 02 | Las dos hipótesis de la Parte B sobre la población común |
| Marca | Línea + punto, más una regla horizontal punteada en 0,05 | La regla es el umbral de señal débil del EDA, fijado antes de mirar |
| x | `corte_ply`, cuantitativa (dominio 5–65) | Sólo hay cortes con jugadas: en el 0 material y reloj son iguales |
| y | `eta2`, cuantitativa, formato % | Proporción de la variación del resultado que explica la variable |
| color | `variable`, nominal, `ESCALA_VARIABLE` | Dos series |
| Transformación | Ninguna en el gráfico. El reloj usa el η² **controlado** (dentro de bandas de material), calculado en el 02 | Así "el reloj suma aunque el material esté parejo" se ve en el gráfico |

### El modelo: `modelo_contra_piso`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | Log-loss de test por corte del modelo y del piso, recalculada por el build y verificada contra el 04 | Coincide con la tabla de la sección 8 del 04 |
| Marca | Línea + punto | Evolución por corte |
| x | `corte_ply`, cuantitativa | |
| y | `log_loss`, cuantitativa, sin cero (`zero=False`) | La diferencia entre las líneas es lo que importa; con cero se aplastaría |
| color | `serie` (Modelo / Piso), `ESCALA_SERIE` | El modelo en ámbar, el color de "lo que está pasando" en toda la app |
| Tooltip | Log-loss, mejora sobre el piso, partidas de test en el corte | |

### Explorá: `explora`

| Componente | Qué es | Por qué |
|---|---|---|
| Datos | Dos tablas: `filas` (una por partida y corte: material y las tres probabilidades) y `partidas` (una por partida: jugadores, ritmo, nivel, resultado). Se unen con `transform_lookup` por `id` | La tabla de partidas va una sola vez (dataset con nombre): el archivo pesa ~4 MB en lugar de 17 |
| Marca (arriba) | Círculo | Una partida = un punto |
| x | `material_visible` = material + un desplazamiento fijo por partida (`transform_calculate`) | El material es entero: sin desplazamiento, los puntos se apilan en columnas |
| y | `ventaja` = P(blancas) − P(negras) (`transform_calculate`), de −100 % a +100 % | Lo que dice el modelo en un solo eje |
| color | `resultado` real, `ESCALA_RESULTADO` | Los mismos colores que la barra de Jugar y Analizar |
| tamaño | Condición: más grande si es la partida elegida | |
| Tooltip | Jugadores, ritmo, nivel, corte, material, las tres probabilidades, resultado y cómo terminó | Detalle a pedido, con el modelo |
| Marca (abajo) | Área apilada normalizada de las tres probabilidades de la partida elegida, a lo largo de todos los cortes (`transform_fold`), y una regla en el corte del deslizador | Es la barra de la app, desplegada en el tiempo |

## Qué toca cada control

| Control | Param de Altair | Componente que toca |
|---|---|---|
| Deslizador "Plies jugados" | `corte` (`binding_range`, 0–120, paso 5) | El **filtro** del panorama (`datum.corte_ply == corte`) y la posición de la regla ámbar del detalle |
| Menú "Ritmo" | `ritmo` (`binding_select`) | El **filtro** del panorama (`ritmo == 'todos' \|\| datum.TimeClass == ritmo`) |
| Menú "Nivel" | `nivel` (`binding_select`) | El **filtro** del panorama, igual con `nivel_promedio` |
| Clic en un punto | `elegida` (`selection_point` sobre `id`) | El **filtro** del gráfico de abajo y el **tamaño** del punto elegido. Doble clic la suelta |

## Una decisión de diseño que cambió

- **Explorá, primera versión:** el clic en un punto llevaba a `/analizar` con esa partida.
  No funcionaba por dos razones. Analizar sólo encuentra las *últimas* partidas de un
  usuario en Chess.com, y una de julio podía no estar. Además, Analizar arma el historial
  con lo que Chess.com devuelve *hoy*, así que la curva no coincidía con la del notebook.
  Ahora el detalle es un segundo gráfico de Altair, con las probabilidades del modelo tal
  como las mide el 04.
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
