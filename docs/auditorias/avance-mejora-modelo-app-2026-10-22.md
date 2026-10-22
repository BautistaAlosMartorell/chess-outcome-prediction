# Avance de la mejora del modelo · traspaso del 22/10/2026

Continuación del [plan](../entregas/plan-mejora-modelo-app.md). Leer este avance antes
de repetir tareas. **El artefacto de producción y la app no se modificaron.**

## Qué quedó hecho

- Copia verificada del modelo vigente en `models/baselines/25051ff7bd92.joblib` y
  manifiesto de hashes del artefacto, Parquets y configuración en el mismo directorio.
  Todo queda ignorado por git, como corresponde a modelos/datos regenerables.
- Protocolo explícito en `config/evaluacion_mejora_app.yaml`: CV temporal por partida,
  purga de partidas sin terminar antes de validar, métricas, estratos y condiciones de
  promoción. Se fijaron tolerancias antes de entrenar las referencias de este avance.
- Lista de 22 partidas ya inspeccionadas en `config/partidas_auditadas_mejora_app.yaml`.
  Son casos de regresión, no test ciego. El período posterior al corte original ya fue
  observado y sigue siendo exploratorio; **no se asignó todavía un holdout nuevo**.
- Piloto de cobertura sin red: `src/audit_history_coverage.py`. Lee ambos colores de
  los JSON existentes, comprueba duplicados contradictorios y consulta sólo cierres
  estrictamente anteriores al inicio, del mismo ritmo. Conserva antigüedad y procedencia.
- Referencias de resultado inicial en `src/experiment_rating_reference.py`: logística
  multinomial de tres resultados con diferencia/nivel de rating, banderas de disponibilidad
  y procedencia, antigüedad, ritmo y control. Sin forma incidental ni motor de ajedrez.
  Imputación, escalado y ajuste pertenecen al Pipeline; los folds son temporales purgados.
- Ocho pruebas nuevas verifican tiempos estrictos, futuro, ritmo, faltantes, duplicados
  contradictorios, procedencia, antigüedad y purga. Pasaron las ocho.

## Resultado del piloto de cobertura

Se leyeron 101.094 registros crudos. Cero fuera del alcance; se deduplicaron 546
observaciones de cuenta/partida que aparecían en más de un archivo. Quedaron 201.642
observaciones de 55.270 cuentas. No se detectaron copias contradictorias.

| Fuente | Train: ambos ratings | Evaluación observada: ambos ratings |
|---|---:|---:|
| Sólo archivos propios | 185 / 80.314 | 85 / 20.080 |
| Incluyendo apariciones incidentales | 33.496 / 80.314 | 9.740 / 20.080 |
| Ambos observados dentro de 1 día | 18.895 / 80.314 | 5.994 / 20.080 |
| Ambos observados dentro de 7 días | 21.123 / 80.314 | 7.096 / 20.080 |
| Ambos observados dentro de 30 días | 24.232 / 80.314 | 8.156 / 20.080 |

Los conteos de archivos propios reproducen los de la auditoría previa. Se excluyeron
del entrenamiento/evaluación las mismas dos partidas que cruzan el corte temporal.

**Interpretación:** hay una mejora grande de cobertura sin descargar datos, pero un
rating incidental es el último **observado por nuestra muestra**, no necesariamente
el rating de la última partida de esa cuenta. No renombrarlo como rating previo exacto.

La antigüedad máxima por pareja entre los pares nuevos tiene mediana de 0,009 días
en train y 0,003 días en evaluación. Hay una cola muy larga: percentil 95 de 692 y
187 días, respectivamente. Por eso se ensayó también una variante que descarta ratings
incidentales de más de 30 días. Los archivos propios se mantienen en esa variante.
No se calcularon rachas, forma de diez partidas ni sesiones de los rivales incidentales.

Archivos generados, ignorados por git:

- `data/processed/auditoria_cobertura/informe.json`: conteos por fuente/ritmo/partición,
  frescura y brecha de rating.
- `data/processed/auditoria_cobertura/cobertura.csv`: la misma tabla en formato tabular.
- `data/processed/auditoria_cobertura/ratings_previos_observados.parquet`: una fila por
  juego, con ratings observados, antigüedad y banderas de archivo propio por color.

## Primera comparación de referencias

**Sólo posición inicial**, no un candidato listo para servir posiciones en vivo.
Cinco folds temporales purgados sobre 80.314 partidas. C=1, semilla 42; sin grilla.
Los tres candidatos usan el mismo conjunto objetivo y las mismas particiones.

| Referencia | Log-loss CV, media ± desvío muestral | Período posterior ya observado |
|---|---:|---:|
| Sólo ratings de archivos propios | 0,892408 ± 0,006516 | 0,882024 |
| Más ratings incidentales y antigüedad/procedencia | 0,868265 ± 0,008632 | 0,856412 |
| Incidentales limitados a 30 días | 0,874132 ± 0,010048 | 0,860413 |

La diferencia pareada de CV de incidentales sin límite menos archivos propios es
**−0,024143 ± 0,005620**, con mejora en los cinco folds. La variante de 30 días también
mejora frente a la referencia propia; su selección definitiva requiere más validación.
La variante de 30 días se agregó por la cola de antigüedad observada, no como búsqueda
de hiperparámetros sobre un holdout nuevo. Ninguno de estos resultados es una garantía
de probabilidades correctas para cada partida ni evidencia de calibración en brechas extremas.

Como referencia descriptiva, el random forest vigente da 0,866232 en la posición
inicial del mismo período observado. La logística enriquecida obtiene 0,856412; esta
comparación **no justifica reemplazar el modelo**: falta CV del bosque enriquecido,
validación de posiciones en curso y evaluación final nueva. No comparar el 0,868 de
esta CV inicial con el 0,836 global del notebook 04: usan unidades/cortes distintos.

Las tres referencias pasaron una grilla neutral de seis niveles medios, cinco brechas
de −400 a +400 y tres ritmos, con ambas entradas conocidas y antigüedad fija: P(victoria
blancas) no disminuye al mejorar su rating relativo. Pasar ese control es necesario,
pero no prueba magnitud/calibración correcta ni resuelve sensibilidad al material.

Artefactos de diagnóstico, todos bajo `models/experiments/rating_reference/`:

- `metrics.json`: folds, métricas, probabilidades en grilla y hashes de entradas.
- `fold_assignments.parquet`: juego/fold/rol para reproducir la comparación.
- `*_reference.joblib`: pipelines de referencia. **No tienen el contrato de la app**,
  no sirven el tablero en vivo y no deben copiarse a `modelo_en_vivo.joblib`.
- `input_manifest.json`: hashes de 120 JSON originales, configuración, Parquet base
  y código del piloto/experimento. Si se modifica el código o se regenera un artefacto,
  actualizar este manifiesto; los hashes de entradas principales también salen en metrics.

## Verificaciones y límites pendientes

- Suite completa: 94 pruebas. Sigue fallando únicamente la prueba conocida de dama
  ganada, en sus dos subcasos (+9,02/+10,34 frente al contrato >15). Los ocho tests
  nuevos pasan. No se cambió el umbral ni el modelo que causa ese fallo.
- El modelo de producción conserva su hash y su copia de seguridad. No se descargaron
  datos, ni se cambió la selección congelada, el DAG o los notebooks.
- El piloto mide cobertura por ritmo y brecha, pero todavía falta completar las tablas
  por banda/cobertura/frescura y estudiar el comportamiento en cuentas nuevas.
- La referencia no modela interacciones entre brecha y ritmo/nivel; antes de ampliarla,
  evaluar si hacen falta por CV y calibración de subgrupos. Los ratings extremos o
  incidentales antiguos pueden seguir siendo problemáticos.
- Los umbrales de promoción son condiciones mínimas, no autorización automática.
  No hay un holdout nuevo ni un modelo completo candidato para producción todavía.

## Próximas acciones para Claude u otra sesión

1. Revisar git y estos archivos. No repetir las lecturas de red de la primera auditoría
   salvo que se necesiten fuentes nuevas. Los snapshots de `/tmp` pueden desaparecer.
2. Completar cobertura/calibración por banda, ritmo, brecha y frescura. Inspeccionar
   dónde falla la referencia, con suficiente n y procedencia explícita. Evitar seleccionar
   correcciones por los resultados del período ya observado.
3. Definir y reservar la evaluación temporal nueva antes de seleccionar el modelo final.
   Si todavía no hay datos adecuados, dejarlo pendiente explícitamente; no promover.
4. Decidir cuánto contexto adicional hace falta descargar: el piloto sin red ya recupera
   bastantes pares. Si se enriquece, hacerlo con un salto de rivales, presupuesto acotado,
   caché y ventana anterior al juego objetivo. No inferir forma completa de apariciones.
5. Integrar ratings/proxies, antigüedad y disponibilidad en un transformador compartido,
   manteniendo separación entre observación propia, incidental y contexto de la app.
   Probar que entrenamiento y API obtienen las mismas features. No reemplazar sin más
   el `PlayerHistoryTransformer`: su causalidad y sus ventanas de forma deben conservarse.
6. Reentrenar primero el bosque actual con contexto enriquecido, luego añadir diferencia
   y promedio de ELO para aislar qué mejora. Comparar con la referencia en los mismos
   folds y posiciones. Evaluar pausas/sesión por ablación reentrenada, no imputación.
7. Validar el modelo completo, contrato de material, calibración y posiciones en vivo;
   sólo después pensar en sustituir el artefacto de la app y recargar el servidor correcto.

## Reproducción

```bash
.venv/bin/python -m src.audit_history_coverage
.venv/bin/python -m src.experiment_rating_reference
.venv/bin/python -m unittest discover -s tests
```

Los dos primeros comandos no consultan la red. Requieren la corrida local y los JSON
de las cuentas congeladas. El segundo genera únicamente referencias de diagnóstico.
Los cambios siguen sin commit; no se hizo push, PR ni merge.
