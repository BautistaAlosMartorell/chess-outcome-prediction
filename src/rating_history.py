"""Rating previo a la partida, reconstruido desde el historial propio de cada cuenta.

``WhiteElo``/``BlackElo`` son el rating **posterior** a la partida (sección 9 del
notebook 02: el signo del cambio de rating coincide con el resultado de esa misma
partida en el 99,91 % de los casos), así que llevan el resultado adentro.

El rating previo de un jugador en una partida es su rating al cierre de su partida
anterior del mismo ``time_class``. Eso sólo se puede leer para las cuentas cuyo
historial se descargó (las seleccionadas): del rival casi nunca hay historial, y ese
lado queda NaN. No se imputa: un valor inventado sería peor que declararlo faltante.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)


def own_game_history(raw_paths: Mapping[str, Path]) -> pd.DataFrame:
    """Una fila por partida propia de cada cuenta descargada, con su rating posterior."""
    rows = []
    for username, path in raw_paths.items():
        with Path(path).open("r", encoding="utf-8") as file:
            games = json.load(file).get("games", [])
        for game in games:
            for color in ("white", "black"):
                side = game.get(color)
                if isinstance(side, dict) and str(side.get("username", "")).lower() == username.lower():
                    rows.append(
                        {
                            "username": username.lower(),
                            "GameUrl": game.get("url"),
                            "color": color,
                            "time_class": game.get("time_class"),
                            "end_time": game.get("end_time"),
                            "rating_posterior": side.get("rating"),
                        }
                    )
                    break
    history = pd.DataFrame(rows).dropna(subset=["rating_posterior", "end_time"])
    return history.sort_values(["username", "time_class", "end_time", "GameUrl"], kind="stable").reset_index(drop=True)


def reconstruct_prior_ratings(raw_paths: Mapping[str, Path]) -> pd.DataFrame:
    """Rating previo de blancas y negras por ``GameUrl`` (NaN donde no hay historial).

    Devuelve una fila por partida con al menos un lado reconstruible y las columnas
    ``elo_blancas_previo`` y ``elo_negras_previo``. Si los dos jugadores son cuentas
    seleccionadas, cada lado sale del historial de su propia cuenta.
    """
    history = own_game_history(raw_paths)
    history["rating_previo"] = history.groupby(["username", "time_class"])["rating_posterior"].shift()
    known = history.dropna(subset=["rating_previo"])

    # The same game can appear in two accounts' files (they played each other): one row
    # per (GameUrl, color) must remain, otherwise the pivot below would silently pick one.
    per_side = known.drop_duplicates(["GameUrl", "color"])
    assert not per_side.duplicated(["GameUrl", "color"]).any()
    prior = per_side.pivot(index="GameUrl", columns="color", values="rating_previo")
    prior = prior.rename(columns={"white": "elo_blancas_previo", "black": "elo_negras_previo"})
    prior = prior.reindex(columns=["elo_blancas_previo", "elo_negras_previo"]).reset_index()
    prior.columns.name = None
    logger.info(
        "Rating previo reconstruido: blancas en %d partidas, negras en %d.",
        int(prior["elo_blancas_previo"].notna().sum()),
        int(prior["elo_negras_previo"].notna().sum()),
    )
    return prior


def add_prior_ratings(df: pd.DataFrame, prior: pd.DataFrame) -> pd.DataFrame:
    """Une el rating previo al dataset por ``GameUrl`` (muchos a uno, sin fan-out)."""
    assert prior["GameUrl"].is_unique, "El rating previo debe tener una fila por partida"
    rows_before = len(df)
    merged = df.merge(prior, on="GameUrl", how="left", validate="many_to_one")
    assert len(merged) == rows_before, "Fan-out detectado al unir el rating previo"
    merged["diferencia_elo_previo"] = merged["elo_blancas_previo"] - merged["elo_negras_previo"]
    return merged
