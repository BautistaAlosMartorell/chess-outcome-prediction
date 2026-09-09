# Criterio para ampliar la muestra de jugadores

## Estado actual

El selector está implementado, pero **todavía no fue ejecutado**. La lista activa en
`config/config.yaml` sigue formada por los ocho usuarios originales, no se consultó la
PubAPI para elegir candidatos y no existen resultados de selección para presentar como
si fueran evidencia observada.

## Problema que resuelve

La muestra de la Entrega 1 está concentrada en cuentas expertas y de élite. Para el EDA
y el modelado conviene sumar información de las bandas menos representadas sin elegir
usuarios conocidos de manera arbitraria. El universo de candidatos se forma con los
oponentes que ya aparecen en el Parquet procesado: todos tienen una relación trazable
con la muestra original.

El selector busca agregar:

- 8 jugadores intermedios, con ELO mediano en `[1200, 1800)`;
- 8 jugadores avanzados, con ELO mediano en `[1800, 2200)`.

Los intervalos son cerrados a izquierda y abiertos a derecha para que un rating ubicado
exactamente en un límite no pertenezca a dos bandas.

## Procedimiento reproducible

```text
Parquet producido por el pipeline
        ↓
oponentes de los 8 usuarios semilla
        ↓
ELO mediano observado y separación por banda
        ↓
orden aleatorio reproducible (semilla 42)
        ↓
validación serial en la PubAPI hasta completar cada cupo
        ↓
manifiesto de aceptados y rechazados
        ↓
revisión humana
        ↓
actualización explícita con --apply
```

Para cada candidato se exige una cuenta activa y sin cierre por fair play, archivos de
partidas anteriores o iguales a agosto de 2026 y al menos 500 partidas utilizables entre
las 1.000 más recientes revisadas. Se aplican los mismos filtros del pipeline: partidas
*rated*, ajedrez estándar y modalidad bullet, blitz o rapid. La mediana se vuelve a
calcular con esas partidas y debe continuar dentro de la banda inicial.

Los candidatos de cada banda se barajan con la semilla configurada y se validan en ese
orden hasta completar el cupo. Esto evita consultar innecesariamente a todos los
oponentes y sigue siendo reproducible: con el mismo Parquet, configuración y respuestas
históricas de la API, el orden y la selección son iguales.

## Uso futuro

Vista previa, sin cambiar la lista del pipeline:

```bash
python scripts/seleccionar_jugadores.py
```

La ejecución escribe `config/player_selection_manifest.yaml` con la política utilizada,
los candidatos evaluados, los motivos de rechazo y la selección propuesta. Si una banda
no alcanza ocho usuarios válidos, el manifiesto queda marcado como incompleto, el comando
termina con error y no se habilita una aplicación parcial.

Después de revisar el manifiesto, la selección completa puede aplicarse explícitamente:

```bash
python scripts/seleccionar_jugadores.py --apply
```

`--apply` conserva los ocho usuarios semilla, agrega los dieciséis seleccionados sin
duplicados y modifica únicamente `chess_com.usernames`. El selector sigue fuera del DAG:
Airflow consume la lista ya congelada y no redefine la muestra durante cada corrida.

## Qué debe validarse después

Una vez aplicada una selección real hay que ejecutar el pipeline completo, investigar
duplicados y fallos por cuenta, y medir la distribución final por ELO. Recién con esos
resultados corresponde aumentar `download.min_users_ok`, `download.min_total_games` y
`quality.min_final_games`. Mantener por ahora los umbrales de la muestra original evita
presentar como validados números que todavía son sólo una estimación.
