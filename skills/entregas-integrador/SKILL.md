---
name: entregas-integrador
description: Cronograma, requisitos y criterios de evaluación del Proyecto Integrador de Ciencia de Datos (UTN FRM 2026) - qué pide cada una de las 4 entregas, fechas, los 7 criterios de una buena fuente de datos y en qué punto del proyecto estamos. Usar para planificar trabajo, priorizar tareas, evaluar si algo alcanza para una entrega o validar una fuente de datos nueva. Triggers - entrega, cronograma, consigna, deadline, qué falta, evaluación, fuente de datos.
---

# Entregas del Proyecto Integrador

Contexto de la cátedra para saber qué se está construyendo y para cuándo.
Documento fuente completo: `Kit_de_arranque_Proyecto_Integrador_2026.md` en la raíz.

## El proyecto

Qué tan bien se puede predecir el **resultado** (`resultado`: gana blancas/negras/
empate) y la **duración restante** (`plies_restantes`) de una partida de ajedrez online
real **antes de que empiece y a medida que avanza**. Antes de empezar se conocen el nivel,
el ritmo (bullet/blitz/rapid) y el color; durante la partida se suman la apertura, la
posición y los relojes.
Unidad de análisis: la partida en un momento dado (partida × corte de plies: uno cada
5, del 0 al 120). La tabla base sigue teniendo una partida por fila; la de cortes se
deriva.

Fuente: PubAPI pública de Chess.com (`/pub/player/{username}/games/{YYYY}/{MM}`), sin
autenticación. Partidas reales de 120 jugadores, 20 por cada banda de ELO, seleccionados
automáticamente por la tarea `listar_jugadores` del DAG desde las listas públicas de
titulados y de jugadores por país, más rankings para la banda `elite`. La lista queda congelada y versionada en
`config/jugadores_seleccionados.yaml`. La API se consulta en serie mediante
sus archivos mensuales.

El integrador vale el **50 % de la nota final** — el doble que los cuatro TPs juntos y
el doble que los dos parciales. Se aprueba con 60 %.

## Cronograma

| Entrega | Fecha | Qué se presenta |
|---|---|---|
| Definición | 12/08/2026 | Grupo, pregunta y fuente de datos |
| 1 · Ingeniería de datos | **02/09/2026** | Pipeline automatizado que produce el dataset |
| 2 · Análisis exploratorio | **23/09/2026** | Exploración, hipótesis y hallazgos |
| 3 · Modelado | **28/10/2026** (5K10: 30/10) | Objetivo predictivo, modelos comparados y métricas |
| 4 · Visualización e integración | **04/11/2026** | Visualizaciones y aplicación funcionando |
| Exposición final | 18/11/2026 | Proyecto completo y demo en vivo |
| Recuperación | 25/11/2026 | Para los grupos que la necesiten |

## Estado del repo

<!-- Actualizar esta sección al cerrar cada entrega. -->

> Las entradas de abajo son el registro de cada entrega y quedan tal como se cerraron. Lo
> vigente es siempre la **última**.

**Al 06/09/2026 (Entrega 1 lista, superada por la del 22/09):** Pipeline de ajedrez online sobre Chess.com,
orquestado con **Airflow en Docker** (`docker-compose.yml` + `Dockerfile`, DAG
`pipeline_ajedrez_chesscom` en `dags/`, cinco tareas 1:1 con los módulos de `src/` y una
tarea final de verificación de los 7 criterios). Validado de punta a punta con la
corrida completa del DAG en verde: 7.215 registros descargados, 7.204 partidas
procesadas, 99,85% de retención y cero nulos finales. Se descartaron 1 duplicado entre
usuarios y 10 partidas con menos de 5 medio-movimientos. La ventana temporal está
congelada (`download.until_month: "2026-08"`) para que una corrida desde cero reproduzca
el dataset. Dos limitaciones quedan documentadas en el README y el notebook para el
modelado de Entrega 3: el rating que informa Chess.com es posterior al cierre de la
partida (fuga de información hacia `resultado`, no sólo un matiz), y la muestra está
concentrada en 8 jugadores de nivel club a élite mundial, no es representativa de
"ajedrez online" en general.

**Al 22/09/2026 (Entrega 2 lista, superada por la del 22/10):** La lista fija de 8 cuentas se reemplazó por la tarea
`listar_jugadores` del DAG (`src/player_selection.py`), que ya no depende de ninguna cuenta
inicial ni del Parquet previo: sortea candidatos de las listas públicas de la PubAPI
(titulados FM/CM/NM para `avanzado`, GM/IM para `experto` y `top_mundial`, jugadores de
ocho países para `principiante` e `intermedio`), los valida y llena 20 por banda. Después
**congela** la lista en `data/raw/seleccion/jugadores_seleccionados.yaml`, así que todas
las corridas descargan los mismos jugadores y el dataset se reproduce. Corrida del
22/09/2026: 100 jugadores (20 por banda), 80.521 registros descargados y 80.145 partidas
finales (99,53% de retención, cero nulos), con las cinco bandas entre 18,2% y 21,8% del
dataset. `notebooks/02_eda_hipotesis.ipynb` contrasta cuatro hipótesis sobre ese Parquet
(H1 V = 0,234 confirmada con matiz; H2 refutada; H3 η² = 0,065 confirmada; H4 η² = 0,007
refutada) y cierra con la tabla de columnas candidatas para la Entrega 3; la guía de
defensa está en `docs/entregas/guia-defensa-entrega-2.md`. Limitaciones vigentes: la fuga
del rating posterior, que el equilibrio entre bandas es una decisión de muestreo y no la
distribución real de Chess.com, y que la banda `avanzado` se arma con titulados de nivel
bajo porque la API no publica listas por rating. El CLI sin Docker usa la misma lista
congelada que el DAG.

**Al 22/10/2026 (Entrega 3 modelada, con un contrato de realismo pendiente; vigente):**
La unidad de modelado es partida × corte, cada 5 plies del 0 al 120. Corrida oficial
`manual__2026-10-22T18:56:28`: 120 cuentas (seis bandas × 20), 101.094 registros →
100.396 partidas (99,31 %), 35 columnas, 1.559.622 cortes y 547.555 de referencia
0/10/20/30/40/60. La extensión conserva las 100 cuentas previas; `top_mundial` es
[2600,3000) y `elite` [3000,4000), esta última desde rankings. El manifiesto vive en
`config/jugadores_seleccionados.yaml`. No hay rapid en las partidas de banda elite.

Los notebooks 01–04 están ejecutados desde kernel limpio, con lecturas de esta corrida.
H1 y H3 globales quedan inconclusas con la regla del EDA; H2 y H4, refutadas. El 03
exploratorio ya mejora antes de mover: 0,880 frente a 0,895. El 04 selecciona por cinco
folds temporales por partida: random forest 0,836 ± 0,025 frente a logística
0,857 ± 0,027 y piso 0,938 ± 0,009. Grilla: max_features=0.3,
min_samples_leaf=20. No se balancea. La regla deja PRE_GAME + LIVE + FORM;
se conservan rating y relojes, entran diez de forma y se excluyen los cuatro grupos
adicionales de posición, estilo y matchup bajo la regla global/corte 0. Después entra
el rating de los rivales (variante D del plan de mejora): 40 columnas finales, sin
pausas ni sesión, con antigüedad, diferencia y promedio de rating.

`PlayerHistoryTransformer` deriva rating y forma dentro del Pipeline con cierres
estrictamente anteriores al inicio. La auditoría encontró 1.345 observaciones para
las que ordenar cierres y aplicar shift no garantizaba esa disponibilidad. Se repitió
la selección con la condición estricta. Test: log-loss 0,795 frente a 0,936 (15,07 %
menos), 5,17 % de mejora antes de mover y 19,58 % al ply 60; recall de Empate 3,81 %.
El período ya fue mirado en el 03 y en versiones anteriores del 04: no es un holdout
nuevo. Duración: MAE 22,889 frente a 28,357 plies, con boosting sin grilla propia.
El artefacto pesa 132,0 MB, no se versiona; `predecir()` reproduce los cortes a 1e-9.

Ratings de rivales (rama `feat/ratings-de-rivales`, 22/10): sólo 185/80.314 partidas
de train tenían ambos ratings previos y la diferencia movía la probabilidad al revés.
El rating de cada rival que traen los JSON entra al historial (33.496/80.314); D mejora
la CV por −0,0053 ± 0,0022 y el corte 0 por −0,0090 ± 0,0029, y la grilla de control
queda sin inversiones (antes 16/44). Arnés: `src/experiment_rival_ratings.py`; plan y
decisión en `docs/entregas/plan-mejora-modelo-app.md`.

La suite local ejecuta 104 tests: 102 pasan y el de dama ganada falla en dos subcasos
(+11,58/+6,29 puntos frente al contrato de +15). Se conserva el fallo y se documenta;
las demás pruebas de realismo (incluida la grilla de rating) y la paridad API/entrenamiento
pasan. Estas pruebas requieren el artefacto y, para población/calibración, los datos
regenerados; sin ellos se saltean. Mapa y respuestas: `docs/entregas/plan-entrega-3.md`.
La app usa este artefacto con historiales, inicios y antigüedad del rating. Falta, para
la Entrega 4, una pieza de visualizaciones de hallazgos además de la app.

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
rompen los proyectos con fuentes flojas. Consigna completa: `docs/entregas/consigna-entrega-3.md`.

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
