"""Calibración de las probabilidades del clasificador final (notebook 04, sección 7b).

El bosque promedia muchos árboles y eso achata las probabilidades extremas: con una
ventaja grande de material el modelo da menos de lo que pasa en la realidad. Un
calibrador corrige esa escala **después** del modelo, sin tocar sus columnas ni su orden
de preferencias, y se ajusta con predicciones de partidas que el modelo no vio.

Métodos:

- ``"temperatura"``: un exponente ``a`` para las tres probabilidades, ``p ∝ p**a``
  (``a > 1`` las hace más marcadas). Un solo parámetro.
- ``"temperatura_tramo"``: un exponente por tramo de jugadas (``src.metricas_tramo``),
  porque el achatamiento crece a medida que avanza la partida.
- ``"isotonica"``: una regresión isotónica por clase (uno contra el resto) y
  renormalización, como ``CalibratedClassifierCV(method="isotonic")``.

``ModeloCalibrado`` envuelve el pipeline ajustado y expone lo mismo que usa la app:
``classes_``, ``predict_proba``, ``predict`` y ``named_steps`` (el transformador de
historial lo consultan ``predecir()``, la auditoría y la trivia).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss

from src.metricas_tramo import LIMITES_TRAMO, TRAMOS

METODOS = ("temperatura", "temperatura_tramo", "isotonica")
# Floor before the log: an isotonic step can return exactly 0.
EPS = 1e-6
# Bounds for the exponent: beyond these the probabilities would be absurdly flat or sharp.
LIMITES_EXPONENTE = (0.5, 4.0)


def _tramo(corte_ply: Any) -> np.ndarray:
    """Tramo de cada ply; los plies después del 120 (la app predice todos) van al último."""
    cortes = np.clip(np.asarray(corte_ply, dtype=float), 0, LIMITES_TRAMO[-1])
    return np.asarray(TRAMOS)[np.searchsorted(LIMITES_TRAMO[1:], cortes, side="left")]


def _potencia(proba: np.ndarray, exponente: float | np.ndarray) -> np.ndarray:
    logits = np.log(np.clip(proba, EPS, 1)) * np.reshape(exponente, (-1, 1))
    logits -= logits.max(axis=1, keepdims=True)
    scaled = np.exp(logits)
    return scaled / scaled.sum(axis=1, keepdims=True)


def _mejor_exponente(proba: np.ndarray, y: np.ndarray, classes: list[str]) -> float:
    result = minimize_scalar(lambda a: log_loss(y, _potencia(proba, a), labels=classes),
                             bounds=LIMITES_EXPONENTE, method="bounded")
    return float(result.x)


class Calibrador:
    """Mapa de probabilidades a probabilidades, ajustado con predicciones fuera de muestra."""

    def __init__(self, metodo: str):
        if metodo not in METODOS:
            raise ValueError(f"Método desconocido: {metodo}")
        self.metodo = metodo

    def fit(self, proba: np.ndarray, y: Any, corte_ply: Any, classes: list[str]) -> "Calibrador":
        proba, y = np.asarray(proba, dtype=float), np.asarray(y)
        self.classes_ = list(classes)
        if self.metodo == "temperatura":
            self.exponente_ = _mejor_exponente(proba, y, self.classes_)
        elif self.metodo == "temperatura_tramo":
            tramo = _tramo(corte_ply)
            self.exponentes_ = {t: _mejor_exponente(proba[tramo == t], y[tramo == t], self.classes_) for t in TRAMOS}
        else:
            self.isotonicas_ = [
                IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(proba[:, k], (y == label).astype(float))
                for k, label in enumerate(self.classes_)
            ]
        return self

    def transform(self, proba: np.ndarray, corte_ply: Any) -> np.ndarray:
        proba = np.asarray(proba, dtype=float)
        if self.metodo == "temperatura":
            return _potencia(proba, self.exponente_)
        if self.metodo == "temperatura_tramo":
            return _potencia(proba, np.array([self.exponentes_[t] for t in _tramo(corte_ply)]))
        calibrated = np.column_stack([iso.predict(proba[:, k]) for k, iso in enumerate(self.isotonicas_)])
        calibrated = np.clip(calibrated, EPS, 1)
        return calibrated / calibrated.sum(axis=1, keepdims=True)

    def describir(self) -> dict[str, Any]:
        """Lo que se guarda en el reporte: el método y sus parámetros legibles."""
        if self.metodo == "temperatura":
            return {"metodo": self.metodo, "exponente": self.exponente_}
        if self.metodo == "temperatura_tramo":
            return {"metodo": self.metodo, "exponentes": self.exponentes_}
        return {"metodo": self.metodo}


class ModeloCalibrado(BaseEstimator, ClassifierMixin):
    """El pipeline ajustado seguido del calibrador; se usa igual que el pipeline."""

    def __init__(self, modelo: Any, calibrador: Calibrador):
        self.modelo = modelo
        self.calibrador = calibrador

    @property
    def classes_(self) -> np.ndarray:
        return self.modelo.classes_

    @property
    def named_steps(self) -> Any:
        return self.modelo.named_steps

    def __sklearn_is_fitted__(self) -> bool:
        return True

    def fit(self, X: Any = None, y: Any = None) -> "ModeloCalibrado":
        """Already fitted: the model and the calibrator are fitted separately (notebook 04)."""
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.calibrador.transform(self.modelo.predict_proba(X), X["corte_ply"])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.classes_)[self.predict_proba(X).argmax(axis=1)]
