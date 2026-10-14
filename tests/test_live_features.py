"""Pruebas del dataset de predicción en vivo y del rating previo (sin acceso de red)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.live_features import build_cut_dataset, game_cut_features
from src.rating_history import add_prior_ratings, reconstruct_prior_ratings

HEADERS = '[Event "Live Chess"]\n[White "W"]\n[Black "B"]\n[Result "1-0"]\n[TimeControl "180+2"]\n\n'

# Italian game with clocks: both sides castle, white checks on ply 13 and wins the queen later.
MOVES = [
    ("e4", 180.0), ("e5", 179.0), ("Nf3", 178.0), ("Nc6", 177.5), ("Bc4", 176.0), ("Bc5", 175.0),
    ("O-O", 174.0), ("Nf6", 172.0), ("d3", 170.0), ("O-O", 168.0), ("Bg5", 165.0), ("h6", 160.0),
    ("Bxf7+", 150.0), ("Rxf7", 150.0), ("Bxf6", 140.0), ("Qxf6", 149.0), ("Nc3", 130.0), ("d6", 147.0),
    ("Nd5", 120.0), ("Qd8", 140.0), ("c3", 110.0), ("Be6", 139.0),
]


def _pgn(moves: list[tuple[str, float]]) -> str:
    tokens = []
    for i, (san, clock) in enumerate(moves):
        h, rest = divmod(clock, 3600)
        m, s = divmod(rest, 60)
        clk = f"{{[%clk {int(h)}:{int(m):02d}:{s:04.1f}]}}"
        prefix = f"{i // 2 + 1}. " if i % 2 == 0 else f"{i // 2 + 1}... "
        tokens.append(f"{prefix}{san} {clk}")
    return HEADERS + " ".join(tokens) + " 1-0"


class LiveFeaturesTest(unittest.TestCase):
    def test_cut_features_describe_the_position_at_the_cut(self) -> None:
        rows, plies = game_cut_features(_pgn(MOVES), [10, 20], base_seconds=180, increment_seconds=2)
        self.assertEqual(plies, 22)
        at10, at20 = rows
        self.assertEqual(at10["corte_ply"], 10)
        self.assertTrue(at10["turno_blancas"])
        self.assertTrue(at10["enroco_blancas"] and at10["enroco_negras"])
        self.assertFalse(at10["derechos_enroque_blancas"])
        self.assertEqual((at10["material_blancas"], at10["material_negras"]), (39, 39))
        self.assertEqual(at10["reloj_blancas_seg"], 170.0)
        self.assertEqual(at10["reloj_negras_seg"], 168.0)
        # White's last 5 own moves: clock 180 -> 170 plus 5 increments of 2 s.
        self.assertEqual(at10["gasto_reciente_blancas_seg"], 180 - 170 + 5 * 2)
        # By ply 20: Bxf7+ (check), Rxf7, Bxf6, Qxf6 -> two white captures, one black... plus Rxf7.
        self.assertEqual(at20["jaques_blancas"], 1)
        self.assertEqual(at20["capturas_blancas"], 2)
        self.assertEqual(at20["capturas_negras"], 2)
        self.assertEqual(at20["balance_material"], 39 - 3 - 3 - (39 - 1 - 3))

    def test_features_ignore_everything_after_the_cut(self) -> None:
        # Same first 10 plies, completely different continuation: identical cut-10 row.
        other_future = MOVES[:10] + [("h3", 160.0), ("a6", 150.0), ("a3", 150.0), ("Ba7", 140.0)]
        full, _ = game_cut_features(_pgn(MOVES), [10], 180, 2)
        truncated, _ = game_cut_features(_pgn(other_future), [10], 180, 2)
        self.assertEqual(full, truncated)

    def test_no_row_when_the_game_ends_at_or_before_the_cut(self) -> None:
        rows, plies = game_cut_features(_pgn(MOVES[:10]), [10, 20], 180, 2)
        self.assertEqual(plies, 10)
        self.assertEqual(rows, [])  # at ply 10 the game is already over

    def test_missing_clocks_stay_missing(self) -> None:
        pgn = _pgn(MOVES).replace("{[%clk 0:02:50.0]}", "")  # drop one clock (ply 9)
        rows, _ = game_cut_features(pgn, [10], 180, 2)
        self.assertIsNone(rows[0]["reloj_blancas_seg"])
        self.assertIsNone(rows[0]["diferencia_reloj_seg"])

    def _raw_file(self, tmp: Path, games: list[dict]) -> Path:
        path = tmp / "a.json"
        path.write_text(json.dumps({"games": games}))
        return path

    def test_build_cut_dataset_keys_targets_and_validation(self) -> None:
        clean = pd.DataFrame(
            {
                "GameUrl": ["g1"],
                "tiempo_base_seg": [180],
                "incremento_seg": [2],
                "cantidad_jugadas": [22],
                "resultado": ["Gana Blancas"],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._raw_file(Path(tmp), [{"url": "g1", "pgn": _pgn(MOVES)}, {"url": "g1", "pgn": _pgn(MOVES)}])
            cut = build_cut_dataset(clean, [path], [10, 20, 30])
            self.assertEqual(cut["corte_ply"].tolist(), [10, 20])  # ply 30 not reached; duplicate PGN ignored
            self.assertEqual(cut["plies_restantes"].tolist(), [12, 2])
            self.assertEqual(cut["resultado"].unique().tolist(), ["Gana Blancas"])

            with self.assertRaises(ValueError):  # replayed plies must equal cantidad_jugadas
                build_cut_dataset(clean.assign(cantidad_jugadas=23), [path], [10])
            with self.assertRaises(ValueError):  # every clean game needs its raw PGN
                build_cut_dataset(pd.concat([clean, clean.assign(GameUrl="g2")]), [path], [10])


class RatingHistoryTest(unittest.TestCase):
    @staticmethod
    def _game(url: str, end: int, white: tuple[str, int], black: tuple[str, int], tc: str = "blitz") -> dict:
        return {
            "url": url,
            "end_time": end,
            "time_class": tc,
            "white": {"username": white[0], "rating": white[1]},
            "black": {"username": black[0], "rating": black[1]},
        }

    def test_prior_rating_is_the_rating_after_the_previous_own_game(self) -> None:
        alice_games = [
            self._game("g1", 100, ("Alice", 1510), ("x", 1400)),
            self._game("g2", 200, ("y", 1600), ("Alice", 1502)),
            self._game("g3", 300, ("Alice", 1520), ("Bob", 1490)),
            self._game("r1", 250, ("Alice", 1300), ("z", 1300), tc="rapid"),  # other time class
        ]
        bob_games = [
            self._game("b0", 150, ("Bob", 1480), ("w", 1500)),
            self._game("g3", 300, ("Alice", 1520), ("Bob", 1490)),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "alice.json").write_text(json.dumps({"games": alice_games}))
            (tmp / "bob.json").write_text(json.dumps({"games": bob_games}))
            prior = reconstruct_prior_ratings({"alice": tmp / "alice.json", "bob": tmp / "bob.json"})

        prior = prior.set_index("GameUrl")
        self.assertEqual(prior.loc["g2", "elo_negras_previo"], 1510)   # Alice after g1
        self.assertTrue(pd.isna(prior.loc["g2", "elo_blancas_previo"]))  # opponent: no history
        self.assertEqual(prior.loc["g3", "elo_blancas_previo"], 1502)  # Alice after g2, not after r1 (rapid)
        self.assertEqual(prior.loc["g3", "elo_negras_previo"], 1480)   # Bob from his own file
        self.assertNotIn("g1", prior.index)                            # first own game: nothing before

        df = pd.DataFrame({"GameUrl": ["g1", "g2", "g3"]})
        merged = add_prior_ratings(df, prior.reset_index())
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged.set_index("GameUrl").loc["g3", "diferencia_elo_previo"], 1502 - 1480)


if __name__ == "__main__":
    unittest.main()
