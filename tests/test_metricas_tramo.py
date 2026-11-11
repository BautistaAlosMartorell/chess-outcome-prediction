"""Pruebas de las métricas por tramo de jugadas (devolución de la Entrega 3), sin red."""

import unittest

import numpy as np
import pandas as pd

from src import app_charts
from src.metricas_tramo import TRAMOS, confusion_por_tramo, metricas_por_tramo, predicha, tramo_de_corte

CLASSES = ["Empate", "Gana Blancas", "Gana Negras"]


class TramoTest(unittest.TestCase):
    def test_every_cut_of_the_config_falls_in_one_band(self):
        cuts = np.arange(0, 121, 5)
        bands = tramo_de_corte(cuts)
        self.assertEqual(bands[0], "0")
        self.assertEqual(list(pd.unique(bands)), TRAMOS)
        self.assertEqual(tramo_de_corte([20, 25, 120]).tolist(), ["5–20", "25–40", "95–120"])

    def test_a_cut_outside_the_bands_fails(self):
        with self.assertRaises(AssertionError):
            tramo_de_corte([125])

    def test_fixed_decision_is_the_most_likely_class(self):
        proba = np.array([[0.2, 0.5, 0.3], [0.6, 0.1, 0.3]])
        self.assertEqual(predicha(proba, CLASSES).tolist(), ["Gana Blancas", "Empate"])


class MetricasTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.cuts = np.tile(np.arange(0, 121, 5), 30)
        self.y = rng.choice(["Gana Blancas", "Empate", "Gana Negras"], size=len(self.cuts))
        self.proba = rng.dirichlet([1, 1, 1], size=len(self.cuts))
        self.games = np.repeat([f"g{i}" for i in range(30)], 25)

    def test_accuracy_counts_hits_and_the_floor_always_says_one_class(self):
        table = metricas_por_tramo(self.y, self.proba, CLASSES, self.cuts, self.games, "Gana Blancas").set_index("tramo")
        self.assertEqual(table["filas"].sum(), len(self.y))
        hits = predicha(self.proba, CLASSES) == self.y
        band = tramo_de_corte(self.cuts)
        for t in TRAMOS:
            self.assertAlmostEqual(table.loc[t, "accuracy"], hits[band == t].mean())
            self.assertAlmostEqual(table.loc[t, "accuracy piso"], (self.y[band == t] == "Gana Blancas").mean())
        self.assertEqual(table.loc["0", "partidas"], 30)

    def test_confusion_rows_add_up_to_100_and_to_every_row(self):
        confusion = confusion_por_tramo(self.y, predicha(self.proba, CLASSES), self.cuts)
        self.assertEqual(confusion["filas"].sum(), len(self.y))
        by_real = confusion.groupby(["tramo", "real"])["porcentaje_fila"].sum()
        np.testing.assert_allclose(by_real.to_numpy(), 100)

    def test_precision_columns_add_up_to_100_and_stay_empty_when_never_predicted(self):
        # The model never says "Empate" here: that column has no precision, not a 0 %.
        y = np.array(["Gana Blancas", "Gana Negras", "Empate", "Gana Blancas"])
        decided = np.array(["Gana Blancas", "Gana Blancas", "Gana Negras", "Gana Blancas"])
        confusion = confusion_por_tramo(y, decided, [0, 0, 0, 0]).set_index(["real", "predicho"])
        self.assertAlmostEqual(confusion.loc[("Gana Blancas", "Gana Blancas"), "porcentaje_columna"], 200 / 3)
        self.assertAlmostEqual(confusion.loc[("Gana Negras", "Gana Blancas"), "porcentaje_columna"], 100 / 3)
        self.assertAlmostEqual(confusion.loc[("Empate", "Gana Negras"), "porcentaje_columna"], 100)
        self.assertTrue(confusion.xs("Empate", level="predicho")["porcentaje_columna"].isna().all())
        by_predicted = confusion.groupby(level="predicho")["porcentaje_columna"].sum(min_count=1).dropna()
        np.testing.assert_allclose(by_predicted.to_numpy(), 100)

    def test_bands_without_rows_are_left_out(self):
        confusion = confusion_por_tramo(["Empate"], ["Empate"], [10])
        self.assertEqual(confusion["tramo"].unique().tolist(), ["5–20"])


class ChartsTest(unittest.TestCase):
    def test_band_charts_serialize_with_the_band_order(self):
        acierto = pd.DataFrame({"serie": ["Modelo", "Piso"] * 6, "tramo": np.repeat(TRAMOS, 2),
                                "accuracy": 0.5, "filas": 10})
        confusion = pd.DataFrame({"tramo": "0", "real": ["Empate", "Gana Blancas"], "predicho": ["Empate", "Empate"],
                                  "porcentaje_fila": [50.0, 10.0], "porcentaje_columna": [np.nan, 25.0], "filas": [1, 1]})
        importancia = pd.DataFrame({"nombre": list(app_charts.NOMBRE_COLUMNA.values()), "tramo": "0",
                                    "log_loss": 0.01, "accuracy": 0.01})
        specs = [app_charts.acierto_por_tramo(acierto, TRAMOS).to_dict(),
                 app_charts.confusion_por_tramo(confusion, TRAMOS).to_dict(),
                 app_charts.importancia_por_tramo(importancia, TRAMOS).to_dict()]
        for spec in specs:
            self.assertEqual(spec["config"]["background"], "transparent")
        self.assertEqual(specs[0]["layer"][0]["encoding"]["x"]["sort"], TRAMOS)
        self.assertEqual(specs[1]["params"][0]["bind"]["options"], TRAMOS)
        self.assertEqual(specs[1]["params"][1]["bind"]["options"], app_charts.VISTAS_CONFUSION)
        # An undefined precision travels as null, never as NaN (invalid JSON for the web).
        rows = next(iter(specs[1]["datasets"].values()))
        self.assertIsNone(rows[0]["porcentaje_columna"])


if __name__ == "__main__":
    unittest.main()
