"""Controles de disponibilidad y de separación temporal de la referencia inicial."""

import unittest

import numpy as np
import pandas as pd

from src.experiment_rating_reference import purged_folds, rating_features


class RatingReferenceTest(unittest.TestCase):
    def test_incidental_rating_is_masked_without_computing_fake_difference(self):
        row = dict(TimeClass="blitz", tiempo_base_seg=180, incremento_seg=0, EsTorneo=False,
                   rating_blancas=1200., rating_negras=1600., age_days_blancas=.1, age_days_negras=3.,
                   source_owner_blancas=True, source_owner_negras=False, WhiteElo=9999)
        frame = pd.DataFrame([row])
        own = rating_features(frame, False)
        enriched = rating_features(frame, True)
        self.assertTrue(np.isnan(own.loc[0, "rating_difference"]))
        self.assertEqual(own.loc[0, "rating_mean_known"], 1200)
        self.assertEqual(enriched.loc[0, "rating_difference"], -400)
        self.assertNotIn("WhiteElo", enriched.columns)

    def test_fold_purges_unfinished_training_game(self):
        starts = pd.date_range("2026-01-01", periods=12, freq="h", tz="UTC")
        games = pd.DataFrame(dict(GameUrl=[str(i) for i in range(12)], StartTime=starts,
                                 EndTime=starts + pd.Timedelta(minutes=10)))
        games.loc[2, "EndTime"] = starts[10]
        for train, valid in purged_folds(games, n_splits=2):
            self.assertNotIn(2, train)
            self.assertLess(games.iloc[train]["EndTime"].max(), games.iloc[valid]["StartTime"].min())

    def test_old_incidental_rating_is_masked_but_own_archive_is_preserved(self):
        frame = pd.DataFrame([dict(TimeClass="blitz", tiempo_base_seg=180, incremento_seg=0, EsTorneo=False,
            rating_blancas=1200., rating_negras=1600., age_days_blancas=60., age_days_negras=60.,
            source_owner_blancas=True, source_owner_negras=False)])
        features = rating_features(frame, True, max_incidental_age_days=30)
        self.assertEqual(features.loc[0, "rating_known_blancas"], 1.)
        self.assertEqual(features.loc[0, "rating_known_negras"], 0.)
        self.assertTrue(np.isnan(features.loc[0, "rating_difference"]))
