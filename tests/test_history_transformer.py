"""Historial del Pipeline: causalidad, ventanas y serialización sin datos de fit."""

import io
import unittest

import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline

from src.history_transformer import HISTORY_FEATURES, PlayerHistoryTransformer


def event(end, rating=1500, score=1.0, tc="blitz", start=None, url=None):
    return (end, tc, rating, score, False, 0.5, end - 100 if start is None else start, str(url or end))


def frame(history, at=6300):
    return pd.DataFrame({
        "StartTime": [pd.Timestamp(at, unit="s", tz="UTC")], "TimeClass": ["blitz"],
        "historial_blancas": [tuple(history)], "historial_negras": [()],
    })


class PlayerHistoryTransformerTest(unittest.TestCase):
    def test_windows_are_computed_inside_pipeline_and_opponent_stays_missing(self):
        history = [event(i * 600, rating=1500 + i, score=0 if i < 4 else 1) for i in range(1, 11)]
        pipeline = Pipeline([("historial", PlayerHistoryTransformer(HISTORY_FEATURES))])
        values = pipeline.fit_transform(frame(history))
        self.assertEqual(values.loc[0, "elo_blancas_previo"], 1510)
        self.assertAlmostEqual(values.loc[0, "forma_ultimas10_blancas"], .7)
        self.assertEqual(values.loc[0, "racha_blancas"], 7)
        self.assertTrue(pd.isna(values.loc[0, "tendencia_rating_blancas"]))
        self.assertEqual(values.loc[0, "partidas_sesion_blancas"], 10)
        self.assertEqual(values.loc[0, "minutos_desde_anterior_blancas"], 5)
        self.assertAlmostEqual(values.loc[0, "reloj_final_blancas"], .5)
        self.assertTrue(values.filter(like="negras").isna().all().all())

    def test_current_equal_overlapping_and_future_results_are_excluded(self):
        past = [event(i * 600) for i in range(1, 12)]
        original = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(past, at=7000))
        # A finish at the exact start is excluded, as are a game in progress and the future.
        later = past + [event(7000, 500, 0), event(7100, 400, 0, start=6900), event(9000, 300, 0)]
        changed = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(later, at=7000))
        pd.testing.assert_frame_equal(original, changed)
        self.assertEqual(original.loc[0, "tendencia_rating_blancas"], 0)

    def test_other_rhythm_only_affects_session_and_gap(self):
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(
            frame([event(600, 1500), event(1200, 900, 0, tc="rapid")], at=1500)
        )
        self.assertEqual(values.loc[0, "elo_blancas_previo"], 1500)
        self.assertEqual(values.loc[0, "racha_blancas"], 1)
        self.assertEqual(values.loc[0, "partidas_sesion_blancas"], 2)
        self.assertEqual(values.loc[0, "minutos_desde_anterior_blancas"], 5)

    def test_clone_serialization_order_and_repeated_cuts(self):
        X = pd.concat([frame([event(600)], at=900), frame([event(600), event(1200)], at=1500)])
        transformer = clone(PlayerHistoryTransformer(HISTORY_FEATURES)).fit(X, ["win", "loss"])
        expected = transformer.transform(X)
        buffer = io.BytesIO()
        joblib.dump(transformer, buffer)
        buffer.seek(0)
        loaded = joblib.load(buffer)
        pd.testing.assert_frame_equal(loaded.transform(X.iloc[::-1]), expected.iloc[::-1])
        self.assertFalse(any(isinstance(value, pd.DataFrame) for value in vars(loaded).values()))

    def test_supplied_aggregates_cannot_override_observed_history(self):
        X = frame([event(600, 1510)], at=900).assign(elo_blancas_previo=9999)
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(X)
        self.assertEqual(values.loc[0, "elo_blancas_previo"], 1510)
        self.assertTrue(pd.isna(values.loc[0, "forma_ultimas10_blancas"]))
        # A live caller may supply its current, observed pre-game rating without history.
        X["historial_blancas"] = [()]
        self.assertEqual(PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(X).loc[0, "elo_blancas_previo"], 9999)


if __name__ == "__main__":
    unittest.main()
