# Predicción del tipo de lesión en la Premier League según congestión de partidos

Proyecto Integrador — Ciencia de Datos (UTN FRM).

## Objetivo

Predecir el **tipo de lesión** de jugadores de la Premier League a partir de la **congestión de partidos** (minutos jugados en los últimos 7 días). Esta primera entrega cubre el pipeline de ingeniería de datos: descarga, categorización de lesiones, filtrado y unión de las fuentes en un dataset final a nivel jugador-día.

## Fuente de datos

**English Premier League Fixture Congestion and Injury Dataset (2012–2025)**, v1.0.0
Autor: Gustavo Pedro Ricou
Repositorio: [Zenodo](https://zenodo.org/records/17835138)
DOI: [10.5281/zenodo.17835138](https://doi.org/10.5281/zenodo.17835138)
Licencia: CC-BY 4.0

Archivos utilizados:
- `tm_injuries_clean.csv` — registros de lesiones por jugador (Transfermarkt), con descripción libre.
- `player_mapping_tm.csv` — tabla de traducción entre `tm_player_id` (Transfermarkt) y `fbref_player_id` (FBref).
- `player_day_panel.csv` — panel día a día por jugador, con minutos jugados y congestión de partidos (~515 MB).

## Estructura de carpetas

```
CienciaDeDatos/
├── data/
│   ├── raw/            # archivos descargados de Zenodo + lesiones categorizadas
│   └── processed/       # panel filtrado y dataset final
├── notebooks/
│   └── 01_pipeline_ingesta.ipynb   # pipeline de ingeniería de datos (Entrega 1)
├── skills/              # convenciones del repo para agentes de código
├── AGENTS.md            # punto de entrada para Codex y OpenCode
├── CLAUDE.md            # punto de entrada para Claude Code
├── requirements.txt
└── README.md
```

## Convenciones de trabajo

Las convenciones del repo (ramas y commits, cómo se escriben los notebooks, qué pide
cada entrega) están en [`skills/`](skills/), en formato Agent Skills, para que las lean
tanto las personas como los agentes de código. Ver [`skills/README.md`](skills/README.md).

**Regla base: no se commitea a `main` ni se suben archivos de `data/`.**

## Cómo correr el pipeline

### Requisitos

- Python 3.11+
- Instalar dependencias:

```
pip install -r requirements.txt
```

### Ejecución

1. Abrir `notebooks/01_pipeline_ingesta.ipynb` en Jupyter Notebook/Lab.
2. Ejecutar las celdas en orden (Restart & Run All), de arriba hacia abajo:
   - **Sección 1 — Descarga automatizada**: descarga los 3 archivos fuente desde Zenodo a `data/raw/`. Si los archivos ya existen, se omite la descarga (el panel pesa ~515 MB, la primera corrida puede tardar varios minutos).
   - **Sección 2 — Categorización de lesiones**: agrupa `injury_desc` en categorías médico-deportivas y guarda `data/raw/tm_injuries_categorized.csv`.
   - **Sección 3 — Filtrado del panel**: procesa `player_day_panel.csv` en streaming (chunks) y guarda el subconjunto de jugadores lesionados en `data/processed/player_day_panel_filtered.csv`.
   - **Sección 4 — Join final**: une mapping, panel filtrado y lesiones categorizadas en `data/processed/dataset_final.csv`.
   - **Sección 5 — Verificación**: chequeos de integridad (shape, jugadores únicos, huérfanos, anti fan-out).
3. El dataset final queda en `data/processed/dataset_final.csv`, listo para la siguiente entrega (modelado).

No se requiere ningún estado previo: el notebook corre de punta a punta desde un kernel nuevo (Restart & Run All) sin depender de ejecuciones parciales anteriores.
