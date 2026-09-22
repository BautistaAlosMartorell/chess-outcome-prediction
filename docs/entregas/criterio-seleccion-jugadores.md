# Criterio de selección de jugadores

## Estado actual

La selección corre **dentro del DAG**, en la primera tarea (`listar_jugadores`, en
`dags/pipeline_ajedrez_dag.py`). La lógica vive en `src/player_selection.py`
(`load_or_create_selection`). No depende de ninguna cuenta inicial ni del Parquet de
una corrida anterior, y **se hace una sola vez**: el resultado queda congelado y todas las
corridas siguientes descargan exactamente los mismos jugadores.

## Problema que resuelve

Las versiones anteriores tenían dos problemas:

1. **Dependían de 8 cuentas elegidas a mano** (streamers y maestros). La muestra quedaba
   concentrada en niveles altos y, cuando se amplió con los oponentes de esas 8, arrastraba
   un sesgo de red: los candidatos eran gente que había jugado contra ellas.
2. **La selección no era estable.** Desde la segunda corrida los candidatos salían del
   Parquet de la corrida anterior, que ya incluía las partidas de los jugadores elegidos.
   El pool crecía en cada corrida (de ~3.600 a ~54.000 candidatos) y la semilla fija
   barajaba un mazo distinto, así que salían otros jugadores. Se perdía la reproducibilidad
   y el bronce descargado antes quedaba huérfano.

## Procedimiento

```text
¿Existe data/raw/seleccion/jugadores_seleccionados.yaml?
        │
        ├── Sí  →  Se lee y se devuelve la misma lista (sin selección, sin red).
        │
        └── No  →  PRIMERA CORRIDA:
                        │
                        ↓
        Tres pools de candidatos, cada uno con las bandas que alimenta
          · titulados_avanzado  WFM, WCM                    → avanzado
          · titulados_alto      GM, IM, WGM, FM             → experto, top_mundial
          · paises              AR, ES, MX, US, IN, BR, DE, RU → principiante, intermedio
          (/pub/titled/{título} y /pub/country/{iso}/players; cada lista se guarda cruda
           en data/raw/seleccion/ → bronce de la selección)
                        ↓
        Cada pool: sin duplicados, orden alfabético y barajado con semilla 42
                        ↓
        Recorrido en ronda (un candidato de cada pool activo por turno):
          · pre-filtro con /pub/player/{u}/stats → banda estimada
            (rating de la modalidad bullet/blitz/rapid con más partidas)
          · si esa banda ya está llena → se saltea sin validar
          · si no → validación completa contra sus partidas hasta el cutoff
          · un pool con todas sus bandas llenas se deja de recorrer
          · checkpoint después de cada validación
                        ↓
        Se detiene al llenar 20 por banda (o al agotar los pools)
                        ↓
        Escritura atómica de jugadores_seleccionados.yaml → queda CONGELADO
                        ↓
        Fuente del .expand() de descarga_usuario
```

### Por qué tres pools y no uno

La primera versión mezclaba todas las listas en una sola cola. Se cortó a mano después de
una hora con 94/100: faltaban 6 `avanzado` (1800–2200). Con muestras de `/stats` del
22/09/2026 se midió qué niveles aporta cada lista:

| Lista | Tamaño | Muestra en `avanzado` | Resto de la muestra |
|---|---|---|---|
| Países (AR, US) | ~10.000 c/u, ~80.000 en total | **0/80** | casi todo principiante |
| FM | 4.859 | 3/20 | experto y top_mundial |
| CM / NM | ~2.600 c/u | 1/20 y 2/20 | experto y top_mundial |
| **WFM** | 966 | **12/20** | experto e intermedio |
| **WCM** | 658 | **9/20** | intermedio, experto |

El 90 % de la cola única eran jugadores por país, sin nadie de 1800+, y los títulos de ese
nivel (WFM y WCM) no estaban. Con las otras bandas llenas, el selector gastaba una consulta
a `/stats` por candidato solo para descartarlo, y menos del 1 % de esas consultas caía en
`avanzado`.

Por eso ahora:

- **Se agregaron WFM y WCM**, que caen mayormente en `avanzado`. CM y NM se descartaron
  porque en la muestra aportaron casi solo 2200+.
- **Cada pool declara las bandas que alimenta** (`player_selection.pools`). Cuando todas
  están llenas, el pool no se sigue recorriendo: una vez completos `principiante` e
  `intermedio`, los ~80.000 jugadores por país ya no se consultan. Si un candidato cae en
  otra banda que sigue abierta, se acepta igual (por ejemplo, un FM de 1900).
- **Los pools se recorren en ronda**, así todas las bandas avanzan en paralelo y ninguna
  espera a que otra termine.
- **Un jugador que figura en dos pools queda solo en el primero**, según el orden del config.
  Nunca se evalúa dos veces.

En una prueba real con la versión final, `avanzado` juntó 6 jugadores con 12 candidatos
(antes eran varios cientos por jugador). Ahora el costo lo domina la validación de cada
aceptado, que recorre sus archivos mensuales hasta juntar 1.000 partidas.

### Checkpoint: si se corta, retoma

Después de cada validación (y cada 100 candidatos salteados), el avance se guarda en
`data/raw/seleccion/jugadores_seleccionados.parcial.yaml`: candidatos consumidos por pool,
seleccionados, evaluados y conteos de salteados. Si la tarea se corta (reintento de Airflow,
worker caído, corte manual), la próxima corrida sigue desde ahí. Como el orden de cada pool
es determinístico (snapshots + semilla), retomar da el mismo resultado que no haberse
cortado. El checkpoint solo se usa si fue hecho con la **misma política**; si cambió el
config, se ignora y se empieza de cero. Cuando la selección se congela, el checkpoint se
borra.

### Validación de cada candidato

Se exige:

- cuenta activa y sin cierre por fair play;
- archivos mensuales anteriores o iguales al `cutoff` (agosto de 2026);
- al menos `player_selection.min_eligible_games` partidas utilizables (hoy **15**) entre las
  `max_games_per_candidate` (1.000) más recientes revisadas.

Se aplican los mismos filtros de alcance que usa el pipeline: partidas *rated*, ajedrez
estándar y modalidad bullet, blitz o rapid. Con esas partidas se calcula la mediana de ELO,
y esa mediana tiene que caer dentro de la banda que estimó el pre-filtro. Así, un jugador
cuyo rating actual cambió mucho respecto de su historial hasta el cutoff no entra en la
banda equivocada.

Las bandas vienen de `elo.bandas` y son intervalos cerrados a izquierda y abiertos a
derecha, para que un rating justo en el límite no pertenezca a dos bandas.

## Por qué queda congelada

La selección se hace **una vez** y se reusa. Es la misma idea que la ventana temporal
congelada (`download.until_month`):

- **Reproducibilidad:** todas las corridas en la misma instalación descargan los mismos
  jugadores, y como la descarga es idempotente, reusan el bronce ya bajado. Sale el mismo
  dataset.
- **Bronce append-only:** nunca queda un JSON crudo huérfano de una selección vieja. Además,
  si `limpieza_y_parseo` tiene que reconstruir rutas, lo hace desde la lista congelada y no
  con un glob de `data/raw/`.
- **Sin intervención humana:** nadie tiene que escribir la lista a mano. La primera corrida
  la arma sola.

Para **volver a seleccionar** hay que borrar a propósito
`data/raw/seleccion/jugadores_seleccionados.yaml`, y también el `.parcial.yaml` si
existiera. Si además se borran los snapshots `country_*.json` / `titled_*.json`, se vuelven
a pedir las listas a la API.

**Límite conocido:** las listas por país y los `/stats` son datos vivos de Chess.com. Otra
instalación que corra la selección desde cero otro día puede obtener otros jugadores. Lo que
se garantiza es que, una vez creada, la selección no cambia entre corridas. Para
reproducir exactamente la muestra en otra máquina alcanza con copiar `data/raw/seleccion/`.

## Tolerancia a bandas incompletas

Si el pool se agota antes de que una banda llegue a su objetivo, se registra un *warning*
(`Banda X: solo N/target jugadores seleccionados`) y la corrida sigue con lo que consiguió.
Hay una excepción: si el total queda por debajo de `download.min_users_ok` (por ejemplo, por
una caída de la API durante la selección), **no se congela nada** y la tarea falla. El
checkpoint queda, así que la próxima corrida retoma desde ahí y no queda fija una lista
inservible.

## Manifiesto

`jugadores_seleccionados.yaml` es a la vez la lista congelada y el manifiesto auditable.
Incluye:

- la política usada (pools con sus listas y bandas, semilla, cutoff, cupos y bandas de ELO);
- el tamaño de cada pool y cuántos candidatos se consumieron de cada uno;
- los seleccionados por banda y la lista plana `usernames`;
- los conteos de candidatos salteados en el pre-filtro, por motivo;
- cada candidato validado, con su banda estimada, su mediana validada y el motivo de rechazo.

## Qué debe validarse después

Después de la primera corrida hay que medir la distribución final por ELO en el Parquet
(`nivel_promedio`) y revisar duplicados y fallos por cuenta. Los umbrales de ingesta
(`download.min_users_ok: 80`, `download.min_total_games`) y de calidad
(`quality.min_final_games`) tienen que acompañar el tamaño real de la muestra.
