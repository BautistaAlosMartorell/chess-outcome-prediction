"""Pruebas unitarias del pipeline de Chess.com sin acceso de red."""

from __future__ import annotations

import unittest

import pandas as pd

from src.clean_data import DataCleaner
from src.download_data import DataDownloader
from src.feature_engineering import FeatureEngineer
from src.utils import load_config


class ChessPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config("config/config.yaml")

    def test_downloader_filters_project_scope(self) -> None:
        downloader = DataDownloader(self.config)
        valid = {"rules": "chess", "time_class": "blitz", "rated": True}
        self.assertTrue(downloader._is_eligible(valid))
        self.assertFalse(downloader._is_eligible({**valid, "rules": "chess960"}))
        self.assertFalse(downloader._is_eligible({**valid, "time_class": "daily"}))
        self.assertFalse(downloader._is_eligible({**valid, "rated": False}))

    def test_parser_handles_chess_com_move_numbers_and_opening(self) -> None:
        game = {
            "url": "https://www.chess.com/game/live/1",
            "rules": "chess",
            "time_class": "blitz",
            "time_control": "180+2",
            "rated": True,
            "eco": "https://www.chess.com/openings/Sicilian-Defense-Bowdler-Attack...3.Bc4",
            "white": {"username": "White", "rating": 1500},
            "black": {"username": "Black", "rating": 1520},
            "pgn": (
                '[Event "Live Chess"]\n[Date "2026.08.24"]\n[White "White"]\n'
                '[Black "Black"]\n[Result "1-0"]\n[WhiteElo "1500"]\n'
                '[BlackElo "1520"]\n[ECO "B20"]\n[TimeControl "180+2"]\n\n'
                '1. e4 {[%clk 0:03:00]} 1... c5 2. Bc4 2... Nc6 1-0'
            ),
        }
        cleaner = DataCleaner(self.config)
        row = cleaner.parse_game(game)
        self.assertIsNotNone(row)
        self.assertEqual(row["Opening"], "Sicilian Defense Bowdler Attack")

        df = pd.DataFrame([row])
        df = cleaner.parse_result(df)
        df = cleaner.parse_numeric_fields(df)
        df = cleaner.count_moves(df)
        self.assertEqual(int(df.loc[0, "cantidad_jugadas"]), 4)
        self.assertEqual(int(df.loc[0, "incremento_seg"]), 2)

    def test_time_class_maps_to_modality(self) -> None:
        df = pd.DataFrame({"TimeClass": ["bullet", "blitz", "rapid"]})
        transformed = FeatureEngineer(self.config).add_time_control_category(df)
        self.assertEqual(transformed["modalidad"].astype("string").tolist(), ["Bullet", "Blitz", "Rapid"])


if __name__ == "__main__":
    unittest.main()
