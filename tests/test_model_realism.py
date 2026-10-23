"""Pruebas de comportamiento del artefacto final, sin acceso de red.

Requieren el modelo local del notebook 04; las pruebas de población/calibración
requieren además los datos regenerables. Las tolerancias amplias se fijan como
contratos de comportamiento, no como las métricas exactas de una corrida.
El artefacto actual incumple el contrato de +15 puntos por ganar la dama en
apertura: se conserva el fallo, explicado en plan-entrega-3.md.
"""

from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.history_transformer import attach_player_histories, player_history_payloads
from src.live_features import game_cut_features
from src.player_selection import load_selection
from src.predict import MODEL_PATH, RESULT_ORDER, cargar_modelo, model_input_frame, predecir
from test_live_features import MOVES, _pgn

ROOT = Path(__file__).resolve().parents[1]


class FinalModelRealismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / MODEL_PATH
        if not path.exists():
            raise unittest.SkipTest("Regenerar el artefacto con notebooks/04_modelado.ipynb")
        cls.artifact = cargar_modelo(path)
        cls.model = cls.artifact["resultado"]
        cls.columns = cls.artifact["columnas"]

    def predict(self, rows):
        proba = self.model.predict_proba(model_input_frame(pd.DataFrame(rows), self.columns))
        self.assertTrue(np.isfinite(proba).all())
        np.testing.assert_allclose(proba.sum(axis=1), 1, atol=1e-8)
        return pd.DataFrame(proba, columns=self.model.classes_)

    def test_initial_probabilities_are_near_observed_proportions(self):
        rows, _ = game_cut_features(_pgn(MOVES), [0], 180, 0)
        examples = []
        for rhythm, base in [("bullet", 60), ("blitz", 180), ("rapid", 600)]:
            for rating in [1000, 1700, 2300, 3100]:
                for side in ["blancas", "negras"]:
                    row = dict(rows[0], TimeClass=rhythm, tiempo_base_seg=base, incremento_seg=0, EsTorneo=False)
                    for color in ["blancas", "negras"]:
                        row[f"reloj_{color}_seg"] = base
                    row[f"elo_{side}_previo"] = rating
                    examples.append(row)
        average = self.predict(examples).mean()
        for label, expected, tolerance in [("Gana Blancas", .488, .12), ("Empate", .068, .08), ("Gana Negras", .444, .12)]:
            self.assertLess(abs(average[label] - expected), tolerance, f"{label}: {average[label]:.3f}")

    def test_winning_a_queen_clearly_helps_the_side_that_wins_it(self):
        # Two legal, independent games: each color wins the opposing queen.
        examples = [
            (["e4", "e5", "Nf3", "Nc6", "Bc4", "Qh4", "Nxh4", "Nf6", "Nc3"], 4, 7, "Gana Blancas"),
            (["e4", "e5", "Qh5", "Nf6", "Bc4", "Nxh5", "Nf3", "Nc6"], 2, 6, "Gana Negras"),
        ]
        context = {"TimeClass": "blitz", "tiempo_base_seg": 180, "incremento_seg": 0, "EsTorneo": False}
        for moves, before, after, winner in examples:
            with self.subTest(winner=winner):
                predictions = predecir(_pgn([(san, 170 - i) for i, san in enumerate(moves)]), context, self.artifact)
                gain = predictions.loc[after, winner] - predictions.loc[before, winner]
                self.assertGreater(gain, .15, f"Queen gain changed {winner} by {gain:.3f}")

    def test_much_less_clock_hurts_each_side_on_the_same_board(self):
        rows, _ = game_cut_features(_pgn(MOVES), [20], 180, 0)
        neutral = dict(rows[0], TimeClass="blitz", tiempo_base_seg=180, incremento_seg=0, EsTorneo=False)
        for side in ["blancas", "negras"]:
            neutral[f"reloj_{side}_seg"] = 90
            neutral[f"reloj_frac_{side}"] = .5
        neutral["diferencia_reloj_seg"] = 0
        baseline = self.predict([neutral]).iloc[0]
        for side, label, sign in [("blancas", "Gana Blancas", -1), ("negras", "Gana Negras", 1)]:
            with self.subTest(side=side):
                hurried = dict(neutral)
                hurried[f"reloj_{side}_seg"] = 1
                hurried[f"reloj_frac_{side}"] = 1 / 180
                hurried["diferencia_reloj_seg"] = sign * 89
                probability = self.predict([hurried]).iloc[0][label]
                self.assertGreater(baseline[label] - probability, .05)

    def test_more_rating_difference_never_lowers_white_on_the_initial_board(self):
        # Control grid of docs/entregas/plan-mejora-modelo-app.md: both ratings known and one
        # day old, empty form, only the difference changes. Rapid 3000 has no training data.
        if not self.artifact.get("historial_rivales"):
            self.skipTest("El artefacto no se entrenó con ratings de rivales")
        differences = [-400, -200, 0, 200, 400]
        for rhythm, base in [("bullet", 60), ("blitz", 180), ("rapid", 600)]:
            board, _ = game_cut_features("1. e4 *", [0], base, 0)
            for mean in [1200, 1800, 2400, 3000]:
                if (rhythm, mean) == ("rapid", 3000):
                    continue
                with self.subTest(rhythm=rhythm, mean=mean):
                    rows = [dict(board[0], TimeClass=rhythm, tiempo_base_seg=base, incremento_seg=0, EsTorneo=False,
                                 elo_blancas_previo=mean + d / 2, elo_negras_previo=mean - d / 2,
                                 antiguedad_rating_dias_blancas=1.0, antiguedad_rating_dias_negras=1.0)
                            for d in differences]
                    white = self.predict(rows)["Gana Blancas"].to_numpy()
                    self.assertTrue((np.diff(white) >= -1e-9).all(), dict(zip(differences, white.round(3))))

    @classmethod
    def population(cls):
        if hasattr(cls, "_population"):
            return cls._population
        clean = ROOT / "data/processed/partidas_ajedrez_clean.parquet"
        cuts_path = ROOT / "data/processed/partidas_cortes.parquet"
        if not clean.exists() or not cuts_path.exists():
            raise unittest.SkipTest("Regenerar las tablas con el pipeline")
        games = pd.read_parquet(clean)
        cutoff = pd.Timestamp(cls.artifact["entrenado_hasta"])
        future = games[games["StartTime"] >= cutoff]
        paths = {u: ROOT / f"data/raw/chesscom_{u}_raw.json" for u in load_selection(ROOT / "config/jugadores_seleccionados.yaml")}
        if not all(path.exists() for path in paths.values()):
            raise unittest.SkipTest("Faltan historiales crudos para las pruebas de población")
        # The same history sources the artifact was trained with.
        histories = player_history_payloads(paths, games[["GameUrl", "StartTime"]],
                                            rivales=cls.artifact.get("historial_rivales", False))
        context = attach_player_histories(future, histories)
        cuts = pd.read_parquet(cuts_path)
        cuts = cuts[cuts["GameUrl"].isin(future["GameUrl"])]
        fixed = ["GameUrl", "TimeClass", "tiempo_base_seg", "incremento_seg", "EsTorneo", "StartTime", "historial_blancas", "historial_negras"]
        count = len(cuts)
        merged = cuts.merge(context[fixed], on="GameUrl", how="left", validate="many_to_one")
        assert len(merged) == count, "Fan-out en la población de prueba"
        cls._population = merged
        return merged

    def test_real_winner_gets_more_probability_near_the_end_on_average(self):
        rows = self.population()
        # Fix the same games at both moments; do not compare changing populations.
        late = rows[rows["corte_ply"] >= 60].sort_values("corte_ply").drop_duplicates("GameUrl", keep="last")
        late = late[(late["resultado"] != "Empate") & (late["plies_restantes"] <= 10)].sample(n=1000, random_state=42)
        early = rows[(rows["corte_ply"] == 0) & rows["GameUrl"].isin(late["GameUrl"])].set_index("GameUrl").loc[late["GameUrl"]]
        late_proba, early_proba = self.predict(late), self.predict(early)
        outcome = late["resultado"].astype(str).to_numpy()
        winner_late = np.array([late_proba.loc[i, y] for i, y in enumerate(outcome)])
        winner_early = np.array([early_proba.loc[i, y] for i, y in enumerate(outcome)])
        self.assertGreater((winner_late - winner_early).mean(), .10)

    def test_classwise_calibration_within_eight_percentage_points(self):
        sample = self.population().sample(n=5000, random_state=42)
        proba = self.predict(sample)
        for label in RESULT_ORDER:
            predicted = proba[label].to_numpy()
            actual = sample["resultado"].eq(label).to_numpy()
            bins = np.minimum((predicted * 10).astype(int), 9)
            ece = sum(np.mean(bins == b) * abs(actual[bins == b].mean() - predicted[bins == b].mean())
                      for b in range(10) if (bins == b).any())
            self.assertLess(ece, .08, f"{label}: ECE={ece:.3f}")


if __name__ == "__main__":
    unittest.main()
