"""Ingeniería de features sobre partidas de ajedrez (vectorizado)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)


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

    def add_elo_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``diferencia_elo``, ``elo_promedio`` y ``favorito``."""
        df["diferencia_elo"] = df["WhiteElo"] - df["BlackElo"]
        df["elo_promedio"] = (df["WhiteElo"] + df["BlackElo"]) / 2
        df["favorito"] = pd.Categorical(
            np.select(
                [df["diferencia_elo"] > 0, df["diferencia_elo"] < 0],
                ["Blancas", "Negras"],
                default="Ninguno",
            ),
            categories=["Blancas", "Negras", "Ninguno"],
        )
        return df

    def add_elo_banda(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``nivel_promedio`` categórico según ``elo_promedio``."""
        bins = [0] + [v[1] for v in self.bandas_elo.values()]
        labels = list(self.bandas_elo.keys())
        df["nivel_promedio"] = pd.cut(df["elo_promedio"], bins=bins, labels=labels)
        return df

    def add_time_control_category(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega ``modalidad`` usando la clasificación provista por Chess.com."""
        mapping = {"bullet": "Bullet", "blitz": "Blitz", "rapid": "Rapid"}
        df["modalidad"] = pd.Categorical(
            df["TimeClass"].astype("string").map(mapping),
            categories=["Bullet", "Blitz", "Rapid"],
        )
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

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica todas las transformaciones de feature engineering en orden."""
        logger.info("Generando features sobre %d partidas...", len(df))
        df = self.add_elo_features(df)
        df = self.add_elo_banda(df)
        df = self.add_time_control_category(df)
        df = self.add_upset_flag(df)
        df = self.add_opening_family(df)
        logger.info("Features generadas: %s", list(df.columns))
        return df
