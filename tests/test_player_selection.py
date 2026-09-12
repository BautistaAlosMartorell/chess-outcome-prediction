"""Pruebas offline del selector ocasional de jugadores."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import yaml

from src.player_selection import (
    Candidate,
    CandidateValidation,
    InsufficientCandidatesError,
    PlayerSelector,
    SelectionResult,
    apply_selection_to_config,
    bootstrap_username_list,
    extract_candidate_pools,
    write_manifest,
)
from src.utils import load_config


class PlayerSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_config = load_config("config/config.yaml")

    def config_for_test(self) -> dict:
        config = copy.deepcopy(self.base_config)
        config["download"]["request_delay_seconds"] = 0
        config["player_selection"]["min_eligible_games"] = 2
        config["player_selection"]["max_games_per_candidate"] = 3
        return config

    def test_extract_candidates_deduplicates_and_excludes_seeds_case_insensitively(self) -> None:
        df = pd.DataFrame(
            {
                "White": ["Seed", "Opponent", "opponent", "Boundary"],
                "Black": ["Opponent", "SEED", "Other", "Advanced"],
                "WhiteElo": [1500, 1600, 1700, 1799],
                "BlackElo": [1400, 1500, 1300, 1800],
            }
        )
        pools = extract_candidate_pools(
            df,
            ["seed"],
            self.base_config["elo"]["bandas"],
            {"intermedio": 8, "avanzado": 8},
        )

        intermediate = {candidate.username.casefold(): candidate for candidate in pools["intermedio"]}
        advanced = {candidate.username.casefold(): candidate for candidate in pools["avanzado"]}
        self.assertNotIn("seed", intermediate)
        self.assertEqual(intermediate["opponent"].historical_median_elo, 1600.0)
        self.assertEqual(intermediate["opponent"].observed_games, 3)
        self.assertIn("boundary", intermediate)
        self.assertIn("advanced", advanced)

    def test_band_boundaries_are_lower_inclusive_and_upper_exclusive(self) -> None:
        df = pd.DataFrame(
            {
                "White": ["At1200", "Below1800", "At1800", "At2200"],
                "Black": ["Seed"] * 4,
                "WhiteElo": [1200, 1799.9, 1800, 2200],
                "BlackElo": [1500] * 4,
            }
        )
        pools = extract_candidate_pools(
            df,
            ["Seed"],
            self.base_config["elo"]["bandas"],
            {"intermedio": 1, "avanzado": 1},
        )
        self.assertEqual(
            {candidate.username for candidate in pools["intermedio"]},
            {"At1200", "Below1800"},
        )
        self.assertEqual(
            {candidate.username for candidate in pools["avanzado"]},
            {"At1800"},
        )

    @staticmethod
    def game(username: str, rating: int, *, rated: bool = True) -> dict:
        return {
            "rules": "chess",
            "time_class": "blitz",
            "rated": rated,
            "white": {"username": username, "rating": rating},
            "black": {"username": "rival", "rating": rating + 5},
        }

    def api_payloads(self, username: str, *, status: str = "basic", ratings=(1500, 1550)) -> dict:
        base = self.base_config["chess_com"]["base_url"]
        archive = f"{base}/{username.lower()}/games/2026/08"
        return {
            f"{base}/{username.lower()}": {"username": username, "status": status},
            f"{base}/{username.lower()}/games/archives": {"archives": [archive]},
            archive: {"games": [self.game(username, rating) for rating in ratings]},
        }

    def test_validate_candidate_accepts_active_account_with_enough_games(self) -> None:
        candidate = Candidate("Active", "intermedio", 1510.0, 4)
        payloads = self.api_payloads(candidate.username, ratings=(1490, 1510, 1530))
        selector = PlayerSelector(
            self.config_for_test(),
            api_get=lambda url: payloads[url],
            sleep=lambda _: None,
        )

        result = selector.validate_candidate(candidate)

        self.assertTrue(result.accepted)
        self.assertEqual(result.eligible_games, 3)
        self.assertEqual(result.validated_median_elo, 1510.0)

    def test_validate_candidate_rejects_closed_and_fair_play_accounts(self) -> None:
        candidate = Candidate("Closed", "intermedio", 1500.0, 3)
        for status in ("closed", "closed:fair_play_violations"):
            with self.subTest(status=status):
                payloads = self.api_payloads(candidate.username, status=status)
                selector = PlayerSelector(
                    self.config_for_test(),
                    api_get=lambda url, payloads=payloads: payloads[url],
                    sleep=lambda _: None,
                )
                result = selector.validate_candidate(candidate)
                self.assertFalse(result.accepted)
                self.assertTrue(result.reason.startswith("cuenta_no_activa:"))

    def test_validate_candidate_rejects_low_activity_and_changed_band(self) -> None:
        candidate = Candidate("Candidate", "intermedio", 1500.0, 3)
        cases = [
            ((1500,), "partidas_elegibles_insuficientes"),
            ((1850, 1900), "elo_validado_fuera_de_banda:avanzado"),
        ]
        for ratings, reason in cases:
            with self.subTest(reason=reason):
                payloads = self.api_payloads(candidate.username, ratings=ratings)
                selector = PlayerSelector(
                    self.config_for_test(),
                    api_get=lambda url, payloads=payloads: payloads[url],
                    sleep=lambda _: None,
                )
                result = selector.validate_candidate(candidate)
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, reason)

    @staticmethod
    def candidate_dataframe(count: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "White": [f"Candidate{index}" for index in range(count)],
                "Black": ["RebeccaHarris"] * count,
                "WhiteElo": [1500 + index for index in range(count)],
                "BlackElo": [1400] * count,
            }
        )

    @staticmethod
    def accept(candidate: Candidate) -> CandidateValidation:
        return CandidateValidation(
            username=candidate.username,
            band=candidate.band,
            accepted=True,
            reason="aceptado",
            historical_median_elo=candidate.historical_median_elo,
            eligible_games=500,
            validated_median_elo=candidate.historical_median_elo,
        )

    def test_selection_is_deterministic_with_fixed_seed(self) -> None:
        config = self.config_for_test()
        config["player_selection"]["target_per_band"] = {"intermedio": 2}
        first = PlayerSelector(config, api_get=lambda _: {}, sleep=lambda _: None)
        second = PlayerSelector(config, api_get=lambda _: {}, sleep=lambda _: None)

        with mock.patch.object(first, "validate_candidate", side_effect=self.accept):
            first_result = first.select_from_dataframe(self.candidate_dataframe(6))
        with mock.patch.object(second, "validate_candidate", side_effect=self.accept):
            second_result = second.select_from_dataframe(self.candidate_dataframe(6))

        self.assertEqual(first_result.selected, second_result.selected)
        self.assertEqual(len(first_result.selected["intermedio"]), 2)

    def test_selection_fails_with_explanatory_partial_result(self) -> None:
        config = self.config_for_test()
        config["player_selection"]["target_per_band"] = {"intermedio": 2}
        selector = PlayerSelector(config, api_get=lambda _: {}, sleep=lambda _: None)

        with mock.patch.object(selector, "validate_candidate", side_effect=self.accept):
            with self.assertRaises(InsufficientCandidatesError) as context:
                selector.select_from_dataframe(self.candidate_dataframe(1))

        self.assertEqual(context.exception.result.selected["intermedio"], ["Candidate0"])
        self.assertIn("Faltantes: {'intermedio': 1}", str(context.exception))

    def test_preview_manifest_does_not_modify_config(self) -> None:
        result = SelectionResult(
            policy={"target_per_band": {"intermedio": 1}},
            candidate_counts={"intermedio": 1},
            evaluated=[],
            selected={"intermedio": ["NewPlayer"]},
        )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            manifest_path = Path(tmp) / "manifest.yaml"
            config_path.write_text("chess_com:\n  usernames:\n    - Seed\n", encoding="utf-8")
            before = config_path.read_text(encoding="utf-8")

            write_manifest(result, manifest_path)

            self.assertEqual(config_path.read_text(encoding="utf-8"), before)
            self.assertEqual(yaml.safe_load(manifest_path.read_text())["status"], "complete")

    def test_apply_preserves_seeds_comments_and_removes_duplicates(self) -> None:
        content = (
            "chess_com:\n"
            "  usernames:\n"
            "    - SeedOne  # comentario original\n"
            "    - SeedTwo\n"
            "  max_games_per_user: 1000\n"
            "other: true\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(content, encoding="utf-8")

            usernames = apply_selection_to_config(
                config_path,
                ["SeedOne", "SeedTwo"],
                {"intermedio": ["NewPlayer", "seedone"], "avanzado": ["OtherPlayer"]},
            )

            updated = config_path.read_text(encoding="utf-8")
            self.assertEqual(usernames, ["SeedOne", "SeedTwo", "NewPlayer", "OtherPlayer"])
            self.assertIn("# comentario original", updated)
            self.assertTrue(yaml.safe_load(updated)["other"])
            self.assertEqual(yaml.safe_load(updated)["chess_com"]["usernames"], usernames)

    # -- New tests for lenient selection, build_username_list, and bootstrap --

    def test_select_lenient_tolerates_incomplete_bands(self) -> None:
        """select_lenient_from_dataframe logs warnings but doesn't raise."""
        config = self.config_for_test()
        config["player_selection"]["target_per_band"] = {"intermedio": 5}
        selector = PlayerSelector(config, api_get=lambda _: {}, sleep=lambda _: None)

        with mock.patch.object(selector, "validate_candidate", side_effect=self.accept):
            # Only 2 candidates in pool, target is 5 → incomplete but no error.
            result = selector.select_lenient_from_dataframe(self.candidate_dataframe(2))

        self.assertFalse(result.is_complete)
        self.assertEqual(len(result.selected["intermedio"]), 2)

    def test_build_username_list_returns_seeds_first_then_selected(self) -> None:
        """build_username_list combines seeds + selected, deduplicated."""
        config = self.config_for_test()
        config["player_selection"]["target_per_band"] = {"intermedio": 2}
        selector = PlayerSelector(config, api_get=lambda _: {}, sleep=lambda _: None)

        with mock.patch.object(selector, "validate_candidate", side_effect=self.accept):
            combined, result = selector.build_username_list(self.candidate_dataframe(6))

        # Seeds come first.
        seeds = config["player_selection"]["seed_usernames"]
        self.assertEqual(combined[: len(seeds)], seeds)
        # Selected players follow.
        self.assertGreater(len(combined), len(seeds))
        # No duplicates (case-insensitive).
        normalised = [u.casefold() for u in combined]
        self.assertEqual(len(normalised), len(set(normalised)))

    def test_build_username_list_deduplicates_seed_in_selected(self) -> None:
        """If a seed appears in selected, it's not duplicated."""
        config = self.config_for_test()
        config["player_selection"]["target_per_band"] = {"intermedio": 1}
        selector = PlayerSelector(config, api_get=lambda _: {}, sleep=lambda _: None)

        # Dataframe where the only non-seed opponent is another seed.
        df = pd.DataFrame(
            {
                "White": ["RebeccaHarris", "erik"],
                "Black": ["erik", "RebeccaHarris"],
                "WhiteElo": [1400, 1700],
                "BlackElo": [1700, 1400],
            }
        )
        with mock.patch.object(selector, "validate_candidate", side_effect=self.accept):
            combined, result = selector.build_username_list(df)

        # Seeds should not be duplicated even if accepted as candidates.
        normalised = [u.casefold() for u in combined]
        self.assertEqual(len(normalised), len(set(normalised)))

    def test_bootstrap_returns_only_seeds(self) -> None:
        """bootstrap_username_list returns a copy of seed_usernames."""
        config = self.config_for_test()
        seeds = config["player_selection"]["seed_usernames"]
        result = bootstrap_username_list(config)
        self.assertEqual(result, seeds)
        # Must be a copy, not the same list.
        self.assertIsNot(result, seeds)


if __name__ == "__main__":
    unittest.main()
