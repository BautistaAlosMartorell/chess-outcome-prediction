"""Métricas del clasificador por tramo de jugadas (devolución de la Entrega 3).

El notebook 04 y ``src.build_app`` agrupan los cortes en los mismos tramos y calculan
las mismas métricas, así la app puede verificar que muestra lo que midió el notebook.
Además de la log-loss, se informan métricas de **decisión fija**: la clase predicha es
la de mayor probabilidad y sólo cuenta si acertó o no (accuracy, matriz de confusión).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss, recall_score

from src.predict import RESULT_ORDER

# Right-closed bins over corte_ply: cut 0 stands alone (before the first move).
LIMITES_TRAMO = [-1, 0, 20, 40, 60, 90, 120]
TRAMOS = ["0", "5–20", "25–40", "45–60", "65–90", "95–120"]


def tramo_de_corte(corte_ply: pd.Series | np.ndarray) -> np.ndarray:
    """Etiqueta de tramo de cada corte; falla si algún corte queda afuera."""
    tramo = pd.cut(np.asarray(corte_ply), LIMITES_TRAMO, labels=TRAMOS)
    assert not pd.isna(tramo).any(), "Un corte quedó fuera de los tramos"
    return np.asarray(tramo.astype(str))


def predicha(proba: np.ndarray, classes: Sequence[str]) -> np.ndarray:
    """Decisión fija: la clase de mayor probabilidad."""
    return np.asarray(classes)[np.asarray(proba).argmax(axis=1)]


def metricas_por_tramo(
    y: Sequence[str], proba: np.ndarray, classes: Sequence[str], corte_ply: Sequence[int],
    partida: Sequence[str], clase_piso: str,
) -> pd.DataFrame:
    """Una fila por tramo: probabilidades (log-loss) y decisión fija (accuracy, F1, recall).

    ``clase_piso`` es lo que decide el piso: la clase más frecuente de train, siempre la misma.
    """
    y, proba, partida = np.asarray(y), np.asarray(proba), np.asarray(partida)
    tramo, decided = tramo_de_corte(corte_ply), predicha(proba, classes)
    rows = []
    for label in TRAMOS:
        mask = tramo == label
        rows.append({
            "tramo": label,
            "filas": int(mask.sum()),
            "partidas": int(pd.unique(partida[mask]).size),
            "accuracy": accuracy_score(y[mask], decided[mask]),
            "accuracy piso": float(np.mean(y[mask] == clase_piso)),
            "log_loss": log_loss(y[mask], proba[mask], labels=list(classes)),
            "f1_macro": f1_score(y[mask], decided[mask], labels=RESULT_ORDER, average="macro", zero_division=0),
            "recall_empate": recall_score(y[mask], decided[mask], labels=["Empate"], average="macro", zero_division=0),
            "confianza media": float(proba[mask].max(axis=1).mean()),
        })
    return pd.DataFrame(rows)


def confusion_por_tramo(y: Sequence[str], decided: Sequence[str], corte_ply: Sequence[int]) -> pd.DataFrame:
    """Formato largo: (tramo, real, predicho) con el % de la fila real y el conteo."""
    y, decided, tramo = np.asarray(y), np.asarray(decided), tramo_de_corte(corte_ply)
    rows = []
    for label in TRAMOS:
        mask = tramo == label
        counts = confusion_matrix(y[mask], decided[mask], labels=RESULT_ORDER)
        share = counts / counts.sum(axis=1, keepdims=True)
        for i, real in enumerate(RESULT_ORDER):
            for j, pred in enumerate(RESULT_ORDER):
                rows.append({"tramo": label, "real": real, "predicho": pred,
                             "filas": int(counts[i, j]), "porcentaje_fila": float(share[i, j] * 100)})
    return pd.DataFrame(rows)
