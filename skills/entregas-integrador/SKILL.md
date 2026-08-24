---
name: entregas-integrador
description: Cronograma, requisitos y criterios de evaluación del Proyecto Integrador de Ciencia de Datos (UTN FRM 2026) - qué pide cada una de las 4 entregas, fechas, los 7 criterios de una buena fuente de datos y en qué punto del proyecto estamos. Usar para planificar trabajo, priorizar tareas, evaluar si algo alcanza para una entrega o validar una fuente de datos nueva. Triggers - entrega, cronograma, consigna, deadline, qué falta, evaluación, fuente de datos.
---

# Entregas del Proyecto Integrador

Contexto de la cátedra para saber qué se está construyendo y para cuándo.
Documento fuente completo: `Kit_de_arranque_Proyecto_Integrador_2026.md` en la raíz.

## El proyecto

Qué combinación de **ELO**, **apertura**, **modalidad de ritmo** (bullet/blitz/rapid)
y **color de piezas** predice el **resultado** (`resultado`: gana blancas/negras/
empate) y la **duración** (`cantidad_jugadas`) de una partida de ajedrez online real.
Unidad de análisis: una partida individual.

Fuente: API pública de Lichess (`GET /api/games/user/{username}`), sin autenticación.
Partidas reales de 8 jugadores en distintos rangos de ELO (nivel club a campeón
mundial). Ver el README del repo para el contexto completo de por qué el tema del
proyecto cambió dos veces antes de llegar a este.

El integrador vale el **50 % de la nota final** — el doble que los cuatro TPs juntos y
el doble que los dos parciales. Se aprueba con 60 %.

## Cronograma

| Entrega | Fecha | Qué se presenta |
|---|---|---|
| Definición | 12/08/2026 | Grupo, pregunta y fuente de datos |
| 1 · Ingeniería de datos | **02/09/2026** | Pipeline automatizado que produce el dataset |
| 2 · Análisis exploratorio | **16/09/2026** | Exploración, hipótesis y hallazgos |
| 3 · Modelado | **14/10/2026** | Objetivo predictivo, modelos comparados y métricas |
| 4 · Visualización e integración | **04/11/2026** | Visualizaciones y aplicación funcionando |
| Exposición final | 18/11/2026 | Proyecto completo y demo en vivo |
| Recuperación | 25/11/2026 | Para los grupos que la necesiten |

## Estado del repo

<!-- Actualizar esta sección al cerrar cada entrega. -->

**Al 24/08/2026:** Tercer tema del proyecto (los dos anteriores — transporte AMBA
multimodal y demanda de subte+clima+feriados, este último completo en la rama
`colectivos` — quedaron descartados o en otra rama por decisión del grupo, no por
fallas). Pipeline de ajedrez online (Lichess) escrito completo en `src/` y validado
línea por línea contra una muestra real de 3 partidas, pero **sin correr todavía con
volumen real** por una restricción de red del entorno donde se escribió (el endpoint
funciona bien desde un navegador normal). Pendiente antes de dar la Entrega 1 por
cerrada: correr `python -m src.pipeline` de punta a punta desde una máquina sin ese
bloqueo y confirmar los números reales (filas, distribución de targets, nulos).

## Qué pide cada entrega

**1 · Ingeniería de datos.** Pipeline que baja los datos sin intervención humana y los
convierte en el dataset de trabajo. Lo que se mira: que corra de punta a punta, que esté
explicado, y que las decisiones de limpieza y unión estén justificadas.

**2 · Análisis exploratorio.** Hipótesis escritas *antes* de mirar, exploración que las
pone a prueba, y hallazgos concretos sobre los datos propios. No es una galería de
gráficos: cada gráfico responde una pregunta. Acá se ve si la variable objetivo tiene
señal aprovechable y si las clases están tan desbalanceadas como para condicionar la
Entrega 3.

**3 · Modelado.** Objetivo predictivo bien planteado, varios modelos comparados con las
mismas métricas, y una justificación de por qué esas métricas. Es la entrega donde se
rompen los proyectos con fuentes flojas.

**4 · Visualización e integración.** Visualizaciones que comunican los hallazgos y una
aplicación funcionando. Demo en vivo en la exposición final.

## Los 7 criterios de una buena fuente

Para validar cualquier fuente nueva que se quiera sumar al proyecto.

**Eliminatorios** — si falla uno solo, la fuente no sirve:

1. **Datos tidy** — cada fila una observación, cada columna una variable.
2. **Unidad alineada con la pregunta** — la fila es aquello sobre lo que se quiere concluir.
3. **Algo modelable** — hay variable a predecir o estructura latente.
4. **Descargable de forma automatizada** — URL, API o página scrapeable, sin intervención humana.

**Facilitadores** — no rompen el proyecto pero lo complican:

5. **Volumen** — > 1.000 filas, ideal > 10.000.
6. **Columnas informativas** — ≥ 5 útiles, mezclando numéricas, categóricas y fechas.
7. **Documentación entendible** — qué significa cada columna y en qué unidades.

## Cómo se evalúa

- Cada entrega es una **reunión privada** del grupo con el docente: se expone el avance,
  el docente pregunta y devuelve en el momento. La exposición final sí es pública.
- **La evaluación es individual.** Las preguntas van dirigidas a integrantes puntuales
  sobre cualquier parte del trabajo. Repartir tareas está bien; desentenderse de las
  partes ajenas, no. Consecuencia directa para el código: tiene que estar escrito de
  forma que cualquiera del grupo lo pueda explicar.

## Los TPs son el entrenamiento

Cuatro TPs sobre el dataset FIFA que provee la cátedra, uno por unidad. Cada TP enseña la
técnica en un caso controlado y la entrega del integrador la aplica a datos propios, más
sucios. **El TP se hace antes de encarar la entrega correspondiente** — el orden importa.

| Unidad | TP sobre FIFA | Se aplica en |
|---|---|---|
| 1 | Pipeline que scrapea sofifa.com | Entrega 1 |
| 2 | Explorar el dataset de jugadores | Entrega 2 |
| 3 | Predecir la posición de un jugador | Entrega 3 |
| 4 | Visualizar y comunicar hallazgos | Entrega 4 |

## El error de gestión más común

Trabajar el integrador la semana previa a cada entrega. Las entregas están separadas por
tres o cuatro semanas y eso genera la ilusión de que sobra tiempo. Cada entrega se apoya
en la anterior: llegar con lo mínimo a la Entrega 1 significa arrastrar un pipeline frágil
hasta noviembre. Se trabaja en paralelo a la cursada, todas las semanas.
