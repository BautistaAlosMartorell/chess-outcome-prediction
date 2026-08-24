"""Parseo y limpieza de partidas de ajedrez en formato PGN (Lichess).

Esquema real verificado contra un PGN descargado a mano de
``/api/games/user/{username}``: cada partida es un bloque de encabezados
``[Clave "Valor"]`` seguido de una línea en blanco y la lista de jugadas en
notación algebraica estándar, terminada en el resultado (``1-0``, ``0-1``,
``1/2-1/2``) y separada de la siguiente partida por una línea en blanco.

No se usa ``python-chess`` (dependencia pesada para lo que hace falta acá):
los encabezados PGN son líneas simples ``[Clave "Valor"]``, parseables con
una regex, y no hace falta reproducir el tablero para las features de este
proyecto (no se analiza la calidad de las jugadas, solo metadata de la
partida).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)

_HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]$', re.MULTILINE)

# Encabezados PGN que interesan para este dataset; el resto (Site, GameId,
# UTCDate/UTCTime -- redundantes con Date) se descarta.
_RELEVANT_HEADERS = [
    "Event",
    "Date",
    "White",
    "Black",
    "Result",
    "WhiteElo",
    "BlackElo",
    "WhiteRatingDiff",
    "BlackRatingDiff",
    "Variant",
    "TimeControl",
    "ECO",
    "Opening",
    "Termination",
]


class DataCleaner:
    """Parsea PGNs crudos de Lichess y arma un dataset tidy, una fila por partida.

    Parameters
    ----------
    config : dict[str, Any]
        Configuración cargada desde ``config/config.yaml``.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def split_games(self, pgn_text: str) -> list[str]:
        """Separa un archivo PGN con múltiples partidas en bloques individuales."""
        blocks = re.split(r"\n\n\n+", pgn_text.strip())
        return [b for b in blocks if b.strip()]

    def parse_game(self, game_text: str) -> dict[str, Any] | None:
        """Parsea un bloque PGN de una partida a un diccionario de columnas.

        Returns
        -------
        dict[str, Any] or None
            ``None`` si el bloque no tiene encabezados parseables (partida
            corrupta o incompleta en el stream).
        """
        headers = dict(_HEADER_RE.findall(game_text))
        if not headers:
            return None

        moves_text = _HEADER_RE.sub("", game_text).strip()
        moves_text = re.sub(r"\{[^}]*\}", "", moves_text)  # strip clock/eval annotations
        moves_text = re.sub(r"\s+", " ", moves_text).strip()
        moves_text = re.sub(r"\s*(1-0|0-1|1/2-1/2|\*)\s*$", "", moves_text).strip()

        row = {h: headers.get(h) for h in _RELEVANT_HEADERS}
        row["moves_text"] = moves_text
        return row

    def parse_pgn_file(self, pgn_path: str | Path) -> pd.DataFrame:
        """Parsea un archivo PGN completo (todas las partidas de un usuario)."""
        pgn_path = Path(pgn_path)
        text = pgn_path.read_text(encoding="utf-8")
        games = self.split_games(text)

        rows = []
        for game_text in games:
            parsed = self.parse_game(game_text)
            if parsed is not None:
                rows.append(parsed)

        return pd.DataFrame(rows)

    def parse_all(self, pgn_paths: dict[str, Path]) -> tuple[pd.DataFrame, int]:
        """Parsea los PGNs de todos los usuarios descargados y los concatena.

        Parameters
        ----------
        pgn_paths : dict[str, Path]
            Mapeo usuario -> ruta al PGN descargado (salida de
            ``DataDownloader.download_all``).

        Returns
        -------
        tuple[pd.DataFrame, int]
            DataFrame concatenado (una fila por partida) y la cantidad total
            de bloques de partida leídos, antes de cualquier filtro.
        """
        dfs = []
        raw_row_count = 0
        for username, path in pgn_paths.items():
            df = self.parse_pgn_file(path)
            raw_row_count += len(df)
            dfs.append(df)
            logger.info("Parseadas %d partidas de %s", len(df), username)

        combined = pd.concat(dfs, ignore_index=True)
        return combined, raw_row_count

    def parse_result(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convierte ``Result`` (PGN: 1-0/0-1/1/2-1/2) a ``resultado`` categórico."""
        mapping = {"1-0": "Gana Blancas", "0-1": "Gana Negras", "1/2-1/2": "Empate"}
        df["resultado"] = df["Result"].map(mapping)
        return df

    def parse_numeric_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convierte ELO, diferencia de rating y control de tiempo a numérico."""
        for col in ["WhiteElo", "BlackElo", "WhiteRatingDiff", "BlackRatingDiff"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # TimeControl viene como "300+3" (segundos base + incremento por jugada).
        tc_split = df["TimeControl"].str.split("+", expand=True)
        df["tiempo_base_seg"] = pd.to_numeric(tc_split[0], errors="coerce")
        df["incremento_seg"] = pd.to_numeric(tc_split[1], errors="coerce") if tc_split.shape[1] > 1 else 0
        return df

    def count_moves(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cuenta la cantidad de jugadas (medio-movimientos / 2) de cada partida."""
        # moves_text tiene tokens de numeración ("1.", "2.", ...) intercalados
        # con las jugadas; contar tokens que no son número+punto da los plies.
        def _count(moves_text: str) -> int:
            tokens = moves_text.split()
            plies = [t for t in tokens if not re.match(r"^\d+\.$", t)]
            return len(plies)

        df["cantidad_jugadas"] = df["moves_text"].apply(_count)
        return df

    def filter_invalid_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Descarta partidas sin resultado válido, sin ELO, o con variante no estándar."""
        valid = (
            df["resultado"].notna()
            & df["WhiteElo"].notna()
            & df["BlackElo"].notna()
            & (df["Variant"] == "Standard")
            & (df["cantidad_jugadas"] > 0)
        )
        return df.loc[valid].copy()

    def optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica downcasting de tipos para reducir el uso de memoria."""
        int_cols = ["WhiteElo", "BlackElo", "tiempo_base_seg", "incremento_seg", "cantidad_jugadas"]
        for col in int_cols:
            df[col] = pd.to_numeric(df[col], downcast="integer")
        for col in ["WhiteRatingDiff", "BlackRatingDiff"]:
            df[col] = pd.to_numeric(df[col], downcast="integer")
        for col in ["resultado", "Termination", "ECO", "Opening", "Event"]:
            df[col] = df[col].astype("category")
        df["Date"] = pd.to_datetime(df["Date"], format="%Y.%m.%d", errors="coerce")
        return df

    def clean(self, pgn_paths: dict[str, Path]) -> tuple[pd.DataFrame, int]:
        """Ejecuta el pipeline completo de parseo y limpieza sobre los PGNs crudos.

        Parameters
        ----------
        pgn_paths : dict[str, Path]
            Mapeo usuario -> ruta al PGN descargado.

        Returns
        -------
        tuple[pd.DataFrame, int]
            DataFrame limpio (sin downcasting todavía) y la cantidad total de
            partidas leídas de los PGN crudos, antes de cualquier filtro.
        """
        df, raw_row_count = self.parse_all(pgn_paths)
        df = self.parse_result(df)
        df = self.parse_numeric_fields(df)
        df = self.count_moves(df)
        df = self.filter_invalid_rows(df)
        logger.info(
            "Limpieza completa: %d partidas crudas -> %d partidas válidas (%.1f%% retenidas).",
            raw_row_count,
            len(df),
            100 * len(df) / raw_row_count if raw_row_count else 0.0,
        )
        return df, raw_row_count
