# Devolución de la Entrega 4 y cómo se resolvió

El profesor revisó la app en la clase de la Entrega 4 (noviembre de 2026). Este documento
junta lo que pidió, qué se hizo con cada pedido, dónde está en el repo y qué falta. Se
armó escuchando la devolución grabada por el grupo; es nuestra lectura, no una cita.

La idea de fondo que marcó: la app no es una presentación de diapositivas. Sirve para usar
los datos y explicar **por qué el modelo anda como anda** y justificar sus errores. Y en la
exposición tiene que hablar cada integrante, explicando sobre todo el porqué.

## Qué pidió y cómo se resolvió

| # | Pedido | Qué se hizo | Dónde |
|---|---|---|---|
| 1 | Que el texto de cada gráfico ayude a entenderlo y esté basado en él | Cada sección tiene tres paneles: «Qué se ve», «Por qué está acá» y «Cómo lo sabemos». «Las hipótesis», que no tenía «Por qué está acá», ahora lo tiene | `/proyecto`; PR #39 y PR #40 |
| 2 | Explicar qué es el «material» | Un cuadro con el valor de las piezas (peón 1, caballo y alfil 3, torre 5, dama 9) y cómo se suma | `/proyecto`, «En qué se fija»; PR #39 |
| 3 | Decir desde qué ply empiezan a pesar el material y el reloj | Una de las tres cifras de «Lo que encontramos»: «40 a 60 plies» en que las dos superan el umbral de señal débil | `/proyecto`; PR #39 |
| 4 | El gráfico del error parece que «empeora»: mostrarlo como logro y que arranque de cero | Se agregó la vista «Error que evita el modelo» (barras desde cero) y ahora va **arriba**; el error en crudo queda abajo | `src/app_charts.py` (`modelo_contra_piso`); PR #39 y rama `ejes-explora` |
| 5 | Mostrar los resultados en crudo, «sin hacer trampa» | El modelo y el piso se muestran juntos y sin retocar; el «Por qué está acá» lo dice | `/proyecto`, «El modelo»; PR #39 |
| 6 | Contar el recorrido: «antes teníamos X, por eso ahora Y» | Línea de tiempo «¿Cómo llegamos hasta acá?», una tarjeta por entrega. La tarjeta de la Entrega 4 decía «una sola cifra de error»: ya se mostraba el error por corte, así que se corrigió | `web/components/Recorrido.tsx`; PR #39 y rama `ejes-explora` |
| 7 | Importancia de las columnas: un gráfico por columna, a la misma escala, mirando la importancia y no el error | Cinco gráficos de área, uno por columna, con la misma escala | `/proyecto`, «En qué se fija»; PR #39 |
| 8 | Explicar por qué sigue fallando cerca del 30 % al final, usando los datos | Sección «Los errores»: mapa de calor del acierto por situación (material o reloj parejo, ventaja chica o grande) y cómo terminaron las partidas donde acertó y donde falló. El 53 % de los errores entre los plies 95–120 son tablas | `/proyecto`, «Los errores»; PR #39 |
| 9 | Explorá: cambiar los ejes, con lo que dice el modelo fijo, para ver si algo explica los errores | El eje horizontal se elige entre material, reloj y **rating previo**. Con el rating se ven 951 de las 2.000 partidas, las que tienen el rating previo de los dos jugadores, y la página lo avisa. Además, el botón «Reproducir» hace avanzar el corte solo | `/explora`; PR #39 (material y reloj) y rama `ejes-explora` (rating) |
| 10 | Si un gráfico de Explorá sirve, usarlo en el tallo | «Los errores» usa el mismo tipo de lectura (material y reloj) y enlaza a Explorá para ver las partidas una por una | `/proyecto`; PR #39 |
| 11 | Que se entienda para qué es la aplicación | La portada dice para qué sirve («ver por qué el modelo anda como anda y dónde se equivoca») y define el piso | `/proyecto`; PR #40 y rama `ejes-explora` |
| 12 | «Las hipótesis», en palabras | Título que afirma, tabla con el veredicto en lenguaje llano y, en «Cómo lo sabemos», las medidas originales del análisis exploratorio | `/proyecto`; rama `ejes-explora` |

La trivia, Jugar y Analizar no cambiaron: el profesor dijo que estaban bien.

Lo que se rehízo después para la exposición final (capítulos con «Teníamos → Por eso», texto
visible en cada gráfico, crudos y menos líneas) está en el [CHANGELOG](../CHANGELOG.md), entrada del
23/11/2026. Reemplaza las filas 1, 2, 3, 6, 7 y 12 de la tabla.

## Cómo se verificó

- `python -m unittest tests.test_build_app tests.test_metricas_tramo tests.test_api`: pasan.
- `cd web && npm run typecheck && npm test && npm run build`: sin errores.
- Se recorrieron `/proyecto` y `/explora` en el navegador: los tres ejes, el aviso del rating
  y el orden de «El modelo».

## Detalle de los datos generados

Los gráficos y el resumen de `web/public/app/` los genera `python -m src.build_app`. La rama
`ejes-explora` no los regeneró enteros: conserva las probabilidades que ya estaban en `main`
(las del modelo con el que se generó el PR #39) y sólo suma lo nuevo:

- `explora.json`: el campo `dif_rating` por partida (null cuando falta el rating previo de
  alguno de los dos) y las transformaciones del tercer eje.
- `modelo.json`: el orden de las dos vistas.
- `resumen.json`: `explora.partidas_con_rating`.

El rating previo es el que lee el modelo (`diferencia_elo_previa`, calculada con las partidas
que cada jugador terminó antes del inicio), no el rating que informa Chess.com después de la
partida. Se calcula con `diferencia_rating` en `src/build_app.py`.

## Qué falta

- **Modelo oficial.** Dos corridas locales del notebook 04 dan lo mismo en total (log-loss 0,79,
  62,3 % de aciertos) pero difieren en las probabilidades por partida, hasta varios puntos en
  algún caso. El grupo tiene que acordar con qué `models/modelo_en_vivo.joblib` se regeneran
  los datos y se publica la API, y volver a correr `build_app` una vez.
- **Notebooks 04 y 05.** Las cifras de la app y los notebooks versionados tienen que
  coincidir, y los datos del PR #39 se regeneraron sin los notebooks.
- **Textos del recorrido.** Los escribió una persona: falta que el grupo los valide.
- **Los errores del final.** El texto de «Los errores» dice que falta comprobar si otras
  columnas ayudarían con las posiciones parejas. No se probó.
- **URL pública.** Todavía no está publicada (ver `deploy/README.md`).
