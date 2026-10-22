"""Historial causal dentro del Pipeline de entrenamiento y predicción.

Los historiales son observaciones de partidas terminadas, no columnas ya agregadas.
El transformador calcula rating, forma y estilo al consultar cada inicio. No aprende
promedios globales ni usa el objetivo que recibe ``fit``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from src.rating_history import (
    FORM_COLUMNS, FORM_WINDOW, SESSION_GAP_MINUTES, STYLE_COLUMNS, STYLE_WINDOW,
    _streak_after_each_game, own_game_history,
)

HISTORY_INPUTS = ["StartTime", "historial_blancas", "historial_negras"]
HISTORY_FEATURES = ["elo_blancas_previo", "elo_negras_previo"] + [
    f"{column}_{side}" for column in FORM_COLUMNS + STYLE_COLUMNS for side in ("blancas", "negras")
]
# One immutable tuple per account, shared by all its rows/cuts. Fields are source
# observations; rolling statistics and lookup at prediction time belong to transform.
History = tuple[tuple, ...]


def player_history_payloads(raw_paths: Mapping[str, Path], start_times: pd.DataFrame) -> dict[str, History]:
    """Lee observaciones individuales y horarios; no calcula features del modelo."""
    history = own_game_history(raw_paths)
    starts = start_times.set_index("GameUrl")["StartTime"]
    assert starts.index.is_unique, "Un inicio por partida"
    # Timestamp resolution may be us or ns in pandas: use timedeltas explicitly.
    known = history["GameUrl"].map(starts)
    seconds = (known - pd.Timestamp("1970-01-01", tz="UTC")) / pd.Timedelta(seconds=1)
    history["start_time"] = seconds.fillna(history["end_time"])
    fields = ["end_time", "time_class", "rating_posterior", "puntaje", "por_tiempo", "reloj_final_frac", "start_time", "GameUrl"]
    return {username: tuple(group[fields].itertuples(index=False, name=None))
            for username, group in history.groupby("username", sort=False)}


def attach_player_histories(frame: pd.DataFrame, histories: Mapping[str, History]) -> pd.DataFrame:
    """Adjunta las observaciones por cuenta, sin agregar ni mirar el resultado actual."""
    result = frame.copy()
    for side, player in (("blancas", "White"), ("negras", "Black")):
        result[f"historial_{side}"] = result[player].astype("string").str.lower().map(histories).map(
            lambda value: value if isinstance(value, tuple) else ()
        )
    return result


def _timeline(payload: History) -> tuple[dict, np.ndarray, np.ndarray]:
    """Statistics after each observed finish, queried strictly before each start."""
    h = pd.DataFrame(payload, columns=["end", "tc", "rating", "score", "timeout", "clock", "start", "url"])
    h = h.sort_values(["end", "url"], kind="stable").reset_index(drop=True)
    timelines = {}
    for tc, group in h.groupby("tc", sort=False):
        group = group.reset_index(drop=True)
        rating = group["rating"].astype(float)
        values = np.column_stack([
            rating,
            group["score"].rolling(FORM_WINDOW, min_periods=FORM_WINDOW).mean(),
            _streak_after_each_game(group["score"]),
            rating - rating.shift(FORM_WINDOW),
            group["timeout"].astype(float).rolling(STYLE_WINDOW, min_periods=FORM_WINDOW).mean(),
            group["clock"].astype(float).rolling(STYLE_WINDOW, min_periods=FORM_WINDOW).mean(),
        ])
        timelines[tc] = (group["end"].to_numpy(dtype=float), values)
    gaps = (h["start"] - h["end"].shift()) / 60
    session_ids = (gaps.isna() | gaps.ge(SESSION_GAP_MINUTES)).cumsum()
    session_count = h.groupby(session_ids).cumcount().to_numpy() + 1
    return timelines, h["end"].to_numpy(dtype=float), session_count


class PlayerHistoryTransformer(TransformerMixin, BaseEstimator):
    """Deriva el historial usando sólo cierres estrictamente anteriores al inicio.

    Entrada: columnas candidatas más ``TimeClass``, ``StartTime`` e
    ``historial_blancas/negras``. Un historial puede contener partidas futuras: el
    filtro temporal excluye tanto esas como la actual y las solapadas. El mismo
    cálculo sirve para CV, entrenamiento final y nuevas partidas de la app.

    Sin historial se conservan observaciones pre-partida explícitas del llamador
    (por ejemplo su rating actual); los faltantes siguen NaN. El notebook de
    entrenamiento entrega NaN en todas las derivadas y exige historiales crudos.
    """

    def __init__(self, columns: list[str]):
        self.columns = columns

    def fit(self, X: pd.DataFrame, y=None):
        self.n_features_in_ = X.shape[1]
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        check_is_fitted(self, "n_features_in_")
        result = X.reindex(columns=self.columns).copy()
        wanted = set(self.columns) & set(HISTORY_FEATURES)
        if not wanted:
            return result
        start = pd.to_datetime(X.get("StartTime", pd.Series(pd.NaT, index=X.index)), utc=True)
        seconds = ((start - pd.Timestamp("1970-01-01", tz="UTC")) / pd.Timedelta(seconds=1)).to_numpy()
        tc = X["TimeClass"].astype(str).to_numpy()
        # Cache only within this transform call: no validation/test observations are
        # retained in the fitted estimator or reused on a later prediction.
        timelines, answers = {}, {}
        for side in ("blancas", "negras"):
            side_columns = [f"elo_{side}_previo", *[f"{c}_{side}" for c in FORM_COLUMNS + STYLE_COLUMNS]]
            if not wanted.intersection(side_columns):
                continue
            payloads = X.get(f"historial_{side}", pd.Series([()] * len(X), index=X.index))
            values = result.reindex(columns=side_columns).to_numpy(dtype=float, copy=True)
            for row, (payload, at, rhythm) in enumerate(zip(payloads, seconds, tc)):
                if not isinstance(payload, tuple) or not payload or not np.isfinite(at):
                    continue
                key = (id(payload), at, rhythm)
                if key not in answers:
                    identity = id(payload)
                    if identity not in timelines:
                        timelines[identity] = _timeline(payload)
                    by_class, all_ends, sessions = timelines[identity]
                    v = np.full(len(side_columns), np.nan)
                    if rhythm in by_class:
                        ends, stats = by_class[rhythm]
                        previous = np.searchsorted(ends, at, side="left") - 1
                        if previous >= 0:
                            v[[0, 1, 2, 3, 6, 7]] = stats[previous]
                    previous = np.searchsorted(all_ends, at, side="left") - 1
                    v[5] = 0
                    if previous >= 0:
                        v[4] = (at - all_ends[previous]) / 60
                        v[5] = sessions[previous] if v[4] < SESSION_GAP_MINUTES else 0
                    answers[key] = v
                values[row] = answers[key]
            for j, column in enumerate(side_columns):
                if column in wanted:
                    result[column] = values[:, j]
        return result

    def get_feature_names_out(self, input_features=None):
        return np.asarray(self.columns, dtype=object)
