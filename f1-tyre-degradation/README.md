# F1 Tyre Degradation — "The Cliff"

Idea candidata para el Proyecto Integrador (Ciencia de Datos, UTN FRM 2026).
Predecir cuándo un neumático de F1 entra en degradación crítica y cómo evoluciona
el tiempo de vuelta, usando datos oficiales vía **FastF1**.

> Esta carpeta convive con otras ideas del repo. Ver `../ideas_proyecto.md` para el
> resto de candidatos. Se limpiará cuando se elija la idea definitiva.

## Contenido
- [`PARTE_0_DEFINICION.md`](./PARTE_0_DEFINICION.md) — la Parte 0 completa (pregunta, hipótesis, criterios, plan).
- [`build_dataset.py`](./build_dataset.py) — pipeline de ingesta automatizado (FastF1 → dataset tidy).
- `requirements.txt` — dependencias.

## Cómo generar el dataset
```bash
pip install -r requirements.txt

# Prueba rápida (3 carreras):
python build_dataset.py --seasons 2024 --max-races 3

# Dataset completo (3 temporadas, >60k vueltas):
python build_dataset.py --seasons 2023 2024 2025
```
Genera `data/f1_laps_raw.csv` y `data/f1_laps_clean.csv` (ambos gitignoreados; se regeneran).

## ¿Por qué la pregunta no usa el combustible?

La pregunta inicial era:

> *"¿En qué momento exacto entra un neumático en fase de degradación crítica ('the cliff') y cómo
> afecta a los tiempos de vuelta según el compuesto, la temperatura de pista y **el consumo de
> combustible** en Fórmula 1?"*

El problema está en el combustible. El **tiempo de vuelta bruto está afectado por dos cosas a la vez**,
que van en direcciones opuestas:

1. **El neumático se gasta** → el auto va más lento (esto es lo que queremos medir).
2. **El combustible se quema** → el auto se aliviana y va más rápido (esto nos "ensucia" la medición).

Para aislar la degradación pura, la pregunta original obligaba a **descontar el efecto del combustible**,
es decir, a saber cuántos kg de nafta había en cada vuelta. **Ese dato no existe públicamente**: la F1 no
lo publica y no está en FastF1. La única forma de obtenerlo sería **estimarlo/inventarlo**, y la cátedra
no permite fabricar ni estimar datos.

### Qué hicimos en su lugar

Reformulamos la pregunta a:

> *"¿Cómo evoluciona el tiempo de vuelta de un piloto a medida que aumenta la vida del neumático dentro
> de un stint, y en qué vuelta ese deterioro entra en fase crítica ('the cliff'), según el compuesto y
> la temperatura de pista?"*

- **No se inventa ningún dato.** Se quita el combustible como variable a estimar.
- **El efecto del combustible no se ignora:** queda representado por `LapNumber` (la vuelta de carrera,
  dato real medido). Como la nafta se quema de forma pareja vuelta a vuelta, `LapNumber` captura ese
  efecto sin que calculemos una sola cantidad física. El modelo lo usa como una variable más.
- **El "cliff" sí se puede detectar igual:** es un salto brusco en el tiempo de vuelta, distinguible del
  descenso suave y constante que produce el combustible.

### Diferencia conceptual entre ambas preguntas

| | Pregunta original | Pregunta actual |
|---|---|---|
| **Objetivo** | Detectar el cliff y su efecto en el lap time | **El mismo** |
| **Variables** | Compuesto, temperatura, **+ combustible** | Compuesto, temperatura, vida del neumático, `LapNumber` |
| **Qué mide del lap time** | Degradación **pura**, aislando el combustible | Degradación **tal como se observa** en pista |
| **¿Inventa datos?** | **Sí** (estimar combustible) | **No** |

El objetivo es prácticamente idéntico; lo único que cambia es que dejamos de depender del único número
que no se puede conseguir.

> **Nota sobre el "cliff":** definir su etiqueta a partir de los tiempos de vuelta reales es *derivar un
> target* (práctica estándar en machine learning), no inventar datos. No es lo mismo que fabricar una
> cantidad física como el combustible.

## Estado
✅ Pipeline probado con la temporada **2024 completa** (24 carreras): 26.604 vueltas → **22.999 limpias**.
El pipeline genera dos archivos: `f1_laps_raw.csv` (35 columnas, todo lo que baja FastF1) y
`f1_laps_clean.csv` (**14 columnas**, dataset lean listo para modelar: features + target, sin datos
estimados ni columnas que produzcan *leakage*). Diccionario visual en `diccionario_columnas.png`.
