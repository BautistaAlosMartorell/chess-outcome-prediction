"""Rating previo a la partida, reconstruido desde el historial propio de cada cuenta.

``WhiteElo``/``BlackElo`` son el rating **posterior** a la partida (sección 9 del
notebook 02: el signo del cambio de rating coincide con el resultado de esa misma
partida en el 99,91 % de los casos), así que llevan el resultado adentro.

El rating previo de un jugador en una partida es su rating al cierre de su partida
anterior del mismo ``time_class``. Eso sólo se puede leer para las cuentas cuyo
historial se descargó (las seleccionadas): del rival casi nunca hay historial, y ese
lado queda NaN. No se imputa: un valor inventado sería peor que declararlo faltante.

Del mismo historial sale la **forma reciente** del jugador (``reconstruct_recent_form``):
puntaje de las últimas partidas, racha, tendencia del rating y si viene de una sesión
larga. Con la misma regla anti-fuga: para una partida sólo se miran partidas propias que
terminaron antes de que empiece.
"""

from __future__ import annotations

import json
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


def _score(result: object) -> float | None:
    """Puntaje del jugador en una partida: 1 ganó, 0,5 tablas, 0 perdió."""
    if not isinstance(result, str):
        return None
    if result == "win":
        return 1.0
    return 0.5 if result in DRAW_RESULTS else 0.0


def own_game_history(raw_paths: Mapping[str, Path]) -> pd.DataFrame:
    """Una fila por partida propia de cada cuenta descargada, con su rating posterior y su puntaje."""
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

    Todo se calcula con ``shift()`` sobre partidas ordenadas por cierre, así que la
    partida actual nunca entra en su propia fila. Sin historial suficiente queda NaN, no 0.
    """
    history = own_game_history(raw_paths)
    per_class = history.groupby(["username", "time_class"])
    previous_score = per_class["puntaje"].shift()
    history["forma_ultimas10"] = previous_score.groupby([history["username"], history["time_class"]]).transform(
        lambda scores: scores.rolling(FORM_WINDOW, min_periods=FORM_WINDOW).mean()
    )
    streak_after = per_class["puntaje"].transform(_streak_after_each_game)
    history["racha"] = streak_after.groupby([history["username"], history["time_class"]]).shift()
    history["tendencia_rating"] = per_class["rating_posterior"].shift() - per_class["rating_posterior"].shift(FORM_WINDOW + 1)

    # Sessions mix time classes: order each account by close time across all of them.
    starts = start_times[["GameUrl", "StartTime"]].drop_duplicates("GameUrl")
    start_seconds = (starts["StartTime"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
    start_by_url = pd.Series(start_seconds.to_numpy(), index=starts["GameUrl"])
    by_account = history.sort_values(["username", "end_time", "GameUrl"], kind="stable")
    # Games outside the tidy table have no StartTime: their close time is the safe stand-in.
    start = by_account["GameUrl"].map(start_by_url).fillna(by_account["end_time"])
    previous_end = by_account.groupby("username")["end_time"].shift()
    gap_minutes = (start - previous_end) / 60
    new_session = gap_minutes.isna() | (gap_minutes >= SESSION_GAP_MINUTES)
    session_id = new_session.groupby(by_account["username"]).cumsum()
    history["minutos_desde_anterior"] = gap_minutes
    history["partidas_sesion"] = by_account.groupby([by_account["username"], session_id]).cumcount()

    # Same pivot as reconstruct_prior_ratings: one row per (GameUrl, color) before pivoting.
    per_side = history.drop_duplicates(["GameUrl", "color"])
    form = per_side.pivot(index="GameUrl", columns="color", values=FORM_COLUMNS)
    form.columns = [f"{column}_{'blancas' if color == 'white' else 'negras'}" for column, color in form.columns]
    ordered = [f"{column}_{suffix}" for column in FORM_COLUMNS for suffix in ("blancas", "negras")]
    form = form.reindex(columns=ordered).reset_index()
    logger.info(
        "Forma reciente: %d partidas con historial de 10 previas de al menos un lado.",
        int(form[["forma_ultimas10_blancas", "forma_ultimas10_negras"]].notna().any(axis=1).sum()),
    )
    return form


def add_recent_form(df: pd.DataFrame, form: pd.DataFrame) -> pd.DataFrame:
    """Une la forma reciente al dataset por ``GameUrl`` (muchos a uno, sin fan-out)."""
    assert form["GameUrl"].is_unique, "La forma reciente debe tener una fila por partida"
    rows_before = len(df)
    merged = df.merge(form, on="GameUrl", how="left", validate="many_to_one")
    assert len(merged) == rows_before, "Fan-out detectado al unir la forma reciente"
    return merged
