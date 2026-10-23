"""Archivos intermedios entre los notebooks y la app de la Entrega 4.

Los notebooks 02 y 04 exportan acá los números que ya calcularon (tablas e hipótesis),
y ``src.build_app`` los lee para armar los gráficos. Así la app muestra lo mismo que dan
los notebooks, sin copiar cifras a mano.
Ninguno de estos archivos se versiona: se regeneran corriendo los notebooks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

REPORTE_EDA = Path("data/processed/reporte_eda.json")
REPORTE_MODELADO = Path("models/reporte_modelado.json")


def tabla(df: pd.DataFrame | pd.Series) -> list[dict[str, Any]]:
    """Convierte una tabla de pandas en registros JSON, con el índice como columna."""
    frame = df.to_frame() if isinstance(df, pd.Series) else df
    return json.loads(frame.reset_index().to_json(orient="records", force_ascii=False, date_format="iso"))


def guardar_reporte(reporte: dict[str, Any], path: Path) -> None:
    """Escribe un reporte como JSON legible (UTF-8, con tildes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(reporte, file, indent=2, ensure_ascii=False, default=str)


def leer_reporte(path: Path) -> dict[str, Any]:
    """Lee un reporte; si falta, dice qué notebook hay que correr para generarlo."""
    if not path.exists():
        notebook = "04_modelado" if path == REPORTE_MODELADO else "02_eda_hipotesis"
        raise FileNotFoundError(f"Falta {path}: correr notebooks/{notebook}.ipynb con Restart & Run All.")
    with path.open(encoding="utf-8") as file:
        return json.load(file)
