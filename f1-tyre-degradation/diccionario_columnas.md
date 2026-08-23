# Diccionario de columnas — dataset F1 tyre degradation

Dataset: `data/f1_laps_clean.csv` — 22,999 vueltas × 14 columnas.
Cada fila = una vuelta de un piloto en una carrera.

| Columna   | Tipo    | Ejemplo            | Uso               | Descripción                                              |
|:----------|:--------|:-------------------|:------------------|:---------------------------------------------------------|
| Year      | int64   | 2024               | ID/contexto       | Temporada                                                |
| Round     | int64   | 1                  | ID/contexto       | Nº de carrera                                            |
| Event     | object  | Bahrain Grand Prix | ID/contexto       | Nombre del GP                                            |
| Driver    | object  | VER                | ID/contexto       | Piloto                                                   |
| LapNumber | float64 | 2.0                | FEATURE           | Vuelta de carrera — representa el efecto del combustible |
| Stint     | float64 | 1.0                | FEATURE           | Nº de tanda entre paradas                                |
| TyreLife  | float64 | 5.0                | FEATURE (central) | Vida del neumático (vueltas) — predictor central         |
| Compound  | object  | SOFT               | FEATURE (central) | Compuesto: SOFT/MEDIUM/HARD — predictor central          |
| FreshTyre | bool    | False              | FEATURE           | Si el neumático salió nuevo                              |
| TrackTemp | float64 | 23.8               | FEATURE (central) | Temperatura de pista (°C) — predictor central            |
| AirTemp   | float64 | 18.3               | FEATURE           | Temperatura del aire (°C)                                |
| Humidity  | float64 | 49.0               | FEATURE           | Humedad (%)                                              |
| Rainfall  | bool    | False              | FEATURE           | Lluvia (bool)                                            |
| LapTime   | float64 | 96.3               | TARGET            | Tiempo de vuelta (s) — lo que se predice (regresión)     |

**Leyenda:** TARGET · FEATURE (central) · FEATURE · feature (opcional) · derivado · ID/contexto · limpieza.