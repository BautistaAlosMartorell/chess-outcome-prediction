# Criterio para ampliar la muestra de jugadores

## Estado actual

El selector está implementado y **corre dentro del DAG** como su primera tarea
(`listar_jugadores`, en `dags/pipeline_ajedrez_dag.py`). Ya no es un script ocasional que
se ejecuta a mano ni modifica `chess_com.usernames`: en cada corrida arma dinámicamente la
lista de cuentas a descargar, la usa como fuente del `.expand()` y guarda un manifiesto
auditable. La lógica vive en `src/player_selection.py`.

## Problema que resuelve

La muestra de la Entrega 1 está concentrada en cuentas expertas y de élite. Para el EDA y
el modelado conviene sumar información de las bandas menos representadas sin elegir usuarios
conocidos de manera arbitraria. El universo de candidatos se forma con los oponentes que ya
aparecen en el Parquet procesado: todos tienen una relación trazable con la muestra
original.

El selector apunta a cubrir **cinco bandas de ELO** con un objetivo de **20 jugadores por
banda** (~100 en total), configurable en `player_selection.target_per_band`:

- `principiante`, `intermedio`, `avanzado`, `experto` y `top_mundial`.

Los intervalos de cada banda se definen en `elo.bandas` y son cerrados a izquierda y
abiertos a derecha para que un rating ubicado exactamente en un límite no pertenezca a dos
bandas.

## Procedimiento reproducible

`listar_jugadores` funciona en dos modos según exista o no un Parquet procesado de una
corrida anterior:

```text
¿Existe data/processed/partidas_ajedrez_clean.parquet?
        │
        ├── No  →  BOOTSTRAP: descubre oponentes de los seeds consultando la PubAPI
        │          (discover_opponents_from_api) y sigue el flujo normal de selección.
        │
        └── Sí  →  Lee el Parquet y extrae los oponentes ya observados (rápido, sin red).
                        │
                        ↓
        ELO mediano observado y separación por banda
                        ↓
        orden aleatorio reproducible (semilla 42)
                        ↓
        validación serial en la PubAPI hasta completar cada cupo
                        ↓
        lista combinada (seeds + seleccionados, sin duplicados)
                        ↓
        manifiesto de aceptados y rechazados
                        ↓
        fuente del .expand() de descarga_usuario
```

Para cada candidato se exige una cuenta activa y sin cierre por fair play, archivos de
partidas anteriores o iguales al `cutoff` (agosto de 2026) y al menos
`player_selection.min_eligible_games` partidas utilizables (hoy **15**) entre las
`max_games_per_candidate` (1.000) más recientes revisadas. Se aplican los mismos filtros
del pipeline: partidas *rated*, ajedrez estándar y modalidad bullet, blitz o rapid. La
mediana se vuelve a calcular con esas partidas y debe continuar dentro de la banda inicial.

Los candidatos de cada banda se barajan con la semilla configurada (`random_state: 42`) y
se validan en ese orden hasta completar el cupo. Esto evita consultar innecesariamente a
todos los oponentes y sigue siendo reproducible: con el mismo Parquet, configuración y
respuestas históricas de la API, el orden y la selección son iguales.

## Tolerancia a bandas incompletas

A diferencia del script original (que abortaba si una banda no llegaba a su cupo), el DAG
usa una **selección tolerante**: si una banda no alcanza su objetivo, se registra un
*warning* en los logs (`Banda X: solo N/target jugadores seleccionados`) y la corrida sigue
con lo que consiguió. Una selección parcial sigue siendo útil para ampliar la muestra, y los
seeds siempre están incluidos, así que nunca queda vacía.

## Manifiesto

Cada corrida escribe `data/processed/player_selection_manifest.yaml`
(`player_selection.manifest_path`) con la política utilizada, los candidatos evaluados, los
motivos de rechazo y la selección final por banda. Es la evidencia auditable de cómo se
armó la muestra en esa corrida.

## Ejecución manual (opcional)

El módulo sigue pudiendo usarse desde la línea de comandos como vista previa, sin depender
de una corrida del DAG:

```bash
python scripts/seleccionar_jugadores.py
```

## Qué debe validarse después

Con la selección corriendo dentro del DAG conviene, tras cada ampliación real de la muestra,
investigar duplicados y fallos por cuenta y medir la distribución final por ELO. Los
umbrales de ingesta (`download.min_users_ok`, `download.min_total_games`) y de calidad
(`quality.min_final_games`) deben acompañar el tamaño real esperado de la muestra ampliada,
no quedar fijos en los números de la muestra original.
