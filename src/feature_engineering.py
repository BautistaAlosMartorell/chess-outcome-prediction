"""Ingeniería de features sobre partidas de ajedrez (vectorizado)."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)

# moves_text arranca siempre con "1. <blancas> 1... <negras>" (Chess.com numera también
# la jugada de negras). MIN_PLIES garantiza que existan las dos primeras jugadas.
_FIRST_MOVES_RE = re.compile(r"^\s*1\.\s*(\S+)\s+1\.\.\.\s*(\S+)")

MATCHUP_OTRA = "otra"
RESULT_RATE_COLUMNS = {
    "tasa_blancas_hist": "Gana Blancas",
    "tasa_tablas_hist": "Empate",
    "tasa_negras_hist": "Gana Negras",
}


def _to_naive_utc(values: pd.Series) -> np.ndarray:
    """Timestamps UTC como ``datetime64`` sin zona, comparables con ``searchsorted``."""
    values = pd.to_datetime(values, utc=True)
    return values.dt.tz_convert(None).to_numpy(dtype="datetime64[ns]")


def _prior_counts(start: np.ndarray, end: np.ndarray, onehot: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Para cada inicio, cuántas partidas del grupo terminaron ANTES y con qué resultados.

    ``end``/``onehot`` describen las partidas del grupo con fin conocido. Se ordenan
    por fin, se acumulan los resultados y cada inicio se ubica con ``searchsorted``
    (``side="left"``): cuenta sólo fines estrictamente anteriores al inicio. Una
    partida nunca se cuenta a sí misma porque termina después de empezar.
    """
    order = np.argsort(end, kind="stable")
    cumulative = np.vstack([np.zeros((1, onehot.shape[1])), np.cumsum(onehot[order], axis=0)])
    n_prev = np.searchsorted(end[order], start, side="left")
    return n_prev, cumulative[n_prev]


def matchup_history(
    df: pd.DataFrame,
    min_prev: int,
    shrink_m: float | None = None,
) -> pd.DataFrame:
    """Tasas históricas de resultado por ``matchup_apertura`` y ``TimeClass``, sin fuga.

    Para cada partida *i* se usan sólo las partidas *j* del mismo matchup y ritmo con
    ``EndTime_j < StartTime_i``: lo que un observador podía saber al empezar la
    partida. Con menos de ``min_prev`` previas la tasa queda NaN (historial
    insuficiente); no se imputa.

    Con ``shrink_m`` se devuelve en cambio la variante contraída
    ``(k + m * p_previa) / (n + m)``, donde ``p_previa`` es la tasa del mismo ritmo
    (todos los matchups) también calculada sólo con partidas previas. Es para modelos
    que no aceptan NaN; siempre debe acompañarse de ``historial_suficiente``.
    """
    outcomes = list(RESULT_RATE_COLUMNS.values())
    onehot_all = np.column_stack([(df["resultado"] == o).to_numpy(dtype=float) for o in outcomes])
    start_all = _to_naive_utc(df["StartTime"])
    end_all = _to_naive_utc(df["EndTime"])

    n_prev = np.full(len(df), np.nan)
    counts = np.full((len(df), len(outcomes)), np.nan)
    positions = pd.RangeIndex(len(df))

    def _fill(group_positions: np.ndarray, target_n: np.ndarray, target_counts: np.ndarray) -> None:
        known_end = group_positions[~np.isnat(end_all[group_positions])]
        known_start = group_positions[~np.isnat(start_all[group_positions])]
        n, k = _prior_counts(start_all[known_start], end_all[known_end], onehot_all[known_end])
        target_n[known_start] = n
        target_counts[known_start] = k

    keys = [df["matchup_apertura"].astype(str).to_numpy(), df["TimeClass"].astype(str).to_numpy()]
    for _, group in pd.Series(positions).groupby(keys):
        _fill(group.to_numpy(), n_prev, counts)

    result = pd.DataFrame(index=df.index)
    result["n_previas_matchup"] = pd.array(n_prev, dtype="Int32")
    enough = n_prev >= min_prev
    result["historial_suficiente"] = enough

    if shrink_m is None:
        with np.errstate(invalid="ignore", divide="ignore"):
            rates = np.where(enough[:, None], counts / n_prev[:, None], np.nan)
    else:
        prior_n = np.full(len(df), np.nan)
        prior_counts = np.full((len(df), len(outcomes)), np.nan)
        for _, group in pd.Series(positions).groupby(df["TimeClass"].astype(str).to_numpy()):
            _fill(group.to_numpy(), prior_n, prior_counts)
        with np.errstate(invalid="ignore", divide="ignore"):
            prior_rate = prior_counts / prior_n[:, None]
            rates = (counts + shrink_m * prior_rate) / (n_prev[:, None] + shrink_m)

    for column, values in zip(RESULT_RATE_COLUMNS, rates.T):
        result[column] = values
    return result


class FeatureEngineer:
    """Genera features de ELO, apertura, ritmo de juego y calendario.

    Parameters
    ----------
    config : dict[str, Any]
        Configuración cargada desde ``config/config.yaml``. Se usa la clave
        ``elo`` (bandas de rating).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.bandas_elo = config["elo"]["bandas"]
        self.matchup_categorias = list(config["matchup_apertura"]["categorias"])
        self.min_partidas_previas = int(config["matchup_apertura"]["min_partidas_previas"])

    def add_elo_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``diferencia_elo`` y ``elo_promedio``."""
        df["diferencia_elo"] = df["WhiteElo"] - df["BlackElo"]
        df["elo_promedio"] = (df["WhiteElo"] + df["BlackElo"]) / 2
        return df

    def add_elo_banda(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``nivel_promedio`` categórico según ``elo_promedio``."""
        bins = [0] + [v[1] for v in self.bandas_elo.values()]
        labels = list(self.bandas_elo.keys())
        df["nivel_promedio"] = pd.cut(df["elo_promedio"], bins=bins, labels=labels)
        return df

    def add_upset_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``es_sorpresa``: 1 si ganó el jugador con menor ELO."""
        gano_blancas = df["resultado"] == "Gana Blancas"
        gano_negras = df["resultado"] == "Gana Negras"
        sorpresa_blancas = gano_blancas & (df["diferencia_elo"] < 0)
        sorpresa_negras = gano_negras & (df["diferencia_elo"] > 0)
        df["es_sorpresa"] = (sorpresa_blancas | sorpresa_negras).astype("int8")
        return df

    def add_opening_family(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``familia_apertura`` a partir de la letra inicial del código ECO.

        La clasificación ECO agrupa aperturas en 5 familias por letra:
        A (aperturas de flanco), B (semiabiertas salvo Francesa/Caro-Kann),
        C (abiertas + Francesa/Caro-Kann), D (cerradas), E (indias).
        """
        letra = df["ECO"].astype(str).str[0]
        mapping = {
            "A": "Flanco",
            "B": "Semiabierta",
            "C": "Abierta",
            "D": "Cerrada",
            "E": "India",
        }
        df["familia_apertura"] = pd.Categorical(
            letra.map(mapping).fillna("Desconocida"),
            categories=["Flanco", "Semiabierta", "Abierta", "Cerrada", "India", "Desconocida"],
        )
        return df

    def add_opening_matchup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``matchup_apertura``: primera jugada de blancas x respuesta de negras.

        Usa sólo los plies 1 y 2 de ``moves_text``, así que no arrastra la fuga del
        ECO de Chess.com (que se asigna mirando la línea completa). Las combinaciones
        fuera de la lista congelada del config caen en ``"otra"``.
        """
        first_moves = df["moves_text"].astype("string").str.extract(_FIRST_MOVES_RE)
        pair = first_moves[0] + "-" + first_moves[1]
        unparsed = int(pair.isna().sum())
        if unparsed:
            logger.warning("%d partidas sin primeras jugadas parseables: quedan en '%s'.", unparsed, MATCHUP_OTRA)
        categories = self.matchup_categorias + [MATCHUP_OTRA]
        df["matchup_apertura"] = pd.Categorical(
            pair.where(pair.isin(self.matchup_categorias), MATCHUP_OTRA),
            categories=categories,
        )
        return df

    def add_matchup_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega las tasas históricas de resultado del matchup (ver ``matchup_history``)."""
        history = matchup_history(df, self.min_partidas_previas)
        for column in history.columns:
            df[column] = history[column]
        logger.info(
            "Historial de matchup suficiente (>= %d previas) en %d de %d partidas (%.1f%%).",
            self.min_partidas_previas,
            int(history["historial_suficiente"].sum()),
            len(df),
            100 * history["historial_suficiente"].mean() if len(df) else 0.0,
        )
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica todas las transformaciones de feature engineering en orden."""
        logger.info("Generando features sobre %d partidas...", len(df))
        df = self.add_elo_features(df)
        df = self.add_elo_banda(df)
        df = self.add_upset_flag(df)
        df = self.add_opening_family(df)
        df = self.add_opening_matchup(df)
        df = self.add_matchup_history(df)
        logger.info("Features generadas: %s", list(df.columns))
        return df
