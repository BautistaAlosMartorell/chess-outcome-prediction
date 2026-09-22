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
        Universo de candidatos: listas públicas de la PubAPI
          · jugadores por país  (/pub/country/{iso}/players; AR, ES, MX, US, IN, BR, DE, RU)
          · titulados           (/pub/titled/{GM, IM, WGM, FM})
          (cada lista se guarda cruda en data/raw/seleccion/ → bronce de la selección)
                        ↓
        Unión sin duplicados, orden alfabético y barajado con semilla 42
                        ↓
        Para cada candidato, en ese orden:
          · pre-filtro con /pub/player/{u}/stats → banda estimada
            (rating de la modalidad bullet/blitz/rapid con más partidas)
          · si esa banda ya está llena → se saltea sin validar
          · si no → validación completa contra sus partidas hasta el cutoff
                        ↓
        Se detiene al llenar 20 por banda (o al agotar el pool)
                        ↓
        Escritura atómica de jugadores_seleccionados.yaml → queda CONGELADO
                        ↓
        Fuente del .expand() de descarga_usuario
```

Las **listas por país** aportan jugadores de todos los niveles, sobre todo de las bandas
bajas y medias. Las **listas de titulados** existen porque entre los jugadores por país casi
no aparecen ratings de 2600 o más, y sin ellas `top_mundial` no se llenaría. Mezclar ocho
países reduce el sesgo de tomar uno solo.

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
`data/raw/seleccion/jugadores_seleccionados.yaml`. Si también se borran los snapshots
`country_*.json` / `titled_*.json`, se vuelven a pedir las listas a la API.

**Límite conocido:** las listas por país y los `/stats` son datos vivos de Chess.com. Otra
instalación que corra la selección desde cero otro día puede obtener otros jugadores. Lo que
se garantiza es que, una vez creada, la selección no cambia entre corridas. Para
reproducir exactamente la muestra en otra máquina alcanza con copiar `data/raw/seleccion/`.

## Tolerancia a bandas incompletas

Si el pool se agota antes de que una banda llegue a su objetivo, se registra un *warning*
(`Banda X: solo N/target jugadores seleccionados`) y la corrida sigue con lo que consiguió.
Hay una excepción: si el total queda por debajo de `download.min_users_ok` (por ejemplo, por
una caída de la API durante la selección), **no se congela nada** y la tarea falla. Así la
próxima corrida vuelve a intentar y no queda fija una lista inservible.

## Manifiesto

`jugadores_seleccionados.yaml` es a la vez la lista congelada y el manifiesto auditable.
Incluye:

- la política usada (países, títulos, semilla, cutoff, cupos y bandas);
- el tamaño del pool;
- los seleccionados por banda y la lista plana `usernames`;
- los conteos de candidatos salteados en el pre-filtro, por motivo;
- cada candidato validado, con su banda estimada, su mediana validada y el motivo de rechazo.

## Qué debe validarse después

Después de la primera corrida hay que medir la distribución final por ELO en el Parquet
(`nivel_promedio`) y revisar duplicados y fallos por cuenta. Los umbrales de ingesta
(`download.min_users_ok: 80`, `download.min_total_games`) y de calidad
(`quality.min_final_games`) tienen que acompañar el tamaño real de la muestra.
