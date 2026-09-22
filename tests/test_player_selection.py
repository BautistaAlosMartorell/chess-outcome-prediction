"""Pruebas offline del selector de jugadores (tarea listar_jugadores del DAG)."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from src.player_selection import (
    PUBAPI_ROOT,
    Candidate,
    CandidateValidation,
    InsufficientSelectionError,
    PlayerSelector,
    _band_for_elo,
    load_or_create_selection,
    load_selection,
)
from src.utils import load_config


class PlayerSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_config = load_config("config/config.yaml")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def config_for_test(self, targets: dict[str, int] | None = None) -> dict:
        config = copy.deepcopy(self.base_config)
        config["download"]["request_delay_seconds"] = 0
        config["download"]["min_users_ok"] = 1
        config["player_selection"]["min_eligible_games"] = 2
        config["player_selection"]["max_games_per_candidate"] = 3
        config["player_selection"]["countries"] = ["AR"]
        config["player_selection"]["titles"] = ["GM"]
        config["player_selection"]["selection_path"] = str(self.tmp / "seleccion" / "sel.yaml")
        if targets is not None:
            config["player_selection"]["target_per_band"] = targets
        return config

    # -- Helpers de payloads falsos -----------------------------------------

    @staticmethod
    def game(username: str, rating: int, *, rated: bool = True) -> dict:
        return {
            "rules": "chess",
            "time_class": "blitz",
            "rated": rated,
            "white": {"username": username, "rating": rating},
            "black": {"username": "rival", "rating": rating + 5},
        }

    def player_payloads(self, username: str, *, status: str = "basic", ratings=(1500, 1550)) -> dict:
        base = self.base_config["chess_com"]["base_url"]
        archive = f"{base}/{username.lower()}/games/2026/08"
        return {
            f"{base}/{username.lower()}": {"username": username, "status": status},
            f"{base}/{username.lower()}/games/archives": {"archives": [archive]},
            archive: {"games": [self.game(username, rating) for rating in ratings]},
            f"{base}/{username.lower()}/stats": {
                "chess_blitz": {
                    "last": {"rating": ratings[0]},
                    "record": {"win": len(ratings), "loss": 0, "draw": 0},
                },
            },
        }

    def fake_api(self, players: dict[str, tuple[int, ...]], *, titled: tuple[str, ...] = ()):
        """Return (api_get, calls): a PubAPI stub over ``players`` and the URLs requested."""
        payloads = {
            f"{PUBAPI_ROOT}/country/AR/players": {"players": sorted(players)},
            f"{PUBAPI_ROOT}/titled/GM": {"players": list(titled)},
        }
        for username, ratings in players.items():
            payloads.update(self.player_payloads(username, ratings=ratings))
        calls: list[str] = []

        def api_get(url: str) -> dict:
            calls.append(url)
            return payloads[url]

        return api_get, calls

    def selector(self, config: dict, api_get) -> PlayerSelector:
        return PlayerSelector(config, api_get=api_get, sleep=lambda _: None)

    # -- Bandas y validación --------------------------------------------------

    def test_band_boundaries_are_lower_inclusive_and_upper_exclusive(self) -> None:
        bands = self.base_config["elo"]["bandas"]
        targets = set(bands)
        self.assertEqual(_band_for_elo(1200, bands, targets), "intermedio")
        self.assertEqual(_band_for_elo(1799.9, bands, targets), "intermedio")
        self.assertEqual(_band_for_elo(1800, bands, targets), "avanzado")
        self.assertIsNone(_band_for_elo(1500, bands, {"avanzado"}))

    def test_validate_candidate_accepts_active_account_with_enough_games(self) -> None:
        candidate = Candidate("Active", "intermedio", 1510.0, "pais:AR")
        payloads = self.player_payloads(candidate.username, ratings=(1490, 1510, 1530))
        result = self.selector(self.config_for_test(), payloads.__getitem__).validate_candidate(candidate)

        self.assertTrue(result.accepted)
        self.assertEqual(result.eligible_games, 3)
        self.assertEqual(result.validated_median_elo, 1510.0)

    def test_validate_candidate_rejects_closed_and_fair_play_accounts(self) -> None:
        candidate = Candidate("Closed", "intermedio", 1500.0, "pais:AR")
        for status in ("closed", "closed:fair_play_violations"):
            with self.subTest(status=status):
                payloads = self.player_payloads(candidate.username, status=status)
                result = self.selector(self.config_for_test(), payloads.__getitem__).validate_candidate(candidate)
                self.assertFalse(result.accepted)
                self.assertTrue(result.reason.startswith("cuenta_no_activa:"))

    def test_validate_candidate_rejects_low_activity_and_changed_band(self) -> None:
        candidate = Candidate("Candidate", "intermedio", 1500.0, "pais:AR")
        cases = [
            ((1500,), "partidas_elegibles_insuficientes"),
            ((1850, 1900), "elo_validado_fuera_de_banda:avanzado"),
        ]
        for ratings, reason in cases:
            with self.subTest(reason=reason):
                payloads = self.player_payloads(candidate.username, ratings=ratings)
                result = self.selector(self.config_for_test(), payloads.__getitem__).validate_candidate(candidate)
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, reason)

    def test_estimate_elo_uses_time_class_with_most_games(self) -> None:
        base = self.base_config["chess_com"]["base_url"]
        stats = {
            "chess_daily": {"last": {"rating": 2500}, "record": {"win": 999}},
            "chess_bullet": {"last": {"rating": 900}, "record": {"win": 10, "loss": 5}},
            "chess_blitz": {"last": {"rating": 1300}, "record": {"win": 40, "loss": 40, "draw": 1}},
        }
        selector = self.selector(self.config_for_test(), {f"{base}/x/stats": stats}.__getitem__)
        self.assertEqual(selector.estimate_elo("x"), 1300.0)

        empty = self.selector(self.config_for_test(), {f"{base}/x/stats": {}}.__getitem__)
        self.assertIsNone(empty.estimate_elo("x"))

    # -- Selección --------------------------------------------------------------

    @staticmethod
    def accept(candidate: Candidate) -> CandidateValidation:
        return CandidateValidation(
            username=candidate.username,
            band=candidate.band,
            accepted=True,
            reason="aceptado",
            estimated_elo=candidate.estimated_elo,
            source=candidate.source,
            eligible_games=500,
            validated_median_elo=candidate.estimated_elo,
        )

    def test_selection_is_deterministic_with_fixed_seed(self) -> None:
        players = {f"player{index}": (1300 + index, 1300 + index) for index in range(12)}
        config = self.config_for_test({"intermedio": 3})
        results = []
        for _ in range(2):
            api_get, _ = self.fake_api(players)
            selector = self.selector(config, api_get)
            with mock.patch.object(selector, "validate_candidate", side_effect=self.accept):
                results.append(selector.select(selector.fetch_candidate_pool()))
            # Drop cached snapshots so the second run fetches the pool again.
            for snapshot in (self.tmp / "seleccion").glob("*.json"):
                snapshot.unlink()

        self.assertEqual(results[0].selected, results[1].selected)
        self.assertEqual(len(results[0].selected["intermedio"]), 3)

    def test_pool_merges_country_and_titled_sources_without_duplicates(self) -> None:
        api_get, _ = self.fake_api({"alice": (1500, 1500), "bob": (2700, 2700)}, titled=("Bob", "carl"))
        pool = self.selector(self.config_for_test(), api_get).fetch_candidate_pool()

        self.assertEqual(len(pool), 3)
        self.assertEqual(pool["bob"], "pais:AR,titulo:GM")
        self.assertTrue((self.tmp / "seleccion" / "country_AR.json").exists())

    def test_full_band_is_skipped_before_validation(self) -> None:
        players = {f"low{index}": (1300, 1300) for index in range(5)}
        players["high"] = (1900, 1900)
        api_get, _ = self.fake_api(players)
        selector = self.selector(self.config_for_test({"intermedio": 1, "avanzado": 1}), api_get)

        with mock.patch.object(selector, "validate_candidate", side_effect=self.accept) as validate:
            result = selector.select(selector.fetch_candidate_pool())

        self.assertTrue(result.is_complete)
        self.assertEqual(result.selected["avanzado"], ["high"])
        validated = [call.args[0].username for call in validate.call_args_list]
        self.assertEqual(sum(name.startswith("low") for name in validated), 1)

    def test_incomplete_band_is_tolerated(self) -> None:
        api_get, _ = self.fake_api({"only": (1300, 1300)})
        selector = self.selector(self.config_for_test({"intermedio": 5}), api_get)

        with self.assertLogs("src.player_selection", level="WARNING"):
            result = selector.select(selector.fetch_candidate_pool())

        self.assertFalse(result.is_complete)
        self.assertEqual(result.selected["intermedio"], ["only"])

    # -- Congelado ---------------------------------------------------------------

    def test_first_run_writes_selection_and_next_runs_reuse_it_without_api(self) -> None:
        config = self.config_for_test({"intermedio": 2})
        api_get, calls = self.fake_api({f"p{index}": (1300, 1310, 1320) for index in range(4)})

        first = load_or_create_selection(config, selector=self.selector(config, api_get))
        path = Path(config["player_selection"]["selection_path"])
        self.assertTrue(path.exists())
        self.assertEqual(len(first), 2)
        self.assertEqual(yaml.safe_load(path.read_text())["status"], "complete")

        calls.clear()
        second = load_or_create_selection(config, selector=self.selector(config, api_get))
        self.assertEqual(second, first)
        self.assertEqual(calls, [])

    def test_selection_below_download_minimum_is_not_frozen(self) -> None:
        config = self.config_for_test({"intermedio": 2})
        config["download"]["min_users_ok"] = 5
        api_get, _ = self.fake_api({"p0": (1300, 1310)})

        with self.assertRaises(InsufficientSelectionError):
            load_or_create_selection(config, selector=self.selector(config, api_get))
        self.assertFalse(Path(config["player_selection"]["selection_path"]).exists())

    def test_snapshot_is_reused_on_retry(self) -> None:
        config = self.config_for_test()
        snapshot = self.tmp / "seleccion" / "country_AR.json"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text(json.dumps({"players": ["frozen"]}))
        api_get, calls = self.fake_api({"other": (1300, 1300)})

        pool = self.selector(config, api_get).fetch_candidate_pool()

        self.assertIn("frozen", pool)
        self.assertNotIn("other", pool)
        self.assertNotIn(f"{PUBAPI_ROOT}/country/AR/players", calls)

    def test_load_selection_rejects_empty_file(self) -> None:
        path = self.tmp / "empty.yaml"
        path.write_text("usernames: []\n")
        with self.assertRaises(ValueError):
            load_selection(path)


if __name__ == "__main__":
    unittest.main()
