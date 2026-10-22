# Criterio de selección de jugadores

## Estado actual

La selección corre **dentro del DAG**, en la primera tarea (`listar_jugadores`, en
`dags/pipeline_ajedrez_dag.py`). La lógica vive en `src/player_selection.py`
(`load_or_create_selection`). No depende de ninguna cuenta inicial ni del Parquet de
una corrida anterior, y **se hace una sola vez**: el resultado queda congelado en
`config/jugadores_seleccionados.yaml`, **versionado en git**, y todas las corridas
siguientes, en cualquier máquina, descargan exactamente los mismos jugadores.

La lista oficial es la de la corrida del 22/10/2026: 100 jugadores, 20 por banda.

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
¿Existe config/jugadores_seleccionados.yaml?
        │
        ├── Sí  →  Se lee y se devuelve la misma lista (sin selección, sin red).
        │
        └── No  →  PRIMERA CORRIDA:
                        │
                        ↓
        Tres pools de candidatos, cada uno con las bandas que alimenta
          · titulados_avanzado  FM, CM, NM                  → avanzado
          · titulados_alto      GM, IM                      → experto, top_mundial
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
            (la banda final la fija la mediana validada, no la estimación)
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
| NM | 2.593 | 2/20 | experto y top_mundial |
| CM | 2.760 | 1/20 | experto y top_mundial |

El 90 % de la cola única eran jugadores por país, y ahí no hay nadie de 1800+. Con las
otras bandas llenas, el selector gastaba una consulta a `/stats` por candidato solo para
descartarlo, y menos del 1 % de esas consultas caía en `avanzado`.

El problema de fondo es que **la PubAPI no publica ninguna lista de jugadores por rating**.
Solo hay listas por país (usuarios comunes, casi todos principiantes) y por título
(maestros, casi todos de 2200 para arriba). Un jugador de 1800–2200 suele ser un amateur
fuerte sin título, así que no figura en ninguna. FM, CM y NM son la fuente abierta más
cercana: aciertan poco (alrededor de 1 de cada 10), pero en un pool propio alcanzan.

> **Una opción que se descartó.** Los títulos femeninos WFM y WCM tienen umbrales más bajos
> (2000–2100 FIDE) y por eso caen mucho más seguido en `avanzado` (12/20 y 9/20 en la
> muestra). Se probaron y se sacaron: llenar una banda con listas exclusivas de un género
> habría hecho que los 20 jugadores de `avanzado` fueran casi todas mujeres y el resto de
> las bandas no, un sesgo metido por la herramienta de muestreo. Hoy los pools usan solo
> títulos abiertos, que puede obtener cualquiera.

Por eso ahora:

- **Cada pool declara las bandas que alimenta** (`player_selection.pools`). Cuando todas
  están llenas, el pool no se sigue recorriendo: una vez completos `principiante` e
  `intermedio`, los ~80.000 jugadores por país ya no se consultan. Si un candidato cae en
  otra banda que sigue abierta, se acepta igual (por ejemplo, un FM de 1900).
- **Los pools se recorren en ronda**, así todas las bandas avanzan en paralelo y ninguna
  espera a que otra termine.
- **Un jugador que figura en dos pools queda solo en el primero**, según el orden del config.
  Nunca se evalúa dos veces.
- **La banda la decide la mediana validada, no la estimación.** Un candidato que se validó
  en otra banda todavía abierta entra ahí igual, en vez de descartarse. La validación es la
  parte cara (recorre los archivos mensuales hasta juntar 1.000 partidas), así que no se
  tira a la basura: en una prueba real eso bajó el tiempo de 547 a 409 segundos para el
  mismo objetivo. Si la banda validada ya está llena, se registra
  `banda_llena_tras_validar:<banda>`.

### Checkpoint: si se corta, retoma

Después de cada validación (y cada 100 candidatos salteados), el avance se guarda en
`data/raw/seleccion/jugadores_seleccionados.parcial.yaml` (`player_selection.snapshot_dir`):
candidatos consumidos por pool,
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
y **esa mediana define la banda del jugador**. El pre-filtro con `/stats` solo sirve para
decidir a quién vale la pena validar: como el rating actual es posterior al cutoff, un
jugador puede terminar en una banda distinta de la estimada, y ahí entra. Si esa banda ya
está llena, se descarta.

Las bandas vienen de `elo.bandas` y son intervalos cerrados a izquierda y abiertos a
derecha, para que un rating justo en el límite no pertenezca a dos bandas.

## Por qué queda congelada

La selección se hace **una vez** y se reusa. Es la misma idea que la ventana temporal
congelada (`download.until_month`):

- **Reproducibilidad:** todas las corridas, en cualquier máquina, descargan los mismos
  jugadores, y como la descarga es idempotente, reusan el bronce ya bajado. Sale el mismo
  dataset.
- **Bronce append-only:** nunca queda un JSON crudo huérfano de una selección vieja. Además,
  si `limpieza_y_parseo` tiene que reconstruir rutas, lo hace desde la lista congelada y no
  con un glob de `data/raw/`.
- **Sin intervención humana:** nadie tiene que escribir la lista a mano. La primera corrida
  la arma sola.

Para **volver a seleccionar** hay que borrar a propósito
`config/jugadores_seleccionados.yaml` (y commitear la lista nueva), y también el
`data/raw/seleccion/jugadores_seleccionados.parcial.yaml` si existiera. Si además se borran los snapshots `country_*.json` / `titled_*.json`, se vuelven
a pedir las listas a la API.

**Por qué se versiona.** Las listas por país y los `/stats` son datos vivos de Chess.com:
otra instalación que corra la selección desde cero otro día obtiene otros jugadores. Hasta
el 22/10/2026 la lista vivía en `data/raw/seleccion/`, ignorada por git, y pasó exactamente
eso: cada integrante tenía su propia lista y su propio dataset (llegaron a convivir cifras
de 80.145 y 76.803 partidas en los documentos). Con la lista en `config/`, el que clona el
repo descarga los mismos 100 jugadores sin seleccionar nada.

**En Linux** el contenedor de Airflow (uid 50000) necesita permiso de escritura en
`config/` para guardar la lista si alguna vez se vuelve a seleccionar:
`setfacl -m u:50000:rwx config`.

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

## Resultado de la selección oficial (22/10/2026)

- 100 jugadores, 20 por banda, sin bandas incompletas.
- 81.094 registros descargados → 80.697 partidas finales.
- `nivel_promedio` (banda del promedio de los dos ratings de cada partida) queda entre
  18,4 % (`avanzado`) y 21,8 % (`intermedio`) del dataset.
- La selección tardó unos 30 minutos; 97 de los 100 jugadores coinciden con una selección
  local anterior hecha con los mismos snapshots y la misma semilla. Los 3 distintos se
  explican porque la banda estimada sale del rating actual (`/stats`), que cambia con el
  tiempo.
