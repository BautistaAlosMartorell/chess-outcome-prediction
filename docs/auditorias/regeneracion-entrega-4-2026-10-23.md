# Regeneración de reportes y gráficos · 23/10/2026

Seguimiento del pendiente de la fase 1 del
[plan de Entrega 4](../entregas/plan-entrega-4.md): ejecutar el DAG, los notebooks
02 y 04 y construir los JSON de la app con sus reportes. Rama local:
`chore/regenerar-reportes-entrega-4`.

## Pipeline y reproducibilidad

- DAG `pipeline_ajedrez_chesscom`, corrida
  `manual__regeneracion_entrega4_20261023`, finalizada con éxito.
- Inicio: 23/10, 09:20 de Argentina; exportación de cortes: 09:41.
  La construcción de cortes requirió 18 min 53 s; la estimación anterior de cinco
  minutos no describe esta ejecución en esta máquina.
- Se reutilizaron los 120 JSON existentes y la selección congelada. Pasaron los
  siete criterios de calidad: 101.094 registros crudos → 100.396 partidas,
  35 columnas y 1.559.622 filas de cortes.
- La selección de jugadores y el Parquet de cortes conservaron sus hashes SHA-256.
- El Parquet base cambió de hash, por lo que se investigó antes de atribuirlo a un
  cambio de datos. Se repitieron limpieza e ingeniería de características directamente,
  sin los archivos intermedios de Airflow. Esa ejecución reprodujo el hash anterior
  `975e416a43851ab7fbf9e48c74a29fac06a9d2428de8dff5881d9c24501e67b5`.
  Al leer ambos Parquet se comprobaron todos sus valores, columnas y tipos: coinciden.
  Los esquemas Arrow también coinciden. La única diferencia en los metadatos de
  pandas es `EndTime.numpy_type`: `datetime64[s]` en la escritura directa y
  `datetime64[ms]` después de releer el intermedio de Airflow. No cambian los
  instantes ni las partidas.
- Airflow estaba apagado al iniciar y se detuvo después del DAG para liberar memoria
  durante el entrenamiento. Sus volúmenes y registros se conservan.

## Notebooks y construcción

- Notebook 02 ejecutado con kernel limpio en aproximadamente 40 segundos, incluidos
  sus anexos y la nueva celda final de exportación. `reporte_eda.json` conserva
  exactamente el hash de su versión local anterior.
- Notebook 04 ejecutado con kernel limpio en 54,5 minutos. Sus 26 celdas de código
  terminaron en orden y sin errores; en el 02 fueron 46. El código de ambos notebooks
  coincide con el versionado: se actualizaron las salidas de ejecución.
- El reporte del 04 reproduce todas las decisiones, columnas y métricas del reporte
  anterior con tolerancia absoluta `1e-9`, excluyendo los tiempos de ajuste:
  random forest de 40 columnas, log-loss 0,795304 frente a 0,936383 del piso
  (15,07 % de mejora); duración, MAE 22,888871 frente a 28,357381 plies.
- `python -m src.build_app` completado en 112 segundos. El test reconstruido coincide
  con el reporte del 04, globalmente y por corte, dentro de la tolerancia `1e-6`.
  Se generaron `web/public/app/resumen.json` y las specs `datos.json`,
  `hallazgos.json`, `modelo.json` y `explora.json` en `web/public/app/graficos/`.
- Explorá contiene 2.000 partidas de test y 31.667 filas (partida, corte). Su spec
  pesa 3.759.746 bytes; todos los archivos quedan por debajo de 5 MB.

## Verificaciones

- Antes y después de reentrenar: 105 tests ejecutados, 104 pasan y uno falla en dos subcasos.
  Es el contrato conocido de ganar una dama: +11,58/+6,29 puntos frente a +15
  exigidos. No se cambió su umbral.
- Web: `npm run typecheck` y `npm run build` pasan. Se apartó la caché local de
  `.next`, que referenciaba páginas de otra versión del repo.
- Las cuatro specs pasan la validación del esquema de Altair. Se verificaron los
  controles de corte, ritmo, nivel y selección de partida; las claves de la muestra
  no se duplican y todas sus filas apuntan a una partida existente. Las probabilidades
  están entre 0 y 1 y suman 1 dentro del redondeo a tres decimales.
- El resumen de portada y las tablas de hipótesis coinciden con los reportes de los
  notebooks. `git diff --check` pasa.

## Alcance restante

La integración de los gráficos en las páginas, las pruebas de navegación y la
publicación siguen en las fases 3–6 del plan de Entrega 4. Esta regeneración no
equivale a publicar la app ni resuelve el contrato de material del modelo.
Las pruebas automatizadas específicas de `tests/test_build_app.py` también quedan
para esa etapa; la validación de los JSON de esta corrida se ejecutó por separado.

El notebook principal de la Entrega 3 es el **04**; el **03** conserva la exploración
previa y no es necesario para regenerar estos reportes y gráficos. Todo el trabajo
queda local, sin commit, push ni PR; datos y modelos siguen ignorados por git.
