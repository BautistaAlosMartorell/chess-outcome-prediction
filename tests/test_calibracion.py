"""Pruebas del calibrador de probabilidades (notebook 04, sección 7b), sin red."""

import pickle
import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from src.calibracion import METODOS, Calibrador, ModeloCalibrado, _tramo

CLASSES = ["Empate", "Gana Blancas", "Gana Negras"]


def _underconfident(n=6000, seed=0):
    """Labels drawn from sharp probabilities, but reported flattened (as a forest does)."""
    rng = np.random.default_rng(seed)
    truth = rng.dirichlet([0.6, 1.2, 1.2], size=n)
    y = np.array([rng.choice(CLASSES, p=p) for p in truth])
    flat = truth ** 0.6
    flat /= flat.sum(axis=1, keepdims=True)
    return flat, y, rng.choice(np.arange(0, 121, 5), size=n)


class CalibradorTest(unittest.TestCase):
    def test_every_method_improves_flattened_probabilities_on_new_rows(self):
        p_fit, y_fit, cut_fit = _underconfident(seed=0)
        p_new, y_new, cut_new = _underconfident(seed=1)
        raw = log_loss(y_new, p_new, labels=CLASSES)
        for method in METODOS:
            calibrated = Calibrador(method).fit(p_fit, y_fit, cut_fit, CLASSES).transform(p_new, cut_new)
            np.testing.assert_allclose(calibrated.sum(axis=1), 1)
            self.assertLess(log_loss(y_new, calibrated, labels=CLASSES), raw, method)

    def test_temperature_sharpens_and_keeps_the_chosen_class(self):
        p, y, cut = _underconfident()
        cal = Calibrador("temperatura").fit(p, y, cut, CLASSES)
        self.assertGreater(cal.exponente_, 1)
        out = cal.transform(p, cut)
        np.testing.assert_array_equal(out.argmax(axis=1), p.argmax(axis=1))
        self.assertGreater(out.max(axis=1).mean(), p.max(axis=1).mean())

    def test_plies_after_120_use_the_last_band(self):
        self.assertEqual(_tramo([0, 5, 20, 25, 120, 180]).tolist(), ["0", "5–20", "5–20", "25–40", "95–120", "95–120"])

    def test_unknown_method_fails(self):
        with self.assertRaises(ValueError):
            Calibrador("platt")


class ModeloCalibradoTest(unittest.TestCase):
    def test_wraps_a_pipeline_like_the_app_expects(self):
        p, y, cut = _underconfident(n=300)
        inner = SimpleNamespace(classes_=np.array(CLASSES), named_steps={"historial": "transformer"},
                                predict_proba=lambda X: p[: len(X)])
        cal = Calibrador("temperatura").fit(p, y, cut, CLASSES)
        model = ModeloCalibrado(inner, cal)
        X = pd.DataFrame({"corte_ply": cut})
        np.testing.assert_allclose(model.predict_proba(X), cal.transform(p, cut))
        self.assertEqual(list(model.classes_), CLASSES)
        self.assertIn("historial", model.named_steps)
        self.assertEqual(model.predict(X).shape, (300,))

    def test_survives_a_round_trip(self):
        p, y, cut = _underconfident(n=500)
        cal = Calibrador("temperatura_tramo").fit(p, y, cut, CLASSES)
        again = pickle.loads(pickle.dumps(cal))
        np.testing.assert_allclose(again.transform(p, cut), cal.transform(p, cut))


if __name__ == "__main__":
    unittest.main()
