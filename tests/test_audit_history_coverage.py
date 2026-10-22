"""La cobertura incidental nunca puede reutilizar la partida objetivo ni el futuro."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.audit_history_coverage import lookup_previous_ratings, read_observations


class HistoryCoverageTest(unittest.TestCase):
    def games(self):
        return pd.DataFrame([dict(GameUrl="target", White="Alice", Black="Bob", TimeClass="blitz",
            StartTime=pd.Timestamp(100, unit="s", tz="UTC"))])

    def observations(self):
        return pd.DataFrame([
            dict(username="alice", GameUrl="past", time_class="blitz", rating=1200., end_time=90., source_owner=True),
            dict(username="alice", GameUrl="equal", time_class="blitz", rating=1500., end_time=100., source_owner=False),
            dict(username="alice", GameUrl="target", time_class="blitz", rating=1600., end_time=110., source_owner=True),
            dict(username="bob", GameUrl="rapid", time_class="rapid", rating=2200., end_time=95., source_owner=False),
        ])

    def test_strict_time_and_same_rhythm(self):
        rows = lookup_previous_ratings(self.games(), self.observations()).set_index("side")
        self.assertEqual(rows.loc["blancas", "rating"], 1200)
        self.assertEqual(rows.loc["blancas", "GameUrl"], "past")
        self.assertTrue(pd.isna(rows.loc["negras", "rating"]))

    def test_future_observations_do_not_change_past(self):
        old = self.observations().iloc[:1]
        a = lookup_previous_ratings(self.games(), old)
        b = lookup_previous_ratings(self.games(), self.observations())
        np.testing.assert_allclose(a["rating"], b["rating"], equal_nan=True)

    def test_empty_history_keeps_both_colors(self):
        rows = lookup_previous_ratings(self.games(), self.observations().iloc[:0])
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows["rating"].isna().all())

    def test_missing_start_is_rejected(self):
        games = self.games()
        games["StartTime"] = pd.NaT
        with self.assertRaises(ValueError):
            lookup_previous_ratings(games, self.observations())

    def test_duplicate_copies_prefer_owner_and_conflicts_are_rejected(self):
        game = dict(url="previous", rated=True, rules="chess", time_class="blitz", pgn="1. e4 *", end_time=90,
                    white=dict(username="Alice", rating=1200), black=dict(username="Bob", rating=1300))
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "alice.json", Path(temporary) / "bob.json"
            first.write_text(json.dumps({"games": [game]}))
            second.write_text(json.dumps({"games": [game]}))
            rows, metadata = read_observations({"alice": first, "bob": second})
            self.assertEqual(len(rows), 2)
            self.assertTrue(rows["source_owner"].all())
            self.assertEqual(metadata["duplicated_observations"], 2)
            game["white"]["rating"] = 999
            second.write_text(json.dumps({"games": [game]}))
            with self.assertRaisesRegex(ValueError, "contradictorias"):
                read_observations({"alice": first, "bob": second})
