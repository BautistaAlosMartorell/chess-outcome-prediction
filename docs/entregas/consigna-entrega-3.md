# Entrega 3 · Modelado
## Proyecto Integrador · Ciencia de Datos 2026
**UTN FRM — Consigna de la cátedra, transcripta tal cual**

Miércoles 28 de octubre, la clase completa, y cinco grupos de la 5K10 el viernes 30. Cada grupo pasa 25 minutos con el docente, en privado. No hay audiencia de otros grupos.

En la Entrega 2 la pregunta era si sabías qué tiene adentro tu dataset. Ahora la pregunta es otra: ¿tenés un modelo que dice algo que los datos solos no decían, y podés explicar por qué es ese y no otro?

Lo que se corrige no es el número final. Un modelo modesto, bien medido y bien explicado vale más que uno brillante que nadie sabe de dónde salió. Y el modelo que elijas acá es el que va a usar la aplicación de la Entrega 4.

> Nuestro proyecto **tiene objetivo** (`resultado`, clasificación; `plies_restantes`, regresión). Cómo lo cubre el notebook: `docs/entregas/plan-entrega-3.md` y `notebooks/04_modelado.ipynb`.

---

## Dos entregas distintas, según tu proyecto

Lo que se pide depende de si tu proyecto tiene una variable objetivo. Fijate en cuál de los dos casos estás y leé esa sección; la otra no es para vos.

| Tu proyecto | Qué es | Qué se pide |
|---|---|---|
| Tiene objetivo: una columna que querés predecir | Clasificación si es una categoría, regresión si es un número | Un modelo que le gane al piso por más que el ruido, elegido con validación cruzada y leído |
| No tiene objetivo: buscás grupos, perfiles o segmentos | Agrupamiento | Grupos elegidos con una medida interna, descriptos y con un nombre que se pueda defender |

Lo que viene después de esas dos secciones —qué traer, cómo son los 25 minutos y cómo se aprueba— vale para todos.

---

## Si tu proyecto tiene objetivo

Antes del primer modelo, cuatro decisiones, porque todo lo demás se lee contra ellas:

- **La métrica, declarada antes de elegir.** Ninguna es la correcta en abstracto: depende de qué error te cuesta más en tu problema. Con clases desparejas, la accuracy esconde a la clase chica y el f1 macro la ve. En regresión, el MAE se lee en las unidades de tu objetivo —«le erramos por 40.000 pesos en promedio»— y por eso es el más fácil de defender.
- **El piso.** Un modelo que no mira ninguna columna —`DummyClassifier` o `DummyRegressor`—, medido con la misma validación que todo lo demás. Sin ese número, el de tu modelo no significa nada.
- **La validación imita el uso.** Los pedazos se arman como se va a usar el modelo, y el test se separa con el mismo criterio:

  | Si tus filas… | Los pedazos se arman… | Con |
  |---|---|---|
  | son independientes entre sí | al azar, estratificando si es clasificación | `StratifiedKFold` o `KFold` |
  | se repiten por entidad: varias filas por partida, por usuario, por carrera, por club | por entidad: la misma nunca queda de los dos lados | `StratifiedGroupKFold` o `GroupKFold`, con `groups=` |
  | están en el tiempo y vas a predecir lo que viene | por fecha: se entrena con lo anterior y se valida con lo posterior | `TimeSeriesSplit`, con las filas ordenadas por fecha |

- **Todo adentro de un pipeline.** Imputar, escalar, codificar y las columnas que derivaste van adentro del objeto que se entrena. Lo que se calcula afuera, sobre el dataset entero, ya vio el test.

### La comparación

- **El modelo simple primero:** una regresión logística, o lineal si tu objetivo es un número, con el pipeline completo. Es la referencia contra la que se justifica cualquier otro.
- **Al menos dos familias más** —un árbol, un bosque, un boosting— sobre las mismas columnas y con la misma validación, con media y desvío. Si el complejo no le gana al simple por más que el desvío, se queda el simple.
- **El ajuste de hiperparámetros del elegido**, con una grilla o una curva de validación, y la tabla completa, no sólo el ganador.
- **Si hay clases desparejas**, qué decidiste —`class_weight`, mover el umbral, o nada— y qué costó en la métrica que declaraste.
- **Las columnas que probaste y no sirvieron**, con el número con y sin cada una. También son evidencia.

### El modelo final, leído

- **Medido una vez sobre el test.** Todo lo que se elige —modelo, hiperparámetros, columnas, umbral— se elige con validación cruzada sobre el entrenamiento. Si mirás el test, cambiás algo y lo volvés a mirar, ya no es un test.
- **Dónde se equivoca.** En clasificación, la matriz de confusión normalizada por fila y por columna, y el reporte por clase. En regresión, lo real contra lo predicho, y en qué tramo del objetivo se erra más.
- **En qué se apoya.** Los coeficientes con su signo, o la importancia por permutación. Si la columna que más pesa te sorprende, sospechá de una fuga antes de festejar.

Una validación al azar sobre filas que no son independientes da números más altos que los reales, y la diferencia es exactamente la fuga que no viste. Es el error más caro de esta entrega, porque no da ningún aviso: el número sale lindo.

### Lo que se pregunta

- Por qué esa métrica: qué error es más caro en tu problema, y si la métrica lo ve.
- Cuánto le gana tu modelo al piso, y si eso es mucho o poco para lo que querés hacer con él.
- Por qué los pedazos de la validación se arman así, y qué le pasaría al número si los armaras al azar.
- Por qué ese modelo y no uno más complejo, con la diferencia y el desvío a la vista.
- Una confusión concreta del modelo, o un tramo donde erra mucho, y una explicación desde tu dominio.
- La columna que más pesa, y qué hiciste para descartar que sea una fuga.

---

## Si tu proyecto no tiene objetivo

No hay métrica contra una respuesta, porque no hay respuesta. No se pide un piso, ni una comparación de modelos, ni un test. Se pide esto, en este orden:

- **Las columnas de la distancia, elegidas y escaladas, con el motivo.** Qué entra en la distancia es la primera decisión del modelo y la que más cambia el resultado. La escala también es parte del modelo: si una columna va de 0 a 100 y otra de 0 a 100.000, la segunda decide sola.
- **k elegido con una medida interna** —el silhouette, o el codo de la inercia— y la curva mostrada, no sólo el valor. En la curva de la inercia, con k = 1 adentro.
- **Los grupos descriptos:** cuántos elementos tiene cada uno, su perfil promedio, y un nombre que se pueda defender con una columna. Un cluster sin descripción es un número.
- **La decisión sobre lo que domina.** Si un grupo se lleva todo, o una columna corta sola, qué hiciste y qué cambió después.
- **Una proyección para mirar:** los datos en dos componentes de PCA, coloreados por grupo, y si los grupos se separan o son cortes de un degradé.
- **Lo que no apareció.** Si esperabas cinco tipos de usuario y el silhouette dice dos, eso es el resultado, y se escribe.

Todo adentro de un pipeline, igual que en supervisado: elegir y escalar las columnas es el primer paso, y agrupar el último.

Un cluster no es una categoría que existía y se descubrió: es un corte que el algoritmo hizo porque se lo pidieron. Si tiene sentido, lo tiene por la descripción, no por el silhouette.

### Lo que se pregunta

- Por qué esas columnas en la distancia, y qué pasaría con los grupos si sacaras una.
- Por qué ese k, y si la medida y el codo dicen lo mismo.
- Qué distingue a un grupo de otro, señalando una columna concreta.
- Qué esperabas encontrar y no apareció.

---

## Qué tenés que traer

Para todos. Llegá con esto ya hecho: los 25 minutos son para mostrar y explicar, no para esperar que termine una búsqueda.

| Qué | Detalle |
|---|---|
| El notebook ejecutado | De arriba a abajo, sin errores, con las salidas guardadas y una semilla definida al principio y pasada a todo lo que la acepte. Abierto antes de entrar. |
| El planteo | Con objetivo: qué predecís, la métrica y por qué, el piso y cómo partiste los datos. Sin objetivo: qué columnas entran en la distancia y por qué. |
| El resultado | Con objetivo: la tabla de comparación y el modelo final leído. Sin objetivo: la elección de k y los grupos descriptos. |
| Lo que te marcamos en la Entrega 2 | Resuelto, o con una explicación de por qué no se pudo. |

## Cómo se organizan los 25 minutos

| Min. | Momento | Qué pasa |
|---|---|---|
| 0–2 | Qué cambió | Qué se corrigió desde la Entrega 2, y si cambió el objetivo o las columnas. Dos oraciones. |
| 2–7 | El planteo | Con objetivo: qué predecís, con qué métrica, cuánto da el piso y cómo armaste la validación. Sin objetivo: qué columnas entran en la distancia y cómo las escalaste. |
| 7–16 | El resultado | Con objetivo: la comparación, el ajuste y el modelo final, con dónde se equivoca y en qué se apoya. Sin objetivo: la elección de k, los grupos y sus nombres, y lo que no apareció. |
| 16–22 | Preguntas dirigidas | El docente pregunta, a integrantes puntuales, sobre cualquier parte de lo anterior. |
| 22–25 | Devolución | Qué está bien, qué hay que corregir antes de la Entrega 4. |

La evaluación es individual. Repartirse el trabajo está bien; desentenderse de la parte del otro, no. La pregunta sobre la validación puede caerle a quien armó las columnas.

## Cómo se aprueba

- El notebook corre entero, con una semilla y las salidas guardadas.
- Todo lo que se le hace a los datos está adentro de un pipeline.
- Con objetivo: la métrica está declarada, el piso medido, al menos tres modelos comparados por validación cruzada con media y desvío, el elegido ajustado, el test mirado una vez y el modelo final leído.
- Sin objetivo: las columnas de la distancia están justificadas, k se eligió con una medida interna y cada grupo está descripto y tiene nombre.
- El grupo puede decir qué probó y no anduvo.
- Las respuestas no vienen de una sola persona.

## Tres formas de perder los 25 minutos

- **El número que da demasiado bien.** Un f1 de 0,99 o un silhouette de 0,9, festejados sin sospechar. Con objetivo, casi siempre es una columna que contiene la respuesta o una validación que dejó la misma entidad de los dos lados. Sin objetivo, casi siempre es un grupo que se lleva todo o una columna que domina la distancia.
- **El zoológico.** Diez modelos con sus valores por defecto, uno al lado del otro, sin desvío y elegidos por el test; o cinco algoritmos de agrupamiento y ningún grupo descripto. Cantidad no es comparación.
- **Que hable uno solo.** Es el error más caro, porque las preguntas van dirigidas y la nota es individual.

Si tu modelo no le ganó al piso, o los grupos no dijeron nada, vení igual y decilo. Un grupo que muestra un resultado que no anduvo y entiende por qué se lleva una devolución útil, y a veces ese es el resultado más honesto del proyecto. Uno que no se presenta, no.
