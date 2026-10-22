# Plan de coherencia de todas las etapas

> **Estado al 22/10/2026: hecho.** Corrida oficial verificada (Fase 0), hoja de datos
> completa (Fase 1), todos los documentos y notebooks revisados (Fase 2) y búsqueda de
> cifras viejas sin restos fuera de los registros con fecha (CHANGELOG, estado de la
> skill de entregas y la explicación de por qué se movió la lista). Cambios respecto del
> plan: el notebook 02_1 se fusionó en el 02 (Parte B) y se borró, y el pipeline ordena
> las filas para que DAG y notebook 01 escriban el mismo archivo. Detalle en
> `docs/CHANGELOG.md`.

Objetivo: que README, guías, skills y notebooks de **todas** las entregas cuenten la
misma historia, con los mismos números, sobre el mismo dataset. Se escribió el 22/10/2026,
antes de la Entrega 3 (28/10).

## El problema

1. **Dos datasets en el repo, y ninguno queda.** La lista "congelada" de jugadores vivía en `data/`, que no
   entra a git, y cada integrante generó la suya. Por eso unos documentos citan la corrida
   del 22/09 (80.521 registros → 80.145 partidas) y otros la del 26/09 (77.229 → 76.803).
   - 80.145: README (criterio 5 y "Corrida validada"), `guia-defensa-entrega-1.md`,
     `skills/entregas-integrador/SKILL.md` (estado al 22/09), `guia-columnas-y-features.md`
     (`Opening` y §9).
   - 76.803: notebooks 01/02/03, `guia-defensa-entrega-2.md`, `machete-entrega-2.md`,
     `explicacion-codigo-pipeline.md`, CHANGELOG.
2. **Dos unidades de análisis.** La Entrega 1 dice "una fila = una partida". El modelado
   usa (partida, corte de plies), y eso no figura en ninguna guía.
3. **La pregunta quedó vieja.** Pregunta sólo por lo que se sabe antes de la partida, y el
   hallazgo principal es que la señal aparece durante la partida.
4. **Partes congeladas.** El notebook 02 y las guías de defensa se dejaron como se
   entregaron, con avisos ("25 columnas", "Notas para la Entrega 3 (sin implementar)").
   Se decidió actualizar todo.

## Decisiones tomadas (22/10/2026)

| Decisión | Valor |
|---|---|
| Dataset oficial | Una corrida **nueva**, con una selección de jugadores nueva. Ninguna de las dos anteriores (80.145 ni 76.803): todas las cifras se rehacen sobre esta |
| Dónde vive la lista | `config/jugadores_seleccionados.yaml`, versionada en git. Snapshots y checkpoint siguen en `data/raw/seleccion/` (`player_selection.snapshot_dir`) |
| Documentos de entregas pasadas | Se actualizan todos; nada queda congelado |
| Cortes | `[0, 10, 20, 30, 40, 60]`. El 0 es la partida antes de la primera jugada |
| Pregunta | Resultado (y duración) **antes y durante** la partida |
| Evaluación con motor (Stockfish) | No entra |

### Pregunta propuesta

> ¿Qué tan bien se puede predecir quién gana una partida de ajedrez online, y cuánto le
> falta para terminar, **antes de que empiece y a medida que avanza**? Antes de empezar se
> conocen el nivel de los jugadores, el ritmo y el color; durante la partida se suman la
> apertura, la posición en el tablero y los relojes.

Título propuesto: *Ajedrez online: predicción del resultado antes y durante la partida*.

Unidad de análisis: **la partida en un momento dado** (partida × corte). El Parquet base
sigue teniendo una partida por fila (tidy, Entrega 1); la tabla de cortes se deriva de él.

## Fase 0 · Corrida oficial (bloquea todo lo demás)

1. Sin `config/jugadores_seleccionados.yaml`, `listar_jugadores` selecciona una lista
   nueva y la escribe ahí. Reusa los snapshots de las listas públicas que ya están en
   `data/raw/seleccion/` (del 22/09).
2. `docker compose build` (la imagen vieja no tiene `python-chess`), `docker compose up -d`,
   disparar `pipeline_ajedrez_chesscom`.
3. Verificar:

   | Qué | Esperado |
   |---|---|
   | Jugadores seleccionados | 100, 20 por banda (si una banda no llena, se documenta) |
   | Columnas del Parquet | 35 |
   | Filas de `partidas_cortes.parquet` | filas de los cortes 10–60 + una por partida en el corte 0 (todas tienen ≥ 5 plies) |
   | `verificar_calidad` | en verde |

4. Commitear `config/jugadores_seleccionados.yaml`: desde ahí todos corren con esa lista.
5. Correr el DAG una segunda vez sin borrar nada tiene que dar exactamente los mismos
   números (prueba de reproducibilidad para la defensa).

## Fase 1 · Hoja de datos vigente

Antes de editar, se completa esta tabla con la corrida oficial. Es la única fuente de los
números: cada documento se corrige contra ella, no contra otro documento.

| Dato | Valor |
|---|---|
| Pregunta y unidad de análisis | (arriba) |
| Fecha de la corrida oficial | 22/10/2026 (`manual__2026-10-22T14:28:37`, DAG completo en verde) |
| Jugadores seleccionados / por banda | 100 / 20 |
| Ventana temporal | hasta `2026-08` |
| Registros descargados → partidas finales (retención) | 81.094 → 80.697 (99,51 %; 397 descartadas) |
| Columnas del Parquet | 35 |
| Filas de la tabla de cortes / partidas con al menos un corte | 435.689 / 80.697 (27 columnas) |
| Filas por corte | 0: 80.697 · 10: 80.099 · 20: 78.456 · 30: 75.383 · 40: 69.788 · 60: 51.266 |
| Reparto de `resultado` (Blancas / Empate / Negras) | 39.540 / 4.905 / 36.252 (49,0 % / 6,1 % / 44,9 %) |
| Partidas de torneo | 6.220 |
| Partidas sin historial de matchup | 1.620 (las primeras 30 de cada uno de los 54 grupos) |
| Cobertura del rating previo (blancas / negras / algún lado / ambos) | 49,8 % / 49,9 % / 99,7 % / 5 partidas |
| Rango de fechas | 2013-01-06 a 2026-09-01 |
| Ritmos (bullet / blitz / rapid) | 21.916 / 45.461 / 13.320 |
| Jugadores en común con la lista local del 22/09 | 97 de 100 |

**Anomalías de esta corrida, a documentar en la Fase 2:**

- 56 partidas tienen `Date` = 2026-09-01 aunque la ventana termina en `2026-08`. Empezaron
  entre las 00:00 y las 02:00 UTC del 1/09: el archivo mensual de Chess.com no corta por
  mes UTC. No es un error del filtro.
- `gasto_reciente_*` es NaN en exactamente las 80.697 filas del corte 0 (todavía no hubo
  jugadas) y en ninguna otra.
- En Linux, el contenedor de Airflow (uid 50000) necesita permiso de escritura sobre
  `config/` para guardar la lista en la primera corrida
  (`setfacl -m u:50000:rwx config`). Documentarlo en el README.

## Fase 2 · Revisión etapa por etapa

En cada archivo se revisan cinco cosas: **pregunta**, **unidad**, **números** (contra la
hoja), **rutas** (`data/raw/seleccion/jugadores_seleccionados.yaml` → `config/`) y
**estado de la fuga del rating** (ahora: resuelta con el rating previo, sólo de un lado).

### Transversal

| Archivo | Qué cambia |
|---|---|
| `README.md` | Título y pregunta; unidad de análisis; criterio 5 y "Corrida validada" (80.145 → oficial); ruta de la lista; sacar el aviso "notebook 02 congelado"; árbol del repo (`config/jugadores_seleccionados.yaml`) |
| `AGENTS.md`, `CLAUDE.md` | Pregunta del proyecto; ruta de la lista en "Correr el pipeline" |
| `skills/entregas-integrador/SKILL.md` | Pregunta y unidad; nueva entrada en "Estado del repo" con la corrida oficial |
| `skills/pipeline-datos/SKILL.md` | Revisar rutas y que la regla de `data/` mencione la excepción de la lista en `config/` |
| `docs/CHANGELOG.md` | Entrada con la lista versionada, el corte 0 y la corrida oficial |
| `docs/entregas/kit-de-arranque.md` | No se toca: es material de la cátedra |

### Definición y Entrega 1 · Ingeniería de datos

| Archivo | Qué cambia |
|---|---|
| `notebooks/01_data_ingestion_verification.ipynb` | Título; §6.A (la fuga ahora tiene solución: rating previo); §9 con la pregunta nueva; mencionar la tabla de cortes como salida del pipeline; Restart & Run All |
| `docs/entregas/guia-defensa-entrega-1.md` | Pregunta; "qué es una fila" (base = partida; modelado = partida × corte); números; "¿sale el mismo dataset?" (ahora sí entre máquinas: lista versionada); las 8 tareas del DAG |
| `docs/entregas/explicacion-codigo-pipeline.md` | "Una fila = una partida" (§5 y §14); `construir_dataset_cortes` con el corte 0; ruta de la lista; `snapshot_dir` |
| `docs/entregas/criterio-seleccion-jugadores.md` | Dónde vive la lista y por qué se versiona; qué queda en `data/` |
| `dags/pipeline_ajedrez_dag.py` | Docstrings: revisar menciones a la ruta de la lista |

### Entrega 2 · Análisis exploratorio

| Archivo | Qué cambia |
|---|---|
| `notebooks/02_eda_hipotesis.ipynb` | Se re-ejecuta con el Parquet de 35 columnas: perfil ("25 columnas"), §9.4 "sin implementar" → qué se implementó y dónde, "Nota para la Entrega 3" del anexo (el campo `tournament` ya está en el pipeline). H1–H4 deberían dar igual sobre las mismas 76.803 partidas: si cambian, se explica |
| `docs/entregas/guia-defensa-entrega-2.md` | Columnas (25 → 35), referencias al notebook 02 re-ejecutado |
| `docs/entregas/machete-entrega-2.md` | `df.shape`, tabla de columnas candidatas |
| `docs/entregas/guia-columnas-y-features.md` | §9 recalculado sobre la corrida oficial; `Opening` (6.796 valores en 80.145 filas); sección nueva con las columnas de la tabla de cortes y el rating previo |

### Entrega 3 · Modelado

| Archivo | Qué cambia |
|---|---|
| `notebooks/03_prediccion_en_vivo.ipynb` | Re-ejecutar con el corte 0. El modelo "pre-partida" (M1) pasa a ser el corte 0 de la misma curva; revisar todas las lecturas escritas a mano |
| `docs/entregas/plan-entrega-3.md` | Actualizar con el corte 0 y la pregunta nueva |
| `notebooks/04_modelado.ipynb` | Nuevo (ver el plan de la Entrega 3) |

## Fase 3 · Verificación

- `grep` de cifras y frases viejas en todo el repo: `80.145`, `80.521`, `80145`,
  `25 columnas`, `(76.803, 25)`, `data/raw/seleccion/jugadores_seleccionados`,
  `una fila = una partida`, `sin implementar`, `congelado`.
- Cada número de la hoja de datos aparece igual en todos los documentos que lo citan.
- `python -m unittest discover -s tests` en verde.
- Notebooks 01, 02 y 03 con Restart & Run All, sin errores y con las salidas guardadas.

## Orden de trabajo y PRs

1. **PR 1 · pipeline** (`feat/corte-cero-y-lista-versionada`): lista en `config/`, corte 0,
   los dos planes y la lista oficial commiteada. Se mergea después de la Fase 0.
   - Cuando se mergee, **cada integrante** tiene que hacer pull y correr con esa lista;
     sus listas locales en `data/raw/seleccion/` dejan de usarse.
2. **PR 2 · coherencia** (rama nueva sobre `main`): Fases 1–3. Notebooks y documentos en
   commits separados por etapa.
   - Para evitar conflictos en `.ipynb`, avisar al grupo que nadie edite los notebooks
     01–03 mientras tanto.
3. **PR 3 · modelado**: `notebooks/04_modelado.ipynb` (plan de la Entrega 3).
