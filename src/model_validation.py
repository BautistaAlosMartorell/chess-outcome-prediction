"""Validación cruzada temporal y por partida para la tabla de cortes.

Cada partida aporta hasta 25 filas (una por corte) con el mismo resultado. Si esas filas
quedaran repartidas entre entrenamiento y validación, el modelo vería en entrenamiento el
resultado de una partida que después tiene que predecir. Además, el uso real es predecir
partidas **futuras**. Por eso los pedazos se arman sobre partidas ordenadas por inicio
(``TimeSeriesSplit``), no sobre filas, y después se expanden a sus cortes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit


def temporal_game_folds(
    game_ids: pd.Series, start_times: pd.Series, n_splits: int = 5
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Folds de ``TimeSeriesSplit`` sobre partidas, devueltos como posiciones de fila.

    ``game_ids`` y ``start_times`` están alineados con las filas de la tabla (una por
    corte). En cada fold, todas las filas de una partida caen del mismo lado, y toda
    partida de validación empieza después que cualquier partida de entrenamiento. Las
    posiciones (0..n-1) sirven para ``iloc`` o para ``cross_validate(cv=...)``.
    """
    games = pd.DataFrame({"game": game_ids.to_numpy(), "start": start_times.to_numpy()}).drop_duplicates()
    assert games["game"].is_unique, "Una partida con más de un StartTime"
    ordered = games.sort_values(["start", "game"], kind="stable")["game"].to_numpy()
    # Position of each row's game in time order.
    game_rank = pd.Index(ordered).get_indexer(game_ids.to_numpy())
    folds = []
    for train_games, val_games in TimeSeriesSplit(n_splits=n_splits).split(ordered):
        train_rows = np.flatnonzero(np.isin(game_rank, train_games))
        val_rows = np.flatnonzero(np.isin(game_rank, val_games))
        folds.append((train_rows, val_rows))
    return folds
