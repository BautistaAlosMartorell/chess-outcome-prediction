"""Rating previo a la partida, reconstruido desde el historial propio de cada cuenta.

``WhiteElo``/``BlackElo`` son el rating **posterior** a la partida (sección 9 del
notebook 02: el signo del cambio de rating coincide con el resultado de esa misma
partida en el 99,93 % de los casos), así que llevan el resultado adentro.

El rating previo de un jugador en una partida es su rating al cierre de su partida
anterior del mismo ``time_class``. Eso sólo se puede leer para las cuentas cuyo
historial se descargó (las seleccionadas): del rival casi nunca hay historial, y ese
lado queda NaN. La reconstrucción no inventa un rating; si el estimador necesita
imputación, se ajusta después y sólo con su entrenamiento.

Del mismo historial sale la **forma reciente** del jugador (``reconstruct_recent_form``):
puntaje de las últimas partidas, racha, tendencia del rating y si viene de una sesión
larga. Con la misma regla anti-fuga: para una partida sólo se miran partidas propias que
terminaron antes de que empiece.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)

# Códigos de ``result`` de la PubAPI que cuentan como tablas para el jugador. ``win`` vale 1
# y cualquier otro código (resigned, timeout, checkmated, abandoned...) es una derrota.
DRAW_RESULTS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}
# Forma reciente: ventana de partidas previas del mismo ritmo.
FORM_WINDOW = 10
# Una sesión es una seguidilla de partidas con huecos menores a esto entre una y otra.
SESSION_GAP_MINUTES = 30
FORM_COLUMNS = ["forma_ultimas10", "racha", "tendencia_rating", "minutos_desde_anterior", "partidas_sesion"]
# Estilo con el reloj: ventana más larga que la forma, porque una derrota por tiempo es
# rara y con 10 partidas la tasa sería casi siempre 0 o 10 %.
STYLE_WINDOW = 20
STYLE_COLUMNS = ["derrotas_por_tiempo", "reloj_final"]
_CLOCK_RE = re.compile(r"\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]")


def _score(result: object) -> float | None:
    """Puntaje del jugador en una partida: 1 ganó, 0,5 tablas, 0 perdió."""
    if not isinstance(result, str):
        return None
    if result == "win":
        return 1.0
    return 0.5 if result in DRAW_RESULTS else 0.0


def _final_clock_fraction(game: dict, color: str) -> float | None:
    """Reloj de ``color`` al terminar la partida, como fracción del tiempo base.

    Lee las anotaciones ``%clk`` del PGN: blancas tiene las de índice par y negras las
    impares. Sin relojes o sin tiempo base, None.
    """
    base = str(game.get("time_control", "")).partition("+")[0]
    if not base.replace(".", "", 1).isdigit() or float(base) <= 0:
        return None
    clocks = [int(h) * 3600 + int(m) * 60 + float(s) for h, m, s in _CLOCK_RE.findall(game.get("pgn", ""))]
    own = clocks[0::2] if color == "white" else clocks[1::2]
    return own[-1] / float(base) if own else None


def own_game_history(raw_paths: Mapping[str, Path]) -> pd.DataFrame:
    """Una fila por partida propia de cada cuenta descargada: rating posterior, puntaje y reloj."""
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
                            "puntaje": _score(side.get("result")),
                            # Chess.com's "timeout" is a loss on time ("timevsinsufficient" is a draw).
                            "por_tiempo": side.get("result") == "timeout",
                            "reloj_final_frac": _final_clock_fraction(game, color),
                        }
                    )
                    break
    history = pd.DataFrame(rows).dropna(subset=["rating_posterior", "end_time"])
    return history.sort_values(["username", "time_class", "end_time", "GameUrl"], kind="stable").reset_index(drop=True)


def game_observations(raw_paths: Mapping[str, Path]) -> pd.DataFrame:
    """Partidas propias más una observación de sólo rating del rival en cada partida.

    Cada partida descargada trae el rating del rival al cerrar: es una observación de
    su rating, aunque de él no se tenga la secuencia de partidas. Esas filas llevan
    ``propia=False`` y no aportan puntaje ni reloj: sólo sirven para el rating previo y
    su antigüedad, nunca para forma, racha, sesión ni estilo. Se deduplica por cuenta y
    ``GameUrl`` (la misma partida puede estar en dos archivos) prefiriendo la propia.
    """
    own = own_game_history(raw_paths).assign(propia=True)
    rows = []
    for username, path in raw_paths.items():
        with Path(path).open("r", encoding="utf-8") as file:
            games = json.load(file).get("games", [])
        for game in games:
            colors = {color: str(game.get(color, {}).get("username", "")).lower() for color in ("white", "black")}
            if username.lower() not in colors.values():
                continue
            for color, rival in colors.items():
                if rival and rival != username.lower():
                    rows.append({
                        "username": rival, "GameUrl": game.get("url"), "color": color,
                        "time_class": game.get("time_class"), "end_time": game.get("end_time"),
                        "rating_posterior": game[color].get("rating"), "puntaje": None,
                        "por_tiempo": False, "reloj_final_frac": None, "propia": False,
                    })
    rivals = pd.DataFrame(rows, columns=own.columns).dropna(subset=["rating_posterior", "end_time", "GameUrl"])
    observations = pd.concat([own, rivals], ignore_index=True)
    before = len(observations)
    observations = observations.sort_values("propia", ascending=False, kind="stable").drop_duplicates(["username", "GameUrl"])
    assert not observations.duplicated(["username", "GameUrl"]).any()
    logger.info("Observaciones de rating: %d propias, %d sólo rating de rivales (%d duplicadas descartadas).",
                int(observations["propia"].sum()), int((~observations["propia"]).sum()), before - len(observations))
    return observations.sort_values(["username", "time_class", "end_time", "GameUrl"], kind="stable").reset_index(drop=True)


def reconstruct_prior_ratings(
    raw_paths: Mapping[str, Path], start_times: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Rating previo de blancas y negras por ``GameUrl`` (NaN donde no hay historial).

    Devuelve una fila por partida con al menos un lado reconstruible y las columnas
    ``elo_blancas_previo`` y ``elo_negras_previo``. Si los dos jugadores son cuentas
    seleccionadas, cada lado sale del historial de su propia cuenta. Para modelado,
    pasar ``start_times``: excluye cierres iguales o posteriores al inicio actual.
    Sin horarios conserva el diagnóstico legado de cierre anterior, que no garantiza
    disponibilidad al inicio y no debe alimentar el modelo.
    """
    if start_times is not None:
        return _history_features_at_start(raw_paths, start_times, ["elo_blancas_previo", "elo_negras_previo"])
    # Legacy diagnostic: previous closure, without a known start. Modeling must pass
    # start_times to exclude overlapping games and equal timestamps.
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


def _streak_after_each_game(scores: pd.Series) -> pd.Series:
    """Racha al cierre de cada partida: +n victorias seguidas, -n derrotas, 0 tras tablas."""
    streaks = []
    current = 0
    for score in scores:
        if pd.isna(score) or score == 0.5:
            current = 0
        elif score == 1:
            current = current + 1 if current > 0 else 1
        else:
            current = current - 1 if current < 0 else -1
        streaks.append(current)
    return pd.Series(streaks, index=scores.index, dtype="float64")


def reconstruct_recent_form(raw_paths: Mapping[str, Path], start_times: pd.DataFrame) -> pd.DataFrame:
    """Forma reciente de blancas y negras por ``GameUrl`` (NaN donde no hay historial).

    ``start_times`` trae ``GameUrl`` y ``StartTime`` del Parquet tidy (la PubAPI no publica
    el inicio de las partidas en vivo). Por lado (``_blancas`` / ``_negras``):

    - ``forma_ultimas10``: puntaje medio de las 10 partidas previas del mismo ritmo.
    - ``racha``: victorias (+) o derrotas (-) seguidas que trae al empezar, mismo ritmo.
    - ``tendencia_rating``: rating previo menos el de 10 partidas antes, mismo ritmo.
    - ``minutos_desde_anterior``: desde que terminó su partida anterior (cualquier ritmo).
    - ``partidas_sesion``: partidas previas de la sesión, con huecos de menos de
      ``SESSION_GAP_MINUTES`` minutos entre una y otra (cualquier ritmo).

    Y el estilo con el reloj, en las ``STYLE_WINDOW`` partidas previas del mismo ritmo:

    - ``derrotas_por_tiempo``: qué fracción perdió por quedarse sin reloj.
    - ``reloj_final``: con qué fracción del tiempo base suele terminar (bajo = juega apurado).

    Se consulta el historial con ``EndTime < StartTime`` mediante el mismo transformador
    del Pipeline. Se excluyen cierres simultáneos, partidas solapadas y futuras.
    Sin historial suficiente queda NaN, no 0.
    """
    columns = [f"{column}_{side}" for column in FORM_COLUMNS + STYLE_COLUMNS for side in ("blancas", "negras")]
    return _history_features_at_start(raw_paths, start_times, columns)


def _history_features_at_start(raw_paths, start_times, columns):
    """Compatibilidad para el EDA: el mismo transformador causal que usa el modelo."""
    from src.history_transformer import PlayerHistoryTransformer, attach_player_histories, player_history_payloads

    history = own_game_history(raw_paths)
    accounts = history.drop_duplicates(["GameUrl", "color"]).pivot(index="GameUrl", columns="color", values="username")
    accounts = accounts.reindex(columns=["white", "black"]).rename(columns={"white": "White", "black": "Black"})
    rhythm = history.drop_duplicates("GameUrl").set_index("GameUrl")["time_class"]
    accounts["TimeClass"] = rhythm
    starts = start_times.set_index("GameUrl")["StartTime"]
    assert starts.index.is_unique, "Un inicio por partida"
    accounts["StartTime"] = accounts.index.map(starts)
    # Raw games excluded from the tidy table have no observed start. Their close is
    # a conservative diagnostic fallback, never used as a modeled game.
    ends = history.drop_duplicates("GameUrl").set_index("GameUrl")["end_time"]
    accounts["StartTime"] = accounts["StartTime"].fillna(pd.Series(pd.to_datetime(accounts.index.map(ends), unit="s", utc=True), index=accounts.index))
    payloads = player_history_payloads(raw_paths, start_times)
    inputs = attach_player_histories(accounts, payloads)
    features = PlayerHistoryTransformer(columns).fit_transform(inputs)
    features.index.name = "GameUrl"
    return features.reset_index()


def add_recent_form(df: pd.DataFrame, form: pd.DataFrame) -> pd.DataFrame:
    """Une la forma reciente al dataset por ``GameUrl`` (muchos a uno, sin fan-out)."""
    assert form["GameUrl"].is_unique, "La forma reciente debe tener una fila por partida"
    rows_before = len(df)
    merged = df.merge(form, on="GameUrl", how="left", validate="many_to_one")
    assert len(merged) == rows_before, "Fan-out detectado al unir la forma reciente"
    return merged
