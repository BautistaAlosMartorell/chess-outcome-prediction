---
name: pipeline-datos
description: Convenciones de este repo para notebooks, ingesta de datos y datasets - reproducibilidad Restart & Run All, descargas idempotentes, procesamiento en streaming de archivos grandes, asserts anti fan-out en cada merge y qué se documenta. Usar al crear o modificar cualquier notebook de notebooks/, al agregar una fuente de datos, al hacer merges de dataframes o al tocar data/. Triggers - notebook, pipeline, dataset, merge, join, pandas, ingesta, descarga.
---

# Pipeline de datos y notebooks

Cómo se escriben los notebooks y se manipulan los datos en este repo. La referencia
viva es `notebooks/01_pipeline_ingesta.ipynb`: ante la duda, mirá cómo está resuelto ahí.

## Principio: el repo guarda código, no datos

`data/raw/` y `data/processed/` están vacíos en git (solo `.gitkeep`) y así se quedan.
Cualquiera clona el repo, corre el notebook y obtiene los mismos archivos. Si un dato no
se puede regenerar corriendo código, el pipeline está incompleto.

Esto no es cosmético: la Entrega 1 pide un **pipeline automatizado**, y una fuente que
haya que bajar a mano no cumple el criterio 4 de la cátedra.

## Estructura de un notebook

```
# Título — Entrega N          (celda markdown: tema, qué hace el notebook, fuente + licencia)

## Sección 1 — <nombre>       (celda markdown: qué hace y POR QUÉ se hace así)
<celdas de código>

## Sección 2 — <nombre>
...

## Sección N — Verificación   (siempre la última)
```

Reglas:

- **Toda sección abre con una celda markdown** que explica la decisión antes del código.
  El notebook se lee de arriba a abajo como un informe, no como un script.
- **Narrativa en markdown en español; comentarios de código en inglés.** Es la convención
  ya establecida en el repo — mantenela.
- Rutas siempre relativas al notebook: `RAW_DIR = Path("../data/raw")`, nunca absolutas.
- Los imports y las rutas base van en la primera celda de código, una sola vez.

## Reproducibilidad: Restart & Run All

El notebook tiene que correr de punta a punta desde un kernel nuevo, sin depender de
ninguna celda ejecutada antes ni de estado manual. Esto se verifica de verdad, no se asume:
antes de commitear, Restart & Run All.

Los outputs se guardan en el `.ipynb` commiteado (ver la skill `git-workflow`).

## Descargas: idempotentes y con manejo de errores

Patrón del repo (`download_file`):

1. Si el archivo ya existe en destino → saltear, informar tamaño, no volver a bajarlo.
2. Descargar con `requests.get(stream=True, timeout=...)` + `raise_for_status()`.
3. Escribir a un `.part` temporal y recién al terminar hacer `rename` al nombre final.
   Así una descarga cortada no deja un archivo truncado que parezca válido.
4. Barra de progreso (`tqdm`) cuando el archivo es grande.

Nunca metas un paso de descarga manual ("bajá esto de tal página y ponelo en data/raw").

## Archivos grandes: streaming, no `read_csv` entero

`player_day_panel.csv` pesa ~515 MB. Si un archivo no entra cómodo en memoria:

```python
for chunk in pd.read_csv(PATH, chunksize=200_000):
    filtered = chunk[chunk["col"].isin(keys)]
    filtered.to_csv(OUT, mode="w" if first else "a", header=first, index=False)
    first = False
```

Filtrar temprano: el paso de streaming es el lugar para descartar filas que no vas a usar,
no después de haber cargado todo.

## Merges: siempre con assert anti fan-out

Un merge contra una tabla con claves duplicadas multiplica filas en silencio y arruina
todo lo que viene después. En este repo, **cada merge va seguido de un chequeo**:

```python
resultado = izquierda.merge(derecha, on="clave", how="left")
assert len(resultado) == len(izquierda), "Fan-out detectado en el merge con <tabla>"
```

Antes de mergear, verificar la cardinalidad de la tabla derecha:

```python
if len(tabla) > tabla["clave"].nunique():
    # una fila por (jugador, temporada), no por jugador -> deduplicar antes
```

**Cuidado con pisar columnas buenas.** Caso real del repo: el panel ya trae su propio
`fbref_player_id` correcto por temporada; traer el del mapping deduplicado lo hubiera
sobrescrito con el de la última temporada. Cuando ambas tablas tienen una columna con el
mismo nombre, decidí explícitamente cuál es la fuente de verdad y traé del otro lado solo
las columnas que faltan.

## Sección de verificación: obligatoria

Todo notebook que produzca un dataset cierra con chequeos, no con un `to_csv`:

- shape final (filas, columnas)
- cantidad de entidades únicas (jugadores)
- **huérfanos**: registros de la tabla origen que no encontraron match en el resultado
- **anti fan-out**: el resultado tiene la misma cantidad de filas que la tabla base

## Anomalías: se investigan y se documentan, no se esconden

Si un chequeo da feo, el paso siguiente no es bajar el umbral ni borrar el assert: es
averiguar por qué y dejarlo escrito en el notebook.

Precedente a imitar (Sección 5 del notebook 1): el 61 % de episodios de lesión quedaban
huérfanos. En vez de ignorarlo, se comparó el `start_date` de cada huérfano contra el
rango de fechas que ese jugador cubre en el panel, mostrando que caen fuera de la
cobertura — una limitación real de la fuente, no un bug del join. Eso es exactamente lo
que el docente pregunta en la entrega.

Escribí la explicación en una celda markdown **antes** del código que la demuestra.

## Dependencias

`requirements.txt` con versiones pinneadas (`==`). Si agregás una librería, agregala ahí
en el mismo commit; si no, el notebook deja de correr en la máquina de los demás.

## Antes de dar por terminado un notebook

- [ ] Restart & Run All desde kernel limpio, sin errores
- [ ] Cada sección tiene su celda markdown explicando el porqué
- [ ] Cada merge tiene su assert anti fan-out
- [ ] Hay sección de verificación al final
- [ ] Las anomalías están investigadas y explicadas por escrito
- [ ] `requirements.txt` cubre todo lo importado
- [ ] Nada de `data/` quedó en el commit
