"""Comparación de las familias de modelos corte por corte (notebook 05).

El notebook 04 compara el piso, la regresión logística, el random forest y el gradient
boosting con validación cruzada temporal, y elige con la log-loss **promediada sobre
todos los cortes**. Para no volver a entrenar, guarda lo que predijo cada familia en la
parte de validación de cada pedazo (``FAMILIAS_POR_PEDAZO``). El notebook 05 lo lee y
lo desglosa por corte y por tramo de jugadas:

- cada métrica se calcula **dentro de cada pedazo** y se informa la media ± el desvío
  de los cinco, como la tabla de comparación del 04;
- dos familias se comparan **pedazo a pedazo** (la diferencia en el mismo pedazo y el
  mismo grupo de filas), con la misma regla del 04: una le gana a la otra sólo si la
  diferencia media supera su desvío.

No decide nada: el modelo de la app es el que dejó el 04.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score

from src.comparacion_cortes import CLASES, COLUMNA_PROBA, decision, perdida_por_fila
from src.metricas_tramo import TRAMOS, tramo_de_corte
from src.predict import RESULT_ORDER

# Written by notebook 04 next to its report; not versioned, like the model.
FAMILIAS_POR_PEDAZO = Path("models/familias_por_pedazo.parquet")
# Lower is better for these; higher for the rest.
MENOR_ES_MEJOR = {"log_loss"}
METRICAS = ["log_loss", "accuracy", "f1_macro", "recall_empate"]


def predicciones_por_pedazo(resultado_cv: dict[str, Any], X: pd.DataFrame, filas: pd.DataFrame,
                            modelo: str) -> pd.DataFrame:
    """Probabilidades de cada pedazo de validación, con el estimador entrenado en ese pedazo.

    ``resultado_cv`` sale de ``cross_validate(..., return_estimator=True, return_indices=True)``.
    ``filas`` son las mismas filas que ``X``, en el mismo orden, con ``GameUrl``,
    ``corte_ply`` y ``resultado``.
    """
    assert len(X) == len(filas), "X y las filas no son la misma tabla"
    partes = []
    for fold, (estimador, validacion) in enumerate(
            zip(resultado_cv["estimator"], resultado_cv["indices"]["test"]), start=1):
        proba = estimador.predict_proba(X.iloc[validacion])
        clases = list(estimador.classes_)
        parte = filas.iloc[validacion][["GameUrl", "corte_ply", "resultado"]].reset_index(drop=True)
        parte["resultado"] = parte["resultado"].astype(str)
        for clase in CLASES:
            # By the estimator's own classes_, never by position.
            parte[COLUMNA_PROBA[clase]] = proba[:, clases.index(clase)] if clase in clases else 0.0
        parte.insert(0, "fold", fold)
        parte.insert(0, "modelo", modelo)
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def metricas_por_pedazo(pred: pd.DataFrame, grupo: str | None = None) -> pd.DataFrame:
    """Una fila por (modelo, fold[, grupo]) con la log-loss y las métricas de decisión fija.

    ``grupo`` es ``"corte_ply"``, ``"tramo"`` o ``None`` (todo el pedazo, como el 04).
    """
    pred = pred.assign(
        _perdida=perdida_por_fila(pred), _decision=decision(pred), _real=pred["resultado"].astype(str),
    )
    if grupo == "tramo":
        pred["tramo"] = tramo_de_corte(pred["corte_ply"])
    claves = ["modelo", "fold"] + ([grupo] if grupo else [])
    rows = []
    for clave, g in pred.groupby(claves, sort=True, observed=True):
        rows.append({
            **dict(zip(claves, clave)),
            "filas": len(g),
            "log_loss": float(g["_perdida"].mean()),
            "accuracy": float((g["_decision"] == g["_real"]).mean()),
            "f1_macro": f1_score(g["_real"], g["_decision"], labels=RESULT_ORDER, average="macro", zero_division=0),
            "recall_empate": recall_score(g["_real"], g["_decision"], labels=["Empate"], average="macro",
                                          zero_division=0),
        })
    tabla = pd.DataFrame(rows)
    if grupo == "tramo":
        tabla["tramo"] = pd.Categorical(tabla["tramo"], categories=TRAMOS, ordered=True)
        tabla = tabla.sort_values(claves).reset_index(drop=True)
    return tabla


def media_y_desvio(tabla: pd.DataFrame, grupo: str | None = None,
                   metricas: Sequence[str] = METRICAS) -> pd.DataFrame:
    """Media y desvío (ddof=1) de los pedazos, por modelo[, grupo], como ``summarize`` del 04."""
    claves = ["modelo"] + ([grupo] if grupo else [])
    agrupado = tabla.groupby(claves, sort=False, observed=True)[list(metricas)]
    media, desvio = agrupado.mean(), agrupado.std(ddof=1)
    columnas = {}
    for m in metricas:
        columnas[m] = media[m]
        columnas[f"± {m}"] = desvio[m]
    return pd.DataFrame(columnas)


def diferencia_pareada(tabla: pd.DataFrame, modelo: str, referencia: str, grupo: str | None = None,
                       metricas: Sequence[str] = ("log_loss", "accuracy")) -> pd.DataFrame:
    """``modelo − referencia`` en el mismo pedazo (y grupo): media, desvío y si supera el desvío.

    "le gana" sigue la regla del notebook 04: la diferencia media, en la dirección buena
    de la métrica, es mayor que su desvío. "pierde" es lo mismo en la dirección mala.
    """
    claves = ["fold"] + ([grupo] if grupo else [])
    a = tabla[tabla["modelo"] == modelo].set_index(claves)
    b = tabla[tabla["modelo"] == referencia].set_index(claves)
    assert len(a) and a.index.equals(b.index), f"{modelo} y {referencia} no tienen los mismos pedazos"
    rows = []
    for m in metricas:
        diff = (a[m] - b[m]).rename("diff").reset_index()
        partes = diff.groupby(grupo, sort=False, observed=True)["diff"] if grupo else [(None, diff["diff"])]
        signo = -1 if m in MENOR_ES_MEJOR else 1
        for nombre, d in partes:
            media, desvio = float(d.mean()), float(d.std(ddof=1))
            rows.append({
                **({grupo: nombre} if grupo else {}),
                "metrica": m, "modelo": modelo, "referencia": referencia,
                "diferencia": media, "± diferencia": desvio,
                "le gana": signo * media > desvio, "pierde": -signo * media > desvio,
            })
    return pd.DataFrame(rows)
