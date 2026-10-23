"""Trivia: elegibilidad, integridad de posiciones y consistencia del artefacto público."""
import json
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

import chess
import chess.pgn
import numpy as np
import pandas as pd

from src.app_trivia import candidatos_trivia, construir_trivia

ROOT = Path(__file__).resolve().parents[1] / "web/public/app/trivia"


class CandidatesTest(unittest.TestCase):
    def test_only_reference_cuts_with_two_clocks(self):
        rows = pd.DataFrame({"GameUrl": ["a"] * 5, "corte_ply": [0, 20, 40, 60, 120],
                             "reloj_blancas_seg": [100, 80, None, 20, 1],
                             "reloj_negras_seg": [100, 85, 60, None, 2]})
        self.assertEqual(candidatos_trivia(rows).corte_ply.tolist(), [20])

    def test_duplicates_are_rejected(self):
        row = {"GameUrl": "a", "corte_ply": 20, "reloj_blancas_seg": 50, "reloj_negras_seg": 60}
        with self.assertRaises(AssertionError):
            candidatos_trivia(pd.DataFrame([row, row]))


class BankConstructionTest(unittest.TestCase):
    def build(self, directory, wrong_probability=False, invert_results=False):
        from types import SimpleNamespace
        from src.history_transformer import PlayerHistoryTransformer
        san = "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Nb8 d4 Nbd7 c4 c6 Nc3 Qc7".split()
        game = chess.pgn.Game()
        board, node = game.board(), game
        for i, move in enumerate(san):
            played = board.parse_san(move)
            node = node.add_variation(played)
            node.set_clock(180 - i)
            board.push(played)
        raw_path = Path(directory) / "raw.json"
        urls = [f"game-{i}" for i in range(5)]
        raw_path.write_text(json.dumps({"games": [{"url": u, "pgn": str(game)} for u in urls]}))
        rows = pd.DataFrame([{
            "GameUrl": u, "corte_ply": 20, "reloj_blancas_seg": 162, "reloj_negras_seg": 161,
            "TimeClass": "blitz", "tiempo_base_seg": 180, "incremento_seg": 0, "EsTorneo": False,
            "StartTime": pd.Timestamp("2026-08-01", tz="UTC"), "historial_blancas": (), "historial_negras": (),
        } for u in urls])
        pred = pd.DataFrame([{"GameUrl": u, "corte_ply": 20, "p_blancas": .5 if wrong_probability else .6,
                              "p_empate": .1, "p_negras": .3} for u in urls])
        games = pd.DataFrame([{"GameUrl": u, "White": "w", "Black": "b", "EndTime": pd.Timestamp("2026-08-01", tz="UTC"),
                               "resultado": "Gana Negras" if invert_results else "Gana Blancas", "Termination": "resignation"} for u in urls])
        columns = ["elo_blancas_previo", "elo_negras_previo"]
        transformer = PlayerHistoryTransformer(columns).fit(pd.DataFrame(columns=columns))
        artifact = {"resultado": SimpleNamespace(named_steps={"historial": transformer}), "columnas": columns}
        curve = pd.DataFrame({"ply": range(24), "Gana Blancas": .6, "Empate": .1, "Gana Negras": .3})
        with patch("src.app_trivia.predecir", return_value=curve):
            return construir_trivia(rows, pred, games, {"w": raw_path}, artifact, 42, limit=3)

    def test_sampling_is_reproducible_and_independent_of_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            index, first = self.build(directory)
            _, again = self.build(directory, invert_results=True)
        self.assertEqual(index["partidas_inspeccionadas"], 3)
        self.assertEqual([c["analisis"]["partida"]["url"] for c in first],
                         [c["analisis"]["partida"]["url"] for c in again])
        self.assertEqual([c["ply"] for c in first], [c["ply"] for c in again])
        self.assertTrue(all(c["analisis"]["contexto"]["elo_blancas_previo"] is None for c in first))

    def test_build_rejects_probability_mismatch(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(AssertionError):
            self.build(directory, wrong_probability=True)


@unittest.skipUnless((ROOT / "index.json").exists(), "Generar el banco con python -m src.build_app")
class PublishedTriviaTest(unittest.TestCase):
    def test_bank_positions_clocks_and_probabilities(self):
        index = json.loads((ROOT / "index.json").read_text())
        self.assertGreaterEqual(len(index["casos"]), 3)
        self.assertLessEqual(len(index["casos"]), 60)
        urls = set()
        for id_ in index["casos"]:
            case = json.loads((ROOT / f"{id_}.json").read_text())
            analysis, cut = case["analisis"], case["ply"]
            url = analysis["partida"]["url"]
            self.assertNotIn(url, urls)
            urls.add(url)
            self.assertIn(cut, [20, 40, 60])
            self.assertLess(cut, len(analysis["jugadas"]))
            board = chess.Board()
            for move in analysis["jugadas"][:cut]:
                board.push_san(move)
            self.assertEqual(board.fen(), case["fen"])
            self.assertFalse(board.is_game_over())
            self.assertIsNotNone(analysis["relojes_seg"][cut - 1])
            self.assertIsNotNone(analysis["relojes_seg"][cut - 2])
            for point in analysis["curva"]:
                self.assertLessEqual(point["ply"], 120)
                p = [point[c] for c in ["gana_blancas", "empate", "gana_negras"]]
                self.assertTrue(all(0 <= x <= 1 for x in p))
                np.testing.assert_allclose(sum(p), 1, atol=1e-9)
