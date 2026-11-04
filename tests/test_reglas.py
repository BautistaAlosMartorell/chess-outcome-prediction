"""Pruebas de la regla de mate que va después del modelo (src/reglas.py)."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.reglas import ConReglaDeMate, aplicar_regla_de_mate

CLASSES = ["Empate", "Gana Blancas", "Gana Negras"]


class _Fijo:
    classes_ = np.array(CLASSES)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.tile([0.47, 0.17, 0.36], (len(X), 1))


def _frame(blancas: list[float], negras: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"puede_dar_mate_blancas": blancas, "puede_dar_mate_negras": negras})


class ReglaDeMateTest(unittest.TestCase):
    def test_impossible_win_goes_to_zero_and_the_rest_keeps_its_proportion(self) -> None:
        proba = aplicar_regla_de_mate(np.array([[0.47, 0.17, 0.36]]), CLASSES, _frame([0], [1]))
        np.testing.assert_allclose(proba, [[0.47 / 0.83, 0.0, 0.36 / 0.83]])

    def test_both_sides_able_or_unknown_leaves_the_model_alone(self) -> None:
        original = np.array([[0.2, 0.5, 0.3], [0.1, 0.6, 0.3]])
        np.testing.assert_allclose(aplicar_regla_de_mate(original, CLASSES, _frame([1, np.nan], [1, np.nan])), original)

    def test_nobody_can_mate_is_a_draw(self) -> None:
        np.testing.assert_allclose(aplicar_regla_de_mate(np.array([[0.2, 0.5, 0.3]]), CLASSES, _frame([0], [0])), [[1, 0, 0]])

    def test_wrapper_applies_the_rule_and_keeps_the_model_interface(self) -> None:
        model = ConReglaDeMate(_Fijo())
        X = _frame([1, 0], [1, 1])
        proba = model.predict_proba(X)
        self.assertEqual(list(model.classes_), CLASSES)
        self.assertEqual(proba[1, 1], 0.0)
        np.testing.assert_allclose(proba.sum(axis=1), 1)
        self.assertEqual(list(model.predict(X)), ["Empate", "Empate"])


if __name__ == "__main__":
    unittest.main()
