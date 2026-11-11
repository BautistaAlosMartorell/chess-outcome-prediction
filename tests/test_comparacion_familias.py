"""Pruebas de la comparación de familias por corte (notebook 05), sin red ni datos."""

import unittest

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import KFold, cross_validate

from src.comparacion_cortes import CLASES
from src.comparacion_familias import (
    diferencia_pareada, media_y_desvio, metricas_por_pedazo, predicciones_por_pedazo,
)


def fake_rows(n_games=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        result = rng.choice(CLASES, p=[0.1, 0.5, 0.4])
        for cut in range(0, 61, 10):
            # A feature that says more about the result as the game goes on.
            signal = {"Gana Blancas": 1.0, "Gana Negras": -1.0, "Empate": 0.0}[result] * cut / 60
            rows.append({"GameUrl": f"g{g}", "corte_ply": cut, "resultado": result,
                         "x": signal + rng.normal(scale=0.5)})
    return pd.DataFrame(rows)


def out_of_fold(rows, estimator, name):
    X = rows[["x", "corte_ply"]]
    folds = list(KFold(n_splits=3).split(X))
    result = cross_validate(estimator, X, rows["resultado"], cv=folds, return_estimator=True, return_indices=True,
                            scoring="neg_log_loss")
    return predicciones_por_pedazo(result, X, rows, name), result


class FamiliasTest(unittest.TestCase):
    def setUp(self):
        self.rows = fake_rows()
        self.logistic, self.cv_logistic = out_of_fold(self.rows, LogisticRegression(), "Logística")
        self.floor, _ = out_of_fold(self.rows, DummyClassifier(strategy="prior"), "Piso")
        self.pred = pd.concat([self.floor, self.logistic], ignore_index=True)

    def test_every_validation_row_once_per_model(self):
        self.assertEqual(len(self.logistic), len(self.rows))
        self.assertEqual(self.logistic[["GameUrl", "corte_ply"]].drop_duplicates().shape[0], len(self.rows))
        np.testing.assert_allclose(self.logistic[["p_empate", "p_blancas", "p_negras"]].sum(axis=1), 1)

    def test_fold_log_loss_matches_cross_validate(self):
        per_fold = metricas_por_pedazo(self.logistic).set_index("fold")["log_loss"]
        np.testing.assert_allclose(per_fold.to_numpy(), -self.cv_logistic["test_score"])

    def test_by_cut_rows_add_up_and_match_sklearn(self):
        table = metricas_por_pedazo(self.pred, "corte_ply")
        self.assertEqual(table["filas"].sum(), len(self.pred))
        one = self.logistic[(self.logistic["fold"] == 1) & (self.logistic["corte_ply"] == 30)]
        expected = log_loss(one["resultado"], one[["p_empate", "p_blancas", "p_negras"]].to_numpy(), labels=CLASES)
        got = table[(table["modelo"] == "Logística") & (table["fold"] == 1) & (table["corte_ply"] == 30)]["log_loss"]
        self.assertAlmostEqual(got.item(), expected)

    def test_bands_keep_their_order(self):
        table = metricas_por_pedazo(self.pred, "tramo")
        summary = media_y_desvio(table, "tramo")
        self.assertEqual([str(t) for t in summary.loc["Logística"].index], ["0", "5–20", "25–40", "45–60"])
        self.assertIn("± log_loss", summary.columns)

    def test_paired_difference_against_itself_is_zero(self):
        table = metricas_por_pedazo(self.pred, "tramo")
        same = diferencia_pareada(table, "Logística", "Logística", "tramo")
        self.assertTrue((same["diferencia"] == 0).all())
        self.assertFalse(same["le gana"].any() or same["pierde"].any())

    def test_paired_difference_direction(self):
        # Late cuts carry a clear signal: the logistic beats the floor in log-loss and in accuracy.
        table = metricas_por_pedazo(self.pred, "tramo")
        diff = diferencia_pareada(table, "Logística", "Piso", "tramo").set_index(["tramo", "metrica"])
        self.assertLess(diff.loc[("45–60", "log_loss"), "diferencia"], 0)
        self.assertGreater(diff.loc[("45–60", "accuracy"), "diferencia"], 0)
        reverse = diferencia_pareada(table, "Piso", "Logística", "tramo").set_index(["tramo", "metrica"])
        self.assertEqual(bool(diff.loc[("45–60", "log_loss"), "le gana"]), bool(reverse.loc[("45–60", "log_loss"), "pierde"]))


if __name__ == "__main__":
    unittest.main()
