# Entrega 4 · Visualización y app
## Proyecto Integrador · Ciencia de Datos 2026
**UTN FRM — Consigna de la cátedra, transcripta tal cual**

Miércoles 11 de noviembre, la clase completa, y cinco grupos de la 5K10 el viernes 13. Cada grupo pasa 25 minutos con el docente, en privado. No hay audiencia de otros grupos.

En las tres entregas anteriores construiste las piezas: un pipeline que produce el dataset, un análisis que dice qué tiene adentro y un modelo que dice algo que los datos solos no decían. Ahora la pregunta es otra: ¿alguien que no estuvo en tu proyecto puede entender lo que encontraste, creerte, y después hacerle sus propias preguntas a tus datos?

Lo que se entrega es la versión final del proyecto: una aplicación web, publicada en una URL, que cuenta el proyecto entero y deja usarlo. Es la misma aplicación que vas a mostrar en la exposición final del 25 de noviembre, así que lo que se corrija acá es lo que llega a esa instancia.

> Cómo lo cubre nuestro proyecto: plan en `docs/entregas/plan-entrega-4.md`. La app es
> la de `web/` (Next.js) + `api/` (FastAPI); la consigna nombra HTML o Streamlit, así que
> la forma de publicación se confirma con el docente.

---

## El ejemplo

En el aula está la aplicación de ejemplo, hecha sobre el dataset canónico: «¿Se puede adivinar la posición?». Abrila antes de leer el resto: cada cosa que pide esta consigna está ahí, y es más fácil de entender viéndola. No es un molde: tu proyecto tiene otra pregunta, otros datos y otros hallazgos, y la aplicación tiene que ser la tuya.

## La forma: una copa de martini

La aplicación entera es una copa de martini. Primero el tallo, que guía el autor: el usuario recorre el proyecto en el orden que elegiste, y cada sección le cuenta un hallazgo. Después la copa, que maneja el usuario: explora tus datos y prueba tu modelo, ya sabiendo qué mirar.

| Parte | Sección | Qué tiene | Cierra |
|---|---|---|---|
| Portada | El proyecto | La pregunta, la idea central en una oración con sujeto y verbo, y tres números que la sostienen. | La definición |
| Tallo | Los datos | Un título que afirma algo de los datos, y un gráfico que lo muestra. | La Entrega 1 |
| Tallo | Lo que encontramos | Un título que afirma el hallazgo principal del análisis, y un gráfico que lo muestra. | La Entrega 2 |
| Tallo | El modelo | Un título que afirma qué logró el modelo, y un gráfico que lo muestra. | La Entrega 3 |
| Copa | Explorá | Tus datos, con el resultado del modelo, para que el usuario los recorra. | Todas |
| Copa | Probá el modelo | El usuario carga un caso nuevo y ve qué dice el modelo. | La Entrega 3 |

El nombre y el diseño de cada sección son decisión del grupo. Lo que tiene que estar es esto.

## El tallo: cada sección, un hallazgo

Cada sección del tallo cuenta una cosa, y tiene tres partes:

- **Un título que afirma.** No «Distribución de los roles», sino «Hay seis roles de campo, y uno de ellos es mucho más chico que el resto». Si la sección no tiene algo que afirmar, todavía no es una sección del tallo.
- **Un gráfico que prueba el título**, y unas pocas líneas que dicen qué mirar en él.
- **«Cómo lo sabemos»:** un desplegable, cerrado por defecto, con la evidencia técnica de esa etapa. Es lo que convierte el hallazgo en algo que se puede creer.

Lo que va en cada «Cómo lo sabemos»:

| Sección | Qué tiene que estar adentro |
|---|---|
| Los datos | De dónde salen y cómo se obtienen: el pipeline y la fecha de los datos. Qué es una fila. Qué se filtró, paso por paso, con cuántas filas quedaron en cada uno y por qué. Qué columnas se descartaron por fuga. |
| Lo que encontramos | Una hipótesis que se sostuvo y una que no, cada una con su número. Cómo se construyó el gráfico, si hubo alguna transformación que no sea obvia. |
| El modelo | La métrica y por qué. El piso. Cómo se armó la validación. La tabla de comparación con media y desvío, el ajuste del elegido, el resultado en el test y dónde se equivoca. En qué se apoya. Sin objetivo: las columnas de la distancia, la elección de k y la descripción de cada grupo. |

Arriba de todo, la portada: la idea central en una oración, la misma que defendiste en la Entrega 3 o la que salió de corregirla, y tres números que la sostienen. En el ejemplo: «Con sus atributos se adivina el rol del 89 % de los jugadores de campo, y cuando el modelo se equivoca, el 68 % de las veces lo confunde con un vecino de cancha».

## La copa: lo que pregunta el usuario

**Explorá.** La exploración va de lo general a lo particular:

- **Un panorama:** todos los datos, o todo el universo que tenga sentido, en una vista.
- **Zoom y filtro:** al menos dos controles que achiquen el universo —un menú, un deslizador, una selección— y que cambien lo que muestra el gráfico.
- **Detalle a pedido:** la información de cada caso cuando el usuario la pide, al pasar el mouse o al elegirlo, incluido lo que dijo el modelo sobre ese caso.

**Probá el modelo.** Con objetivo: el usuario carga los valores de un caso nuevo y ve lo que predice el modelo, con su probabilidad si es clasificación. Sin objetivo: a qué grupo pertenece un caso que el usuario elige o carga, y qué lo acerca a ese grupo. En los dos casos, el usuario no puede cargar valores que el modelo nunca vio, o la aplicación le avisa cuando lo hace.

## Los gráficos

Hechos con **Altair**. Cada uno tiene que poder leerse componente por componente: datos, mapeo, marca, transformaciones, escalas.

Los colores, las categorías y las escalas significan lo mismo en toda la aplicación. Si el azul es una clase en el tallo, es la misma clase en la copa.

La copa es interactiva; el tallo puede serlo, pero cada gráfico del tallo tiene que decir lo suyo sin que nadie lo toque.

## Dónde corre: HTML o Streamlit

La aplicación se publica en una URL que se abre desde cualquier navegador, sin instalar nada. Hay dos formas, y elige el grupo:

| Forma | Cómo se publica | Lo que hay que resolver |
|---|---|---|
| Una página HTML, como el ejemplo | GitHub Pages, desde el repositorio del grupo. | En el navegador no corre Python. Las predicciones para explorar se calculan antes y viajan con los datos. Para probar el modelo, la fórmula tiene que poder escribirse adentro de la página: una regresión, lineal o logística, o un árbol. |
| Una aplicación de Streamlit | Streamlit Community Cloud, desde el repositorio del grupo. | Corre Python, así que carga cualquier modelo guardado. A cambio, hay que mantenerla publicada y andando. |

Si tu mejor modelo de la Entrega 3 no se puede llevar al navegador, hay dos salidas: Streamlit, o un modelo que sí se puede llevar y que queda a menos de un desvío del mejor. La segunda es una decisión de modelado, y va con sus números en el «Cómo lo sabemos» del modelo, como en el ejemplo.

## El proyecto integrado

La aplicación no es una pieza aparte: es el último paso de la misma cadena.

| Qué | Detalle |
|---|---|
| El repositorio | En GitHub, con el código del pipeline, del análisis y del modelo, y un README que explique cómo se corre todo. |
| La construcción | Un script que toma los datos que produce tu pipeline, carga o entrena el modelo con la misma semilla y genera la aplicación. Si los datos se actualizan, correrlo de nuevo actualiza la aplicación. En el ejemplo es `build_app.py`. |
| El modelo | El elegido en la Entrega 3, con lo que te marcamos corregido. Lo que muestra la aplicación tiene que coincidir con lo que da el notebook. |

## Qué tenés que traer

Llegá con esto ya funcionando. Los 25 minutos son para mostrar y explicar, no para publicar ni para esperar que cargue un modelo.

| Qué | Detalle |
|---|---|
| La aplicación abierta | La URL pública, ya abierta en el navegador antes de entrar. Que funcione en la notebook de alguien del grupo no alcanza. |
| El repositorio | Abierto en GitHub, con el README. |
| Lo que te marcamos en la Entrega 3 | Resuelto, o con una explicación de por qué no se pudo. |

## Cómo se organizan los 25 minutos

| Min. | Momento | Qué pasa |
|---|---|---|
| 0–2 | Qué cambió | Qué se corrigió del modelo desde la Entrega 3. Dos oraciones. |
| 2–10 | El tallo | Recorrés la aplicación como si el docente no conociera tu proyecto: de la portada al modelo, en orden. El docente abre los «Cómo lo sabemos» que quiera. |
| 10–15 | La copa | El docente toma el mouse: explora los datos y prueba el modelo con un caso propio. El grupo responde lo que aparezca. |
| 15–22 | Preguntas dirigidas | El docente pregunta, a integrantes puntuales, sobre cualquier parte de la aplicación o del repositorio. |
| 22–25 | Devolución | Qué está bien, qué hay que corregir antes de la exposición final. |

La evaluación es individual. Repartirse el trabajo está bien; desentenderse de la parte del otro, no. La pregunta sobre un gráfico puede caerle a quien armó la publicación.

## Lo que hay que saber explicar

Esto no lo mide ningún script: se pregunta.

- Por qué cada título del tallo afirma lo que afirma, y qué número lo sostiene.
- Un gráfico de la aplicación, componente por componente: qué variable va a cada canal, qué marca, qué transformación y qué escala, y por qué.
- Una decisión de diseño que cambiaste: qué tenía la primera versión de ese gráfico y por qué no funcionaba.
- Qué componente del gráfico toca cada control de la copa.
- Cómo llega el modelo a la aplicación, y qué pasa si el usuario carga un caso raro.
- Cómo se regenera la aplicación desde el repositorio si cambian los datos.

## Cómo se aprueba

- La aplicación abre en su URL pública y funciona sin errores durante la entrega.
- Está la portada con la oración, y las tres secciones del tallo, cada una con un título que afirma, un gráfico que lo prueba y su «Cómo lo sabemos» completo.
- Está la copa: un panorama, al menos dos controles que cambian el gráfico, detalle a pedido con el resultado del modelo, y una forma de probar el modelo con un caso nuevo.
- Los gráficos están hechos con Altair y el grupo puede leer cualquiera de ellos componente por componente.
- Lo que muestra la aplicación coincide con el notebook, y el repositorio tiene un README con el que otra persona puede regenerarla.
- Las respuestas no vienen de una sola persona.

## Tres formas de perder los 25 minutos

- **El tablero sin historia.** Diez filtros, seis gráficos y ninguna conclusión: todo el control al usuario y ningún mensaje. El usuario no sabe qué mirar, y el docente tampoco.
- **El notebook con otra ropa.** La aplicación copia las celdas del análisis una debajo de la otra: todos los gráficos que se hicieron, sin decir cuáles importan ni por qué. Lo técnico va en los «Cómo lo sabemos», no en el tallo.
- **La aplicación que sólo corre en una notebook.** Si la URL no abre el día de la entrega, no hay entrega que mostrar. Publicá con tiempo y probala desde otra computadora.

Que hable uno solo sigue siendo el error más caro, porque las preguntas van dirigidas y la nota es individual.

Si algo no te dio —el modelo no le gana al piso, un hallazgo no se sostuvo—, la aplicación lo puede contar igual. Una historia honesta sobre un resultado modesto vale más que una aplicación brillante que no se sabe de dónde salió.
