---
name: pipeline-datos
description: Convenciones de este repo para notebooks, ingesta de datos y datasets - reproducibilidad Restart & Run All, descargas idempotentes, procesamiento en streaming de archivos grandes, asserts anti fan-out en cada merge y qué se documenta. Usar al crear o modificar cualquier notebook de notebooks/, al agregar una fuente de datos, al hacer merges de dataframes o al tocar data/. Triggers - notebook, pipeline, dataset, merge, join, pandas, ingesta, descarga.
---

# Pipeline de datos y notebooks

Cómo se escriben los notebooks y se manipulan los datos en este repo. La referencia
viva es `notebooks/01_data_ingestion_verification.ipynb` (y el pipeline reusable en
`src/`): ante la duda, mirá cómo está resuelto ahí.

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

Patrón del repo (`src/download_data.py`, `DataDownloader`):

1. Si el JSON del usuario ya existe en `data/raw/` → saltear, loguear, no volver a bajarlo.
2. `requests.Session` identificada con `User-Agent` + reintentos (`Retry`/backoff) para
   429/5xx, y `raise_for_status()` en cada request.
3. Escribir a un `.part` temporal y recién al terminar hacer `replace` al nombre final.
   Así una descarga cortada no deja un archivo truncado que parezca válido.
4. Solicitudes en serie (Chess.com no limita el acceso serial) + `request_delay` de cortesía.
5. Tolerar fallos aislados: si una cuenta falla (404, sin partidas), se loguea un warning
   y se sigue; al final se exige un mínimo de usuarios y de partidas (`download.min_*`).

Nunca metas un paso de descarga manual ("bajá esto de tal página y ponelo en data/raw").

## Filtrar temprano, no después

Los archivos mensuales de Chess.com son chicos, pero el principio vale igual: la descarga
ya descarta lo que está fuera del alcance (`_is_eligible`: rated, estándar, bullet/blitz/
rapid) y lo posterior a la ventana congelada (`download.until_month`). No bajes datos que
no vas a usar para filtrarlos en memoria más tarde.

## Uniones de dataframes: siempre con assert anti fan-out

Concatenar o mergear tablas con claves repetidas multiplica filas en silencio. En este
repo la única unión es en `parse_all`: `pd.concat` de los JSON de todos los usuarios +
`drop_duplicates(subset="GameUrl")`, porque dos cuentas configuradas pueden reportar la
misma partida si jugaron entre sí. El conteo de duplicados se loguea, y el notebook
cierra asserteando `df["GameUrl"].is_unique` sobre el parquet final.

Si en una entrega futura sumás un merge de verdad:

```python
resultado = izquierda.merge(derecha, on="clave", how="left")
assert len(resultado) == len(izquierda), "Fan-out detectado en el merge con <tabla>"
```

Antes de mergear, verificá la cardinalidad de la tabla derecha (`len(tabla) >
tabla["clave"].nunique()` → deduplicá primero) y no pises columnas buenas: cuando ambas
tablas tienen una columna con el mismo nombre, decidí cuál es la fuente de verdad y traé
del otro lado solo lo que falta.

## Sección de verificación: obligatoria

Todo notebook que produzca un dataset cierra con chequeos, no con un `to_csv`:

- shape final (filas, columnas)
- clave sin duplicados (`GameUrl.is_unique`) y sin nulos
- columna objetivo (`resultado`) sin nulos; `cantidad_jugadas` sin nulos
- rangos con sentido (ELO, `cantidad_jugadas >= MIN_PLIES`, fechas dentro de la ventana)
- los 7 criterios de la cátedra (los replica la tarea `verificar_calidad` del DAG)

## Anomalías: se investigan y se documentan, no se esconden

Si un chequeo da feo, el paso siguiente no es bajar el umbral ni borrar el assert: es
averiguar por qué y dejarlo escrito en el notebook.

Precedente a imitar (Secciones 6 y 8 del notebook): el rating que informa Chess.com es
posterior al cierre de la partida (fuga de información hacia `resultado`), y la muestra
está concentrada en 8 cuentas de nivel alto (mediana de ELO ~2780). Ninguna de las dos se
silenció: se cuantificaron con datos y se dejaron escritas como limitación de la fuente
para el modelado de Entrega 3. Eso es exactamente lo
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
