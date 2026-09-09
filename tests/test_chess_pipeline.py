"""Pruebas unitarias del pipeline de Chess.com sin acceso de red."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import requests

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

    def test_downloader_respects_frozen_month_window(self) -> None:
        downloader = DataDownloader(self.config)
        base = "https://api.chess.com/pub/player/erik/games"
        self.assertEqual(downloader.until_month, (2026, 8))
        self.assertTrue(downloader._archive_in_window(f"{base}/2026/08"))
        self.assertTrue(downloader._archive_in_window(f"{base}/2025/12"))
        self.assertFalse(downloader._archive_in_window(f"{base}/2026/09"))
        self.assertFalse(downloader._archive_in_window(f"{base}/2027/01"))
        # until_month = None desactiva el tope
        no_cap = {**self.config, "download": {**self.config["download"], "until_month": None}}
        self.assertTrue(DataDownloader(no_cap)._archive_in_window(f"{base}/2030/01"))

    def test_config_declares_explicit_final_volume_minimum(self) -> None:
        self.assertEqual(self.config["quality"]["min_final_games"], 4000)

    def test_download_all_tolerates_failed_user_and_enforces_minimums(self) -> None:
        def fake_download_user_games(self, username, dest_path):
            if username == "bad":
                raise requests.HTTPError("404 Client Error: Not Found")
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps({"games": [{"pgn": "x"}, {"pgn": "y"}, {"pgn": "z"}]}))
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(self.config)
            cfg["chess_com"]["usernames"] = ["good1", "good2", "bad"]
            cfg["paths"]["raw_dir"] = tmp
            cfg["download"]["min_users_ok"] = 2
            cfg["download"]["min_total_games"] = 4

            with mock.patch.object(DataDownloader, "download_user_games", fake_download_user_games):
                # 'bad' se saltea, los otros dos quedan y se superan los mínimos
                results = DataDownloader(cfg).download_all()
                self.assertEqual(set(results), {"good1", "good2"})

                # mínimo de partidas inalcanzable -> corta con RuntimeError
                cfg["download"]["min_total_games"] = 999
                with self.assertRaises(RuntimeError):
                    DataDownloader(cfg).download_all()

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

    @staticmethod
    def _minimal_game(url: str, result: str = "1-0", *, eco_header: bool = True, pgn: str | None = None) -> dict:
        headers = (
            f'[Event "Live Chess"]\n[Date "2026.08.24"]\n[White "W"]\n[Black "B"]\n'
            f'[Result "{result}"]\n[WhiteElo "1500"]\n[BlackElo "1500"]\n'
            f'[TimeControl "180"]\n[Termination "W won by resignation"]\n'
        )
        if eco_header:
            headers += '[ECO "B20"]\n'
        body = '\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6\n'
        return {
            "url": url,
            "rules": "chess",
            "time_class": "blitz",
            "time_control": "180",
            "rated": True,
            "white": {"username": "W", "rating": 1500},
            "black": {"username": "B", "rating": 1500},
            "pgn": pgn if pgn is not None else headers + body,
        }

    def test_parse_result_maps_draw(self) -> None:
        cleaner = DataCleaner(self.config)
        df = pd.DataFrame({"Result": ["1-0", "0-1", "1/2-1/2"]})
        df = cleaner.parse_result(df)
        self.assertEqual(df["resultado"].tolist(), ["Gana Blancas", "Gana Negras", "Empate"])

    def test_parse_game_drops_missing_or_empty_pgn(self) -> None:
        cleaner = DataCleaner(self.config)
        self.assertIsNone(cleaner.parse_game({"url": "x"}))  # sin pgn
        self.assertIsNone(cleaner.parse_game({"url": "x", "pgn": None}))
        self.assertIsNone(cleaner.parse_game({"url": "x", "pgn": "sin headers"}))

    def test_opening_family_unknown_when_eco_missing(self) -> None:
        engineer = FeatureEngineer(self.config)
        df = pd.DataFrame({"ECO": ["B20", None, pd.NA]})
        df = engineer.add_opening_family(df)
        self.assertEqual(df["familia_apertura"].astype("string").tolist(), ["Semiabierta", "Desconocida", "Desconocida"])

    def test_parse_all_deduplicates_shared_game(self) -> None:
        cleaner = DataCleaner(self.config)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shared = self._minimal_game("https://www.chess.com/game/live/999")
            only_a = self._minimal_game("https://www.chess.com/game/live/111")
            (tmp_path / "a.json").write_text(json.dumps({"games": [shared, only_a]}))
            (tmp_path / "b.json").write_text(json.dumps({"games": [shared]}))
            combined, raw_count = cleaner.parse_all({"a": tmp_path / "a.json", "b": tmp_path / "b.json"})
        self.assertEqual(raw_count, 3)          # 3 filas parseadas
        self.assertEqual(len(combined), 2)      # 1 duplicada eliminada
        self.assertTrue(combined["GameUrl"].is_unique)

    def test_upset_flag_zero_when_elos_equal(self) -> None:
        engineer = FeatureEngineer(self.config)
        df = pd.DataFrame(
            {
                "resultado": ["Gana Blancas", "Gana Negras", "Empate"],
                "diferencia_elo": [0, 0, 0],
            }
        )
        df = engineer.add_upset_flag(df)
        self.assertEqual(df["es_sorpresa"].tolist(), [0, 0, 0])

    def test_time_class_maps_to_modality(self) -> None:
        df = pd.DataFrame({"TimeClass": ["bullet", "blitz", "rapid"]})
        transformed = FeatureEngineer(self.config).add_time_control_category(df)
        self.assertEqual(transformed["modalidad"].astype("string").tolist(), ["Bullet", "Blitz", "Rapid"])

    def test_termination_reason_strips_username(self) -> None:
        cleaner = DataCleaner(self.config)
        self.assertEqual(cleaner._termination_reason("erik won by resignation"), "resignation")
        self.assertEqual(cleaner._termination_reason("RebeccaHarris won - game abandoned"), "abandoned")
        self.assertEqual(cleaner._termination_reason("x won by abandonment"), "abandoned")
        self.assertEqual(cleaner._termination_reason("Game drawn by agreement"), "agreement")
        self.assertEqual(cleaner._termination_reason("Game drawn by 50-move rule"), "50-move_rule")
        self.assertIsNone(cleaner._termination_reason(None))

    def test_termination_reason_anchors_and_splits_timeout_draw(self) -> None:
        cleaner = DataCleaner(self.config)
        # un username que contiene "time" no debe leerse como motivo "time"
        self.assertEqual(cleaner._termination_reason("Timmy won by resignation"), "resignation")
        self.assertEqual(cleaner._termination_reason("SirTime won on time"), "time")
        # tablas por bandera con material insuficiente: categoría propia, no "time"
        self.assertEqual(
            cleaner._termination_reason("Game drawn by timeout vs insufficient material"),
            "timeout_vs_insufficient_material",
        )
        self.assertEqual(cleaner._termination_reason("frase rara sin patron"), "otro")

    def test_filter_invalid_rows_drops_short_abandons(self) -> None:
        cleaner = DataCleaner(self.config)
        df = pd.DataFrame(
            {
                "resultado": ["Gana Blancas", "Gana Blancas"],
                "WhiteElo": [1500, 1500],
                "BlackElo": [1500, 1500],
                "Date": pd.to_datetime(["2026-08-01", "2026-08-01"]),
                "Variant": ["Standard", "Standard"],
                "TimeClass": ["blitz", "blitz"],
                "Rated": [True, True],
                "cantidad_jugadas": [1, 40],
            }
        )
        filtered = cleaner.filter_invalid_rows(df)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered["cantidad_jugadas"].iloc[0], 40)

    def test_clean_drops_rows_with_unparseable_date(self) -> None:
        cleaner = DataCleaner(self.config)
        df = pd.DataFrame(
            {
                "resultado": ["Gana Blancas", "Gana Negras"],
                "WhiteElo": [1500, 1500],
                "BlackElo": [1500, 1500],
                "Date": ["2026.08.22", "????.??.??"],
                "Variant": ["Standard", "Standard"],
                "TimeClass": ["blitz", "blitz"],
                "Rated": [True, True],
                "cantidad_jugadas": [40, 40],
            }
        )
        df = cleaner.parse_date(df)
        self.assertEqual(int(df["Date"].isna().sum()), 1)
        filtered = cleaner.filter_invalid_rows(df)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered["Date"].iloc[0], pd.Timestamp("2026-08-22"))


if __name__ == "__main__":
    unittest.main()
