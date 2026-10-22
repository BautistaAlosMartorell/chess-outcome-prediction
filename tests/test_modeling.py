"""Pruebas de la validación temporal por partida y de la predicción jugada a jugada."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor

from src.model_validation import temporal_game_folds
from src.predict import LIVE, PRE_GAME, RESULT_ORDER, model_frame, predecir
from test_live_features import MOVES, _pgn


class TemporalGameFoldsTest(unittest.TestCase):
    def test_games_never_split_and_validation_is_later(self) -> None:
        rng = np.random.default_rng(0)
        games = pd.DataFrame({"game": [f"g{i}" for i in range(30)], "start": rng.permutation(30) * 100})
        # Up to 4 cuts per game, rows shuffled: the order of the table must not matter.
        rows = games.loc[games.index.repeat(rng.integers(1, 5, size=30))].sample(frac=1, random_state=0)
        rows = rows.reset_index(drop=True)

        folds = temporal_game_folds(rows["game"], rows["start"], n_splits=3)
        self.assertEqual(len(folds), 3)
        for train, val in folds:
            train_games, val_games = set(rows.loc[train, "game"]), set(rows.loc[val, "game"])
            self.assertFalse(train_games & val_games)
            self.assertLess(rows.loc[train, "start"].max(), rows.loc[val, "start"].min())
            # Every row of a game in the fold travels with it.
            self.assertEqual(len(train), rows["game"].isin(train_games).sum())
            self.assertEqual(len(val), rows["game"].isin(val_games).sum())

    def test_a_game_with_two_start_times_is_an_error(self) -> None:
        with self.assertRaises(AssertionError):
            temporal_game_folds(pd.Series(["g1", "g1", "g2"]), pd.Series([1, 2, 3]), n_splits=2)


class PredecirTest(unittest.TestCase):
    CONTEXT = {"TimeClass": "blitz", "tiempo_base_seg": 180, "incremento_seg": 2, "elo_blancas_previo": 1500}

    def _model(self) -> dict:
        columns = PRE_GAME + LIVE
        X = model_frame(pd.DataFrame({"TimeClass": ["blitz"] * 6}), columns)
        # Priors 3/6, 1/6, 2/6: classes_ come out sorted, so the mapping to names is tested.
        y = ["Gana Blancas"] * 3 + ["Empate"] + ["Gana Negras"] * 2
        return {
            "resultado": DummyClassifier(strategy="prior").fit(X, y),
            "plies_restantes": DummyRegressor(strategy="constant", constant=0).fit(X, [0] * 6),
            "columnas": columns,
        }

    def test_one_row_per_ply_with_probabilities_by_name(self) -> None:
        result = predecir(_pgn(MOVES), self.CONTEXT, self._model())
        self.assertEqual(result["ply"].tolist(), list(range(len(MOVES))))  # the game is over at ply 22
        self.assertEqual(list(result.columns), ["ply", *RESULT_ORDER, "plies_restantes"])
        np.testing.assert_allclose(result[RESULT_ORDER].sum(axis=1), 1)
        np.testing.assert_allclose(result.loc[0, RESULT_ORDER].to_numpy(dtype=float), [3 / 6, 1 / 6, 2 / 6])
        self.assertTrue((result["plies_restantes"] >= 1).all())  # a game in progress has at least one ply left

    def test_model_frame_types_and_missing_columns(self) -> None:
        frame = model_frame(
            pd.DataFrame({"TimeClass": ["rapid"], "EsTorneo": [True], "en_jaque": [False]}),
            ["TimeClass", "EsTorneo", "en_jaque", "forma_ultimas10_negras"],
        )
        self.assertEqual(frame.loc[0, "TimeClass"], "rapid")
        self.assertEqual(frame.loc[0, "EsTorneo"], 1.0)
        self.assertEqual(frame["en_jaque"].dtype, "float64")
        self.assertTrue(pd.isna(frame.loc[0, "forma_ultimas10_negras"]))  # unknown side stays NaN


if __name__ == "__main__":
    unittest.main()
