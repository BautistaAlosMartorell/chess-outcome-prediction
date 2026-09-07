# Kit de arranque
## Proyecto Integrador · Ciencia de Datos 2026
**UTN FRM — Ingeniería en Sistemas de Información · Clase 1 · 12/08/2026**

Este documento es lo mínimo que necesitás para arrancar hoy. Queda publicado en el campus todo el cuatrimestre: es el mapa del proyecto de punta a punta. El detalle de qué se pide en cada entrega está en el mosaico de cada unidad, y cómo se corrige, en la página "Cómo se evalúa". Hoy alcanza con esto.

---

## 1. Qué es el Proyecto Integrador

Un proyecto de ciencia de datos de punta a punta, sobre un problema que elige tu grupo y datos que consigue tu grupo. Empieza hoy y termina el 18 de noviembre.

Vas a recorrer el ciclo completo: conseguir los datos y automatizar su descarga, explorarlos, modelarlos, visualizarlos y comunicar lo que encontraste en una aplicación funcionando.

Es el eje de la materia, no un anexo. Tres datos para dimensionarlo:

- Vale el **50 %** de la nota final — el doble que los cuatro trabajos prácticos juntos, el doble que los dos parciales.
- Ocupa **cuatro clases completas** del cuatrimestre, dedicadas exclusivamente a las entregas.
- Cada TP práctico de la materia está diseñado para prepararte para la entrega del integrador que viene después.
- Se aprueba con el **60 %**. Hay una instancia de recuperación al final del cursado.

---

## 2. Qué tenés que resolver hoy

Dos cosas, y las dos salen cerradas de esta clase:

| # | Qué | Cómo queda registrado |
|---|-----|------------------------|
| 1 | Tu grupo, de 5 a 6 integrantes | Formulario de la cátedra, antes de terminar la clase |
| 2 | Tu pregunta y tu fuente de datos, validadas por el docente | Mismo formulario |

Que salgan cerradas hoy no es un formalismo. Todo lo que viene después se apoya en esta decisión: el pipeline que vas a construir, el análisis que vas a hacer sobre él, el modelo que vas a entrenar y la aplicación que vas a mostrar en noviembre.

Una fuente floja no da la cara enseguida — aguanta la primera entrega y recién se rompe en septiembre u octubre, cuando hay que modelar. Para ese momento, cambiar de fuente significa rehacer todo lo anterior con la mitad del cuatrimestre encima. **Los veinte minutos que le dediques hoy a revisar los criterios valen más que cualquier otra cosa que hagas esta clase.**

---

## 3. Primero la pregunta, después la fuente

En ese orden. No al revés.

1. **¿Qué querés investigar?** Una pregunta acotada, sobre una unidad concreta — un jugador, una transacción, un país-año, un tweet, un paciente.
2. **¿Qué fuente responde esa pregunta?**

Elegir el dataset primero e inventar la pregunta después lleva a proyectos mecánicos, que se hacen cuesta arriba a partir de septiembre. Vas a convivir cuatro meses con esta decisión: que el tema te interese de verdad importa más de lo que parece ahora.

De dónde pueden salir las preguntas: predicción de comportamientos (abandono de clientes, deserción, demanda), análisis de opiniones o textos, segmentación de usuarios o productos, detección de anomalías, patrones espaciales o temporales, análisis de redes. También sirve —y suele funcionar mejor— algo del entorno local, de la facultad, de un trabajo o de un interés personal.

---

## 4. Los 7 criterios de una buena fuente

Se desarrollan en el bloque 2 de hoy, con ejemplos. Acá va el resumen para tenerlo a mano mientras buscás.

### Eliminatorios — sin esto no hay proyecto

| # | Criterio | Qué significa |
|---|----------|----------------|
| 1 | Datos tidy | Cada fila es una observación, cada columna una variable |
| 2 | Unidad alineada con tu pregunta | La unidad de cada fila coincide con aquello sobre lo que querés concluir |
| 3 | Algo modelable | Hay una variable a predecir, o grupos naturales que sospechás encontrar |
| 4 | Descargable de forma automatizada | URL, API o página scrapeable. Sin intervención humana |

**Si tu fuente falla uno solo de estos cuatro, no insistas: buscá otra o ajustá tu pregunta.**

### Facilitadores — no rompen el proyecto, pero lo complican

| # | Criterio | Objetivo | Salida si no lo cumplís |
|---|----------|----------|--------------------------|
| 5 | Volumen suficiente | > 1.000 filas; ideal > 10.000 | Combinar con otra fuente, o acotar el alcance |
| 6 | Varias columnas informativas | ≥ 5 útiles, mezclando numéricas, categóricas y fechas | Derivar variables nuevas, o cruzar con otra fuente |
| 7 | Documentación entendible | Saber qué significa cada columna y sus unidades | Reconstruirla leyendo los datos. Cuesta tiempo |

Si sobre alguno de los siete no podés responder con certeza, todavía no tenés tu fuente.

---

## 5. Errores de años anteriores que no queremos repetir

- **Datos ya agregados.** Promedios por provincia, totales por año. Perdiste la observación individual y con ella la posibilidad de modelar.
- **Sin variable objetivo ni estructura latente.** Un listado de museos con su dirección es información, no un problema de ciencia de datos. En la unidad 3 el proyecto se rompe.
- **Muy pocas filas.** Con 200 registros los modelos no aprenden y los gráficos cuentan anécdotas.
- **Una sola columna útil.** Sin features no hay modelo, y sin dimensiones no hay visualizaciones que cruzar.
- **Bajable solo a mano.** Un PDF con una tabla adentro, un sitio con captcha, una base privada. La unidad 1 pide un pipeline automatizado.
- **Fuente elegida por descarte, sin interés real.** Es el que más caro sale: son cuatro meses.

---

## 6. Cómo se ve el cuatrimestre completo

Cuatro entregas parciales, una por unidad, más la exposición final.

| Entrega | Fecha | Qué se presenta |
|---------|-------|-------------------|
| Definición | 12/08 (hoy) | Grupo, pregunta y fuente de datos |
| 1 · Ingeniería de datos | 02/09 | Pipeline automatizado que produce tu dataset |
| 2 · Análisis exploratorio | 16/09 | Exploración, hipótesis y hallazgos sobre tus datos |
| 3 · Modelado | 14/10 | Objetivo predictivo, modelos comparados y métricas |
| 4 · Visualización e integración | 04/11 | Visualizaciones y aplicación funcionando |
| Exposición final | 18/11 | Presentación del proyecto completo y demo en vivo |
| Recuperación | 25/11 | Instancia para los grupos que la necesiten |

**Cómo son las entregas parciales.** Cada grupo se reúne en privado con el docente: exponen el avance, el docente pregunta y devuelve en el momento. No hay audiencia de otros grupos. La exposición final sí es pública, frente al curso.

**La evaluación es individual.** Aunque el trabajo sea grupal, en cada entrega las preguntas van dirigidas a integrantes puntuales. Con grupos de 5 o 6 personas esto importa: repartir el trabajo está bien, desentenderse de las partes ajenas no.

---

## 7. Los TPs prácticos son tu entrenamiento

Durante el cuatrimestre vas a hacer cuatro trabajos prácticos, uno por unidad, todos sobre un mismo dataset: **FIFA**, que la cátedra provee.

No son una materia paralela. Cada TP te enseña la técnica con un caso controlado, y la entrega del integrador que viene después te pide aplicar esa misma técnica a tu dataset, que va a ser más sucio, más ambiguo y más difícil.

| Unidad | En el TP practicás sobre FIFA | En el Integrador lo aplicás a tu proyecto |
|--------|-------------------------------|---------------------------------------------|
| 1 · Ingeniería de datos | Armar un pipeline que scrapee sofifa.com | Tu pipeline, sobre tu fuente → Entrega 1 |
| 2 · Análisis exploratorio | Explorar el dataset de jugadores | Tu exploración → Entrega 2 |
| 3 · Machine Learning | Predecir la posición de un jugador | Tu problema predictivo → Entrega 3 |
| 4 · Visualización | Visualizar y comunicar los hallazgos | Tus visualizaciones y tu app → Entrega 4 |

La consecuencia práctica: el TP se resuelve en casa y se entrega por campus, pero conviene hacerlo **antes** de encarar la entrega del integrador correspondiente. El orden importa.

---

## 8. El error de gestión más común

**Trabajar el integrador la semana previa a cada entrega.**

Las cuatro entregas están separadas por tres o cuatro semanas, y esa distancia genera la ilusión de que hay tiempo de sobra. No lo hay: cada entrega se apoya en la anterior, y llegar con lo mínimo a la Entrega 1 significa arrastrar un pipeline frágil hasta noviembre.

**El proyecto se trabaja en paralelo a la cursada, todas las semanas.** Los espacios de consulta en clase están para eso.

---

## 9. Antes de irte hoy

- [ ] Grupo armado, de 5 a 6 integrantes
- [ ] Pregunta escrita en una frase
- [ ] Fuente identificada, con su URL
- [ ] Los 7 criterios revisados sobre esa fuente
- [ ] Fuente validada con el docente
- [ ] Formulario completado

---

*Ciencia de Datos · UTN FRM · Ciclo lectivo 2026*
