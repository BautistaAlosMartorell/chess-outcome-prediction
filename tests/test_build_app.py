"""Pruebas de la construcción de la app de la Entrega 4, sin acceso de red.

Las primeras usan tablas chicas inventadas. Las de los archivos generados se saltean si
todavía no se corrió ``python -m src.build_app``.
"""

import json
import re
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src import app_charts
from src.build_app import MAXIMO_MB, SALIDA, _log_loss, curva_de_test, muestra_explora, verificar_contra_notebook
from src.predict import RESULT_ORDER

ROOT = Path(__file__).resolve().parents[1]
PROBAS = ["p_blancas", "p_empate", "p_negras"]


def _predicciones(n_games=40, cuts=(0, 5, 10)):
    rng = np.random.default_rng(0)
    rows = []
    for g in range(n_games):
        result = RESULT_ORDER[g % 3]
        for cut in cuts:
            p = rng.dirichlet([2, 1, 2])
            rows.append({"GameUrl": f"https://chess.com/game/{g}", "corte_ply": cut, "balance_material": int(rng.integers(-3, 4)),
                         "resultado": result, "p_blancas": p[0], "p_empate": p[1], "p_negras": p[2],
                         "piso_p_blancas": 0.45, "piso_p_empate": 0.1, "piso_p_negras": 0.45})
    return pd.DataFrame(rows)


def _partidas(pred):
    urls = pred["GameUrl"].unique()
    return pd.DataFrame({
        "GameUrl": urls, "White": [f"w{i}" for i in range(len(urls))], "Black": [f"b{i}" for i in range(len(urls))],
        "WhiteElo": 1500, "BlackElo": 1520, "TimeClass": ["bullet", "blitz"] * (len(urls) // 2),
        "nivel_promedio": "intermedio", "resultado": [RESULT_ORDER[i % 3] for i in range(len(urls))],
        "Termination": "resignation", "StartTime": pd.date_range("2026-07-01", periods=len(urls), freq="h", tz="UTC"),
    })


def _escalas(spec):
    """Every color scale in a serialized spec, wherever it sits."""
    found = []
    if isinstance(spec, dict):
        if isinstance(spec.get("scale"), dict) and "range" in spec["scale"] and "domain" in spec["scale"]:
            found.append(spec["scale"])
        for value in spec.values():
            found += _escalas(value)
    elif isinstance(spec, list):
        for value in spec:
            found += _escalas(value)
    return found


class ChartsTest(unittest.TestCase):
    def setUp(self):
        self.pred = _predicciones()
        self.games = _partidas(self.pred)

    def test_result_colors_are_the_same_in_every_chart(self):
        filas, partidas = muestra_explora(self.pred, self.games, random_state=0)
        spec = app_charts.explora(filas, partidas, ["intermedio"])
        result_scales = [s for s in _escalas(spec) if s["domain"] == RESULT_ORDER]
        self.assertEqual(len(result_scales), 2)  # the scatter and the selected game's curve
        for scale in result_scales:
            self.assertEqual(scale["range"], [app_charts.COLOR_RESULTADO[r] for r in RESULT_ORDER])

    def test_explora_declares_its_controls_and_detail(self):
        filas, partidas = muestra_explora(self.pred, self.games, random_state=0)
        spec = app_charts.explora(filas, partidas, ["intermedio"])
        params = {p["name"]: p for p in spec["params"]}
        self.assertEqual(params["corte"]["bind"]["input"], "range")
        self.assertEqual(params["ritmo"]["bind"]["input"], "select")
        self.assertEqual(params["nivel"]["bind"]["input"], "select")
        self.assertEqual(params["elegida"]["select"]["type"], "point")
        # The per-game table travels once, as a named dataset.
        self.assertEqual(len(spec["datasets"]["partidas"]), len(partidas))
        self.assertNotIn('"data": {"values"', json.dumps(spec["vconcat"]))

    def test_tallo_charts_serialize(self):
        vivas = pd.DataFrame({"TimeClass": ["bullet", "blitz"], "corte_ply": [0, 0], "partidas": [10, 20], "siguen": [1.0, 1.0]})
        eta2 = pd.DataFrame({"variable": ["Material", "Reloj, a igual material"], "corte_ply": [10, 10], "eta2": [0.0, 0.01]})
        curva = curva_de_test(self.pred)
        larga = pd.concat([curva.assign(serie="Modelo", log_loss=curva["modelo"]),
                           curva.assign(serie="Piso", log_loss=curva["piso"])])
        for chart in [app_charts.partidas_vivas(vivas), app_charts.senal_por_corte(eta2), app_charts.modelo_contra_piso(larga)]:
            spec = chart.to_dict()
            self.assertEqual(spec["config"]["background"], "transparent")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.pred = _predicciones()
        self.games = _partidas(self.pred)

    def test_explora_sample_keeps_every_cut_of_each_game(self):
        filas, partidas = muestra_explora(self.pred, self.games, random_state=0)
        self.assertEqual(set(filas["id"]), set(partidas["id"]))
        self.assertTrue(filas.groupby("id")["corte_ply"].nunique().eq(3).all())
        np.testing.assert_allclose(filas[PROBAS].sum(axis=1), 1, atol=0.002)

    def test_log_loss_reads_columns_in_the_right_order(self):
        perfect = self.pred.copy()
        for label, column in zip(RESULT_ORDER, PROBAS):
            perfect[column] = (perfect["resultado"] == label) * 0.97 + 0.01
        self.assertLess(_log_loss(perfect), 0.03)

    def test_rebuilt_test_must_match_the_notebook(self):
        curva = curva_de_test(self.pred)
        reporte = {
            "test": {"log_loss": _log_loss(self.pred), "log_loss piso": _log_loss(self.pred, "piso_")},
            "test_por_corte": [{"población": "todas", "corte_ply": int(r.corte_ply), "log_loss": r.modelo} for r in curva.itertuples()],
        }
        verificar_contra_notebook(self.pred, curva, reporte)
        reporte["test"]["log_loss"] += 0.001
        with self.assertRaises(AssertionError):
            verificar_contra_notebook(self.pred, curva, reporte)


class WebPaletteTest(unittest.TestCase):
    def test_chart_colors_are_the_web_tokens(self):
        css = (ROOT / "web/app/globals.css").read_text(encoding="utf-8")
        tokens = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6});", css))
        self.assertEqual(app_charts.COLOR_RESULTADO["Gana Blancas"], tokens["blancas"])
        self.assertEqual(app_charts.COLOR_RESULTADO["Empate"], tokens["tablas"])
        self.assertEqual(app_charts.COLOR_RESULTADO["Gana Negras"], tokens["negras"])
        self.assertEqual(app_charts.COLOR_MODELO, tokens["reloj"])


class GeneratedFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = ROOT / SALIDA
        if not (cls.dir / "resumen.json").exists():
            raise unittest.SkipTest("Generar la app con python -m src.build_app")
        cls.resumen = json.loads((cls.dir / "resumen.json").read_text(encoding="utf-8"))

    def test_files_exist_and_stay_light(self):
        for name in ["resumen.json", "graficos/datos.json", "graficos/hallazgos.json", "graficos/modelo.json",
                     "graficos/explora.json"]:
            path = self.dir / name
            self.assertTrue(path.exists(), name)
            self.assertLess(path.stat().st_size / 1e6, MAXIMO_MB, name)

    def test_cover_numbers_come_from_the_test_curve(self):
        curve = {row["corte_ply"]: row for row in self.resumen["modelo"]["test_por_corte"]}
        self.assertAlmostEqual(self.resumen["portada"]["mejora_antes_de_mover"], curve[0]["mejora"])
        self.assertAlmostEqual(self.resumen["portada"]["mejora_ply_60"], curve[60]["mejora"])
        self.assertEqual(self.resumen["portada"]["partidas"], self.resumen["datos"]["embudo"][-1]["filas"])

    def test_explora_probabilities_add_up(self):
        spec = json.loads((self.dir / "graficos/explora.json").read_text(encoding="utf-8"))
        rows = next(v for k, v in spec["datasets"].items() if k != "partidas" and len(v) > 1)
        total = np.array([[r[c] for c in PROBAS] for r in rows]).sum(axis=1)
        np.testing.assert_allclose(total, 1, atol=0.002)


if __name__ == "__main__":
    unittest.main()
