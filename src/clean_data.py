"""Parseo y limpieza de partidas obtenidas de la PubAPI de Chess.com."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)

_HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]$', re.MULTILINE)
_MOVE_NUMBER_RE = re.compile(r"^\d+\.(?:\.\.)?$")

# Debajo de este umbral la partida es un abandono o resultado administrativo
# inmediato (por ejemplo "ganó por abandono" tras la primera jugada), no una
# partida jugada: no aporta señal real a resultado ni a cantidad_jugadas.
MIN_PLIES = 5

# Chess.com embebe el username del ganador en el texto de Termination
# ("fulano won by resignation"), lo que vuelve la columna casi un identificador
# (cardinalidad ~ cantidad de filas). Se normaliza al motivo puro para que sea
# utilizable como categórica en EDA. El motivo se toma SOLO de la parte anclada
# ("... won by/on <motivo>" o "Game drawn by <motivo>"), nunca de un match suelto
# en cualquier lugar del string —así un username como "Timmy" no se lee como "time".
_TERMINATION_WON_RE = re.compile(r"\bwon (?:by|on) (.+)$", re.IGNORECASE)
_TERMINATION_DRAWN_RE = re.compile(r"\bdrawn by (.+)$", re.IGNORECASE)
_TERMINATION_ABANDON_RE = re.compile(r"abandon", re.IGNORECASE)

# Frases que no mapean 1:1 a snake_case, o que hay que distinguir a propósito.
_TERMINATION_ALIASES = {
    "abandonment": "abandoned",
    "game abandoned": "abandoned",
    "insufficient material": "insufficient_material",
    "50-move rule": "50-move_rule",
    "50 move rule": "50-move_rule",
    "threefold repetition": "repetition",
    # Empate: un jugador cae por tiempo pero el rival no tiene material para dar
    # mate. Es tablas, NO una victoria por tiempo: se marca aparte de "time".
    "timeout vs insufficient material": "timeout_vs_insufficient_material",
}


class DataCleaner:
    """Convierte los JSON crudos de Chess.com en una tabla tidy de partidas."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.time_classes = set(config["chess_com"]["time_classes"])

    @staticmethod
    def _opening_name(eco_url: str | None) -> str | None:
        """Convierte una URL ECO de Chess.com en un nombre de apertura legible."""
        if not eco_url:
            return None
        slug = unquote(urlparse(eco_url).path.rsplit("/", 1)[-1]).split("...", 1)[0]
        return slug.replace("-", " ").strip() or None

    def parse_game(self, game: dict[str, Any]) -> dict[str, Any] | None:
        """Extrae metadata y jugadas de un objeto de partida de Chess.com."""
        pgn = game.get("pgn")
        if not isinstance(pgn, str):
            return None

        headers = dict(_HEADER_RE.findall(pgn))
        if not headers:
            return None

        moves_text = _HEADER_RE.sub("", pgn).strip()
        moves_text = re.sub(r"\{[^}]*\}", "", moves_text)
        moves_text = re.sub(r"\s+", " ", moves_text).strip()
        moves_text = re.sub(r"\s*(1-0|0-1|1/2-1/2|\*)\s*$", "", moves_text).strip()

        eco_url = game.get("eco") or headers.get("ECOUrl")
        return {
            "GameUrl": game.get("url") or headers.get("Link"),
            "Event": headers.get("Event"),
            "Date": headers.get("Date"),
            "White": headers.get("White") or game.get("white", {}).get("username"),
            "Black": headers.get("Black") or game.get("black", {}).get("username"),
            "Result": headers.get("Result"),
            "WhiteElo": headers.get("WhiteElo") or game.get("white", {}).get("rating"),
            "BlackElo": headers.get("BlackElo") or game.get("black", {}).get("rating"),
            "Variant": "Standard" if game.get("rules") == "chess" else game.get("rules"),
            "TimeControl": game.get("time_control") or headers.get("TimeControl"),
            "TimeClass": game.get("time_class"),
            "ECO": headers.get("ECO"),
            "Opening": self._opening_name(eco_url),
            "Termination": headers.get("Termination"),
            "Rated": game.get("rated"),
            "moves_text": moves_text,
        }

    def parse_json_file(self, json_path: str | Path) -> pd.DataFrame:
        """Parsea un archivo crudo consolidado de un usuario."""
        with Path(json_path).open("r", encoding="utf-8") as file:
            payload = json.load(file)
        rows = [self.parse_game(game) for game in payload.get("games", [])]
        return pd.DataFrame(row for row in rows if row is not None)

    def parse_all(self, raw_paths: dict[str, Path]) -> tuple[pd.DataFrame, int]:
        """Parsea todos los archivos y elimina partidas repetidas entre usuarios."""
        dfs = []
        raw_row_count = 0
        for username, path in raw_paths.items():
            df = self.parse_json_file(path)
            raw_row_count += len(df)
            dfs.append(df)
            logger.info("Parseadas %d partidas de %s", len(df), username)

        if not dfs:
            raise ValueError("No hay archivos crudos para procesar")
        combined = pd.concat(dfs, ignore_index=True)
        duplicates = int(combined.duplicated(subset="GameUrl").sum())
        if duplicates:
            logger.info("Se eliminaron %d partidas repetidas entre usuarios.", duplicates)
            combined = combined.drop_duplicates(subset="GameUrl", keep="first")
        return combined, raw_row_count

    def parse_result(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convierte el resultado PGN al target categórico principal."""
        mapping = {"1-0": "Gana Blancas", "0-1": "Gana Negras", "1/2-1/2": "Empate"}
        df["resultado"] = df["Result"].map(mapping)
        return df

    def parse_numeric_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convierte ratings y control de tiempo a campos numéricos."""
        for col in ["WhiteElo", "BlackElo"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        tc_split = df["TimeControl"].astype("string").str.split("+", n=1, expand=True)
        df["tiempo_base_seg"] = pd.to_numeric(tc_split[0], errors="coerce")
        df["incremento_seg"] = (
            pd.to_numeric(tc_split[1], errors="coerce").fillna(0)
            if tc_split.shape[1] > 1
            else 0
        )
        return df

    def count_moves(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cuenta los medio-movimientos (plies) de cada partida."""

        def _count(moves_text: str) -> int:
            tokens = moves_text.split()
            return sum(
                not _MOVE_NUMBER_RE.match(token)
                and not token.startswith("$")
                and token not in {"1-0", "0-1", "1/2-1/2", "*"}
                for token in tokens
            )

        df["cantidad_jugadas"] = df["moves_text"].fillna("").apply(_count)
        return df

    @staticmethod
    def parse_date(df: pd.DataFrame) -> pd.DataFrame:
        """Convierte el header PGN ``Date`` a ``datetime``; deja ``NaT`` si no parsea.

        Chess.com a veces emite ``"????.??.??"`` u otras fechas incompletas. Se
        pasan a ``NaT`` acá para que ``filter_invalid_rows`` descarte esas filas,
        en vez de dejar que un nulo se cuele al dataset final.
        """
        df["Date"] = pd.to_datetime(df["Date"], format="%Y.%m.%d", errors="coerce")
        return df

    def filter_invalid_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Conserva partidas rated, estándar, con resultado, ratings, fecha y jugadas válidas.

        El umbral ``MIN_PLIES`` descarta además abandonos o resultados
        administrativos inmediatos (partidas cortadas en la primera o segunda
        jugada), que no son partidas jugadas y distorsionan la cola inferior
        de ``cantidad_jugadas``. Requiere que ``parse_date`` se haya corrido antes.
        """
        valid = (
            df["resultado"].notna()
            & df["WhiteElo"].notna()
            & df["BlackElo"].notna()
            & df["Date"].notna()
            & (df["Variant"] == "Standard")
            & df["TimeClass"].isin(self.time_classes)
            & (df["Rated"] == True)  # noqa: E712
            & (df["cantidad_jugadas"] >= MIN_PLIES)
        )
        return df.loc[valid].copy()

    @staticmethod
    def _termination_reason(text: str | None) -> str | None:
        """Extrae el motivo de finalización, sin el username del ganador.

        Lee el motivo solo de la parte anclada del texto de Chess.com
        (``"... won by/on X"`` o ``"Game drawn by X"``); todo lo demás cae en
        ``"abandoned"`` (formato ``"... won - game abandoned"``) o ``"otro"``.
        """
        if not isinstance(text, str):
            return None
        stripped = text.strip()
        match = _TERMINATION_WON_RE.search(stripped) or _TERMINATION_DRAWN_RE.search(stripped)
        if match is None:
            return "abandoned" if _TERMINATION_ABANDON_RE.search(stripped) else "otro"
        reason = match.group(1).strip().rstrip(".").lower()
        return _TERMINATION_ALIASES.get(reason, reason.replace(" ", "_"))

    def normalize_termination(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reemplaza ``Termination`` por su motivo puro (sin username embebido)."""
        df["Termination"] = df["Termination"].apply(self._termination_reason)
        return df

    def optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica tipos compactos al dataset limpio."""
        int_cols = [
            "WhiteElo",
            "BlackElo",
            "tiempo_base_seg",
            "incremento_seg",
            "cantidad_jugadas",
        ]
        for col in int_cols:
            df[col] = pd.to_numeric(df[col], downcast="integer")
        for col in ["resultado", "Termination", "ECO", "Opening", "Event", "TimeClass"]:
            df[col] = df[col].astype("category")
        # ``Date`` ya viene parseada desde ``parse_date``; se re-parsea solo si
        # ``optimize_dtypes`` se llamara sobre datos sin limpiar.
        if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = pd.to_datetime(df["Date"], format="%Y.%m.%d", errors="coerce")
        return df

    def clean(self, raw_paths: dict[str, Path]) -> tuple[pd.DataFrame, int]:
        """Ejecuta parseo, deduplicación, validación y limpieza."""
        df, raw_row_count = self.parse_all(raw_paths)
        df = self.parse_result(df)
        df = self.parse_numeric_fields(df)
        df = self.count_moves(df)
        df = self.parse_date(df)

        invalid_dates = int(df["Date"].isna().sum())
        if invalid_dates:
            logger.info("%d partidas descartadas por fecha inválida (p. ej. '????.??.??').", invalid_dates)

        df = self.filter_invalid_rows(df)
        df = self.normalize_termination(df)
        logger.info(
            "Limpieza completa: %d registros descargados -> %d partidas válidas (%.1f%%).",
            raw_row_count,
            len(df),
            100 * len(df) / raw_row_count if raw_row_count else 0.0,
        )
        return df, raw_row_count
