"""Historial del Pipeline: causalidad, ventanas y serialización sin datos de fit."""

import io
import json
import tempfile
import unittest
from pathlib import Path

import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline

from src.history_transformer import HISTORY_FEATURES, PlayerHistoryTransformer, player_history_payloads
from src.rating_history import game_observations


def event(end, rating=1500, score=1.0, tc="blitz", start=None, url=None):
    return (end, tc, rating, score, False, 0.5, end - 100 if start is None else start, str(url or end))


def rival(end, rating=1500, tc="blitz", start=None, url=None):
    """A rating-only observation: the account appeared as someone else's opponent."""
    return (end, tc, rating, None, False, None, end - 100 if start is None else start, str(url or end), False)


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



class RivalRatingObservationsTest(unittest.TestCase):
    def test_target_game_seen_as_rival_observation_is_not_used(self):
        # The game being predicted closes after its own start: its rating is posterior.
        history = [rival(1000, 1400), rival(7000, 1900, start=6300, url="target")]
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(history, at=6300))
        self.assertEqual(values.loc[0, "elo_blancas_previo"], 1400)

    def test_simultaneous_close_is_not_used(self):
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame([rival(1000, 1400), rival(6300, 1900)]))
        self.assertEqual(values.loc[0, "elo_blancas_previo"], 1400)

    def test_rival_observation_sets_rating_and_age_but_not_form_or_session(self):
        own = [event(i * 600, rating=1500, score=1.0) for i in range(1, 11)]
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(own, at=86400 * 2))
        mixed = own + [rival(86400 * 2 - 3600, 1650)]
        changed = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(mixed, at=86400 * 2))
        self.assertEqual(changed.loc[0, "elo_blancas_previo"], 1650)
        self.assertAlmostEqual(changed.loc[0, "antiguedad_rating_dias_blancas"], 1 / 24)
        unchanged = [f"{c}_blancas" for c in ["forma_ultimas10", "racha", "minutos_desde_anterior", "partidas_sesion",
                                               "derrotas_por_tiempo", "reloj_final"]]
        pd.testing.assert_series_equal(changed.loc[0, unchanged], values.loc[0, unchanged])

    def test_rating_age_in_days(self):
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame([event(6300 - 86400 * 3)], at=6300))
        self.assertAlmostEqual(values.loc[0, "antiguedad_rating_dias_blancas"], 3)
        self.assertTrue(pd.isna(values.loc[0, "antiguedad_rating_dias_negras"]))

    def test_eight_field_observations_count_as_own(self):
        own8 = [event(i * 600) for i in range(1, 11)]
        own9 = [(*e, True) for e in own8]
        a = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(own8))
        b = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(frame(own9))
        pd.testing.assert_frame_equal(a, b)

    def test_difference_only_with_both_ratings_and_mean_of_known(self):
        X = frame([event(600, 1600)], at=900)
        values = PlayerHistoryTransformer(HISTORY_FEATURES).fit_transform(X)
        self.assertTrue(pd.isna(values.loc[0, "diferencia_elo_previa"]))
        self.assertEqual(values.loc[0, "elo_promedio_previo"], 1600)
        X["historial_negras"] = [(rival(500, 1400),)]
        values = PlayerHistoryTransformer(["diferencia_elo_previa", "elo_promedio_previo"]).fit_transform(X)
        self.assertEqual(values.loc[0, "diferencia_elo_previa"], 200)
        self.assertEqual(values.loc[0, "elo_promedio_previo"], 1500)
        self.assertEqual(list(values.columns), ["diferencia_elo_previa", "elo_promedio_previo"])

    def test_duplicates_across_files_count_once_and_own_copy_wins(self):
        def game(url, end, white, black, w_rating, b_rating):
            return {"url": url, "end_time": end, "time_class": "blitz", "time_control": "180", "pgn": "",
                    "white": {"username": white, "rating": w_rating, "result": "win"},
                    "black": {"username": black, "rating": b_rating, "result": "resigned"}}

        shared = game("g1", 1000, "Ana", "Beto", 1510, 1490)
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for user, games in {"ana": [shared, game("g2", 2000, "Ana", "Caro", 1520, 1700)],
                                "beto": [shared, shared]}.items():
                paths[user] = Path(tmp) / f"{user}.json"
                paths[user].write_text(json.dumps({"games": games}))
            observations = game_observations(paths)
            payloads = player_history_payloads(
                paths, pd.DataFrame({"GameUrl": ["g1", "g2"], "StartTime": pd.to_datetime([900, 1900], unit="s", utc=True)}),
                rivales=True)
        self.assertFalse(observations.duplicated(["username", "GameUrl"]).any())
        beto = observations[observations["username"] == "beto"]
        self.assertEqual(len(beto), 1)
        self.assertTrue(beto["propia"].iloc[0])
        caro = observations[observations["username"] == "caro"]
        self.assertEqual(caro[["GameUrl", "rating_posterior"]].values.tolist(), [["g2", 1700]])
        self.assertFalse(caro["propia"].iloc[0])
        self.assertEqual(payloads["caro"], ((2000, "blitz", 1700, None, False, None, 1900.0, "g2", False),))


if __name__ == "__main__":
    unittest.main()
