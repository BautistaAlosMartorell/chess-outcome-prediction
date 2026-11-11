"""Pruebas de la comparación entre cortes (notebook 05), sin red ni datos."""

import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from src.comparacion_cortes import (
    CLASES, decision, diferencias_entre_cortes, intervalos, metricas_por_corte, perdida_por_fila, poblacion_comun,
    replicas_bootstrap,
)


def fake_predictions(n_games=40, seed=0):
    """Games of different lengths, one row per cut reached, like src.build_app.predecir_test."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        result = rng.choice(CLASES)
        for cut in range(0, int(rng.choice([20, 40, 60])) + 1, 10):
            p = rng.dirichlet([1, 1, 1])
            rows.append({"GameUrl": f"g{g}", "corte_ply": cut, "resultado": result,
                         "p_empate": p[0], "p_blancas": p[1], "p_negras": p[2],
                         "piso_p_empate": 0.1, "piso_p_blancas": 0.5, "piso_p_negras": 0.4})
    return pd.DataFrame(rows)


class MetricasTest(unittest.TestCase):
    def setUp(self):
        self.pred = fake_predictions()

    def test_row_loss_averages_to_sklearn_log_loss(self):
        proba = self.pred[["p_empate", "p_blancas", "p_negras"]].to_numpy()
        self.assertAlmostEqual(perdida_por_fila(self.pred).mean(), log_loss(self.pred["resultado"], proba, labels=CLASES))

    def test_decision_is_the_most_likely_class(self):
        pred = self.pred.head(1).assign(p_empate=0.2, p_blancas=0.3, p_negras=0.5)
        self.assertEqual(decision(pred).tolist(), ["Gana Negras"])

    def test_metrics_by_cut_put_both_metrics_side_by_side(self):
        table = metricas_por_corte(self.pred, "Gana Blancas").set_index("corte_ply")
        self.assertEqual(table["filas"].sum(), len(self.pred))
        at0 = self.pred[self.pred["corte_ply"] == 0]
        self.assertAlmostEqual(table.loc[0, "accuracy"], (decision(at0) == at0["resultado"]).mean())
        self.assertAlmostEqual(table.loc[0, "accuracy piso"], (at0["resultado"] == "Gana Blancas").mean())
        self.assertAlmostEqual(table.loc[0, "puntos sobre piso"],
                               100 * (table.loc[0, "accuracy"] - table.loc[0, "accuracy piso"]))
        self.assertAlmostEqual(table.loc[0, "mejora log_loss"], 1 - table.loc[0, "log_loss"] / table.loc[0, "log_loss piso"])


class PoblacionComunTest(unittest.TestCase):
    def test_same_games_in_every_cut(self):
        pred = fake_predictions()
        common = poblacion_comun(pred, 40)
        self.assertEqual(common["corte_ply"].max(), 40)
        per_cut = common.groupby("corte_ply")["GameUrl"].apply(frozenset)
        self.assertEqual(per_cut.nunique(), 1)
        self.assertEqual(set(per_cut.iloc[0]), set(pred.loc[pred["corte_ply"] == 40, "GameUrl"]))

    def test_no_game_reaches_the_cut(self):
        with self.assertRaises(ValueError):
            poblacion_comun(fake_predictions(), 500)


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.pred = fake_predictions(n_games=60)
        self.puntual = metricas_por_corte(self.pred, "Gana Blancas")
        self.replicas = replicas_bootstrap(self.pred, "Gana Blancas", n_replicas=300, random_state=1)

    def test_same_seed_same_replicates(self):
        again = replicas_bootstrap(self.pred, "Gana Blancas", n_replicas=300, random_state=1)
        pd.testing.assert_frame_equal(self.replicas["accuracy"], again["accuracy"])

    def test_intervals_surround_the_sample_value(self):
        table = intervalos(self.replicas, self.puntual)
        self.assertTrue((table["bajo"] <= table["alto"]).all())
        accuracy = table[table["metrica"] == "accuracy"]
        self.assertTrue(((accuracy["bajo"] <= accuracy["valor"]) & (accuracy["valor"] <= accuracy["alto"])).all())

    def test_a_cut_against_itself_does_not_change(self):
        common = poblacion_comun(self.pred, 20)
        replicas = replicas_bootstrap(common, "Gana Blancas", n_replicas=200)
        table = diferencias_entre_cortes(replicas, metricas_por_corte(common, "Gana Blancas"), [(10, 10), (0, 20)])
        same = table[(table["desde"] == 10) & (table["hasta"] == 10)]
        self.assertTrue((same[["cambio", "bajo", "alto"]] == 0).all().all())
        self.assertFalse(same["distinto de cero"].any())


if __name__ == "__main__":
    unittest.main()
