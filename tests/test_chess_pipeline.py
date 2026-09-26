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
from src.feature_engineering import FeatureEngineer, matchup_history
from src.pipeline import build_summary
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
        self.assertEqual(self.config["quality"]["min_final_games"], 1500)

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
            usernames = ["good1", "good2", "bad"]
            cfg["paths"]["raw_dir"] = tmp
            cfg["download"]["min_users_ok"] = 2
            cfg["download"]["min_total_games"] = 4

            with mock.patch.object(DataDownloader, "download_user_games", fake_download_user_games):
                # 'bad' se saltea, los otros dos quedan y se superan los mínimos
                results = DataDownloader(cfg).download_all(usernames)
                self.assertEqual(set(results), {"good1", "good2"})

                # mínimo de partidas inalcanzable -> corta con RuntimeError
                cfg["download"]["min_total_games"] = 999
                with self.assertRaises(RuntimeError):
                    DataDownloader(cfg).download_all(usernames)

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

    def test_parse_game_keeps_tournament_and_utc_times(self) -> None:
        cleaner = DataCleaner(self.config)
        game = self._minimal_game("https://www.chess.com/game/live/7")
        game["pgn"] = game["pgn"].replace(
            '[Event "Live Chess"]\n', '[Event "Live Chess"]\n[UTCDate "2026.08.24"]\n[UTCTime "23:58:30"]\n'
        )
        game["end_time"] = 1787616090  # 2026-08-25 00:01:30 UTC: cruza la medianoche
        with_tournament = {**game, "tournament": "https://api.chess.com/pub/tournament/arena-123"}

        row = cleaner.parse_game(game)
        self.assertIsNone(row["TournamentUrl"])
        self.assertEqual(row["StartTime"], "2026.08.24 23:58:30")
        self.assertEqual(cleaner.parse_game(with_tournament)["TournamentUrl"], with_tournament["tournament"])

        df = cleaner.parse_timestamps(pd.DataFrame([row, cleaner.parse_game(with_tournament)]))
        self.assertEqual(df["StartTime"].iloc[0], pd.Timestamp("2026-08-24 23:58:30", tz="UTC"))
        self.assertEqual(df["EndTime"].iloc[0], pd.Timestamp("2026-08-25 00:01:30", tz="UTC"))
        self.assertEqual(df["EsTorneo"].tolist(), [False, True])

    def test_clean_keeps_games_without_utc_times(self) -> None:
        # _minimal_game has no UTCDate/UTCTime/end_time: the game stays, with NaT.
        cleaner = DataCleaner(self.config)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps({"games": [self._minimal_game("https://www.chess.com/game/live/8")]}))
            df, _ = cleaner.clean({"a": path})
        df = cleaner.optimize_dtypes(df)
        self.assertEqual(len(df), 1)
        self.assertTrue(pd.isna(df["StartTime"].iloc[0]) and pd.isna(df["EndTime"].iloc[0]))
        self.assertFalse(df["EsTorneo"].iloc[0])
        self.assertEqual(df["EsTorneo"].dtype, bool)

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

    def test_summary_includes_all_opening_family_counts(self) -> None:
        df = pd.DataFrame(
            {
                "resultado": ["Gana Blancas", "Empate", "Gana Negras"],
                "TimeClass": ["blitz", "blitz", "rapid"],
                "nivel_promedio": ["avanzado", "avanzado", "experto"],
                "familia_apertura": ["Abierta", "Abierta", "Desconocida"],
                "es_sorpresa": [0, 1, 0],
                "cantidad_jugadas": [20, 30, 40],
                "Termination": ["resignation", "otro", "checkmate"],
                "EsTorneo": [True, False, False],
                "historial_suficiente": [True, True, False],
            }
        )

        summary = build_summary(df, raw_row_count=3)

        self.assertEqual(summary["distribucion_time_class"], {"blitz": 2, "rapid": 1})
        self.assertEqual(summary["partidas_de_torneo"], 1)

        self.assertEqual(
            summary["distribucion_familia_apertura"],
            {
                "Flanco": 0,
                "Semiabierta": 0,
                "Abierta": 2,
                "Cerrada": 0,
                "India": 0,
                "Desconocida": 1,
            },
        )

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

    def test_transform_does_not_duplicate_time_class_or_elo_sign(self) -> None:
        df = pd.DataFrame(
            {
                "WhiteElo": [1400, 1600, 1500],
                "BlackElo": [1500, 1500, 1500],
                "TimeClass": ["bullet", "blitz", "rapid"],
                "resultado": ["Gana Blancas", "Gana Negras", "Empate"],
                "ECO": ["B20", "C50", "D00"],
                "moves_text": ["1. e4 1... e5 2. Nf3", "1. d4 1... d5 2. c4", "1. e4 1... e5 2. Bc4"],
                "StartTime": pd.to_datetime(["2026-08-01 10:00", "2026-08-01 10:00", "2026-08-01 11:00"], utc=True),
                "EndTime": pd.to_datetime(["2026-08-01 10:05", "2026-08-01 10:05", "2026-08-01 11:05"], utc=True),
            }
        )
        transformed = FeatureEngineer(self.config).transform(df)

        self.assertNotIn("modalidad", transformed.columns)
        self.assertNotIn("favorito", transformed.columns)
        self.assertEqual(transformed["es_sorpresa"].tolist(), [1, 1, 0])

    def test_opening_matchup_uses_first_two_plies_and_groups_the_rest(self) -> None:
        engineer = FeatureEngineer(self.config)
        df = pd.DataFrame({"moves_text": ["1. e4 1... e5 2. Nf3 2... Nc6", "1. d4 1... Nf6 2. c4", "1. b3 1... e5 2. Bb2"]})
        df = engineer.add_opening_matchup(df)
        self.assertEqual(df["matchup_apertura"].astype(str).tolist(), ["e4-e5", "d4-Nf6", "otra"])
        self.assertEqual(len(df["matchup_apertura"].cat.categories), 18)  # 17 congeladas + "otra"

    @staticmethod
    def _history_games() -> pd.DataFrame:
        # Same matchup and TimeClass, overlapping in time, plus one game of another
        # matchup that must never be counted in the e4-e5 history.
        rows = [
            ("e4-e5", "10:00", "10:05", "Gana Blancas"),  # g0
            ("e4-e5", "10:01", "10:10", "Gana Negras"),   # g1: g0 still running when g1 starts
            ("e4-e5", "10:05", "10:20", "Empate"),        # g2: g0 ends exactly at g2's start -> not prior
            ("e4-e5", "10:11", "10:30", "Gana Blancas"),  # g3: prior = g0, g1
            ("e4-e5", "10:21", "10:40", "Gana Negras"),   # g4: prior = g0, g1, g2
            ("d4-d5", "09:00", "09:05", "Gana Blancas"),  # other matchup
        ]
        return pd.DataFrame(
            {
                "matchup_apertura": [r[0] for r in rows],
                "TimeClass": "blitz",
                "StartTime": pd.to_datetime([f"2026-08-01 {r[1]}" for r in rows], utc=True),
                "EndTime": pd.to_datetime([f"2026-08-01 {r[2]}" for r in rows], utc=True),
                "resultado": [r[3] for r in rows],
            }
        )

    def test_matchup_history_counts_only_games_finished_before_start(self) -> None:
        history = matchup_history(self._history_games(), min_prev=2)
        self.assertEqual(history["n_previas_matchup"].tolist(), [0, 0, 0, 2, 3, 0])
        self.assertEqual(history["historial_suficiente"].tolist(), [False, False, False, True, True, False])
        rates = history[["tasa_blancas_hist", "tasa_tablas_hist", "tasa_negras_hist"]]
        self.assertTrue(rates.iloc[[0, 1, 2, 5]].isna().all().all())  # insufficient history -> NaN, not imputed
        self.assertEqual(rates.iloc[3].tolist(), [0.5, 0.0, 0.5])
        for value in rates.iloc[4].tolist():
            self.assertAlmostEqual(value, 1 / 3)
        self.assertTrue(((rates.dropna().sum(axis=1) - 1).abs() < 1e-12).all())

    def test_matchup_history_is_invariant_to_row_order_and_future_games(self) -> None:
        games = self._history_games()
        base = matchup_history(games, min_prev=2)
        shuffled = games.sample(frac=1, random_state=0)
        pd.testing.assert_frame_equal(matchup_history(shuffled, min_prev=2).loc[games.index], base)
        # A game that starts after everything else can't change any earlier feature.
        later = pd.concat([games, games.iloc[[0]].assign(
            StartTime=pd.Timestamp("2026-08-01 12:00", tz="UTC"), EndTime=pd.Timestamp("2026-08-01 12:05", tz="UTC")
        )], ignore_index=True)
        pd.testing.assert_frame_equal(matchup_history(later, min_prev=2).iloc[: len(games)], base)

    def test_matchup_history_shrinkage_uses_only_prior_games(self) -> None:
        history = matchup_history(self._history_games(), min_prev=2, shrink_m=1)
        # g3: matchup prior (1 W, 1 B of 2); TimeClass prior = d4-d5 W, g0 W, g1 B -> p_W = 2/3.
        self.assertAlmostEqual(history["tasa_blancas_hist"].iloc[3], (1 + 2 / 3) / (2 + 1))
        # The first game of the TimeClass has no prior at all: still NaN, never imputed.
        self.assertTrue(pd.isna(history["tasa_blancas_hist"].iloc[5]))

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
