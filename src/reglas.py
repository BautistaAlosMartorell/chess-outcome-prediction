"""Reglas del ajedrez que el modelo no puede violar (notebook 04, sección 8).

Un lado al que no le alcanza el material para dar mate (rey solo, o rey y una pieza
menor) no puede ganar: si al rival se le cae la bandera, la partida es tablas. En el
dataset no hay ni una partida que lo contradiga, pero el bosque promedia hojas y le
puede dejar algo de probabilidad (con el reloj del rival casi en cero, mucha). La regla
pone en 0 la victoria imposible y reparte el resto en proporción; si ninguno de los dos
puede dar mate, son tablas. Lee ``puede_dar_mate_*`` de la misma fila que el modelo.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

GANA = {"Gana Blancas": "puede_dar_mate_blancas", "Gana Negras": "puede_dar_mate_negras"}


def aplicar_regla_de_mate(proba: np.ndarray, classes: list[str], X: pd.DataFrame) -> np.ndarray:
    """Probabilidades con las victorias imposibles en 0; filas sin el dato quedan igual."""
    proba = np.array(proba, dtype=float, copy=True)
    for label, column in GANA.items():
        cannot = (pd.to_numeric(X[column]) == 0).to_numpy()
        proba[cannot, classes.index(label)] = 0.0
    total = proba.sum(axis=1, keepdims=True)
    # Neither side can mate: the game is drawn on the board.
    dead = total[:, 0] == 0
    proba[dead] = 0.0
    proba[dead, classes.index("Empate")] = 1.0
    total[dead] = 1.0
    return proba / total


class ConReglaDeMate(BaseEstimator, ClassifierMixin):
    """El modelo ajustado (con o sin calibrar) seguido de la regla; se usa igual que él."""

    def __init__(self, modelo: Any):
        self.modelo = modelo

    @property
    def classes_(self) -> np.ndarray:
        return self.modelo.classes_

    @property
    def named_steps(self) -> Any:
        return getattr(self.modelo, "named_steps", {})

    def __sklearn_is_fitted__(self) -> bool:
        return True

    def fit(self, X: Any = None, y: Any = None) -> "ConReglaDeMate":
        """Already fitted: the rule learns nothing."""
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return aplicar_regla_de_mate(self.modelo.predict_proba(X), list(self.classes_), X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.classes_)[self.predict_proba(X).argmax(axis=1)]
