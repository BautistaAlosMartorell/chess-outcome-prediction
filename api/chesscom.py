"""Cliente de la PubAPI de Chess.com para la app: la ficha de un jugador y sus partidas.

La app no depende de la lista de jugadores del DAG: consulta cualquier usuario en el
momento. Las respuestas se guardan unos minutos en memoria para no repetir requests, y
se manda el User-Agent identificable del config, como pide Chess.com.

Mismas reglas que el pipeline: partidas rated de ajedrez estándar en bullet, blitz o
rapid. El rating que trae cada partida es **posterior** a ella (lleva el resultado
adentro), así que el rating previo de una partida es el de la partida anterior del mismo
jugador en ese ritmo, igual que en ``src/rating_history.py``.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

import requests

from src.rating_history import DRAW_RESULTS

BASE_URL = "https://api.chess.com/pub/player"
RITMOS = ("bullet", "blitz", "rapid")
FORMA_VENTANA = 10


class JugadorNoEncontrado(LookupError):
    """El usuario no existe en Chess.com (la PubAPI respondió 404)."""


class ChessComClient:
    """GETs a la PubAPI con caché en memoria por URL."""

    def __init__(self, user_agent: str, ttl_seconds: float = 300, timeout: float = 15,
                 session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.ttl_seconds = ttl_seconds
        self.timeout = timeout
        self._cache: dict[str, tuple[float, Any]] = {}

    def _get(self, url: str) -> Any:
        cached = self._cache.get(url)
        if cached is not None and time.monotonic() - cached[0] < self.ttl_seconds:
            return cached[1]
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code == 404:
            raise JugadorNoEncontrado(url)
        response.raise_for_status()
        payload = response.json()
        self._cache[url] = (time.monotonic(), payload)
        return payload

    def perfil(self, usuario: str) -> dict[str, Any]:
        return self._get(f"{BASE_URL}/{usuario.lower()}")

    def estadisticas(self, usuario: str) -> dict[str, Any]:
        return self._get(f"{BASE_URL}/{usuario.lower()}/stats")

    def partidas(self, usuario: str, minimo: int = 40, max_meses: int = 3) -> list[dict[str, Any]]:
        """Partidas válidas de los últimos meses, de la más nueva a la más vieja.

        Recorre los archivos mensuales hacia atrás hasta juntar ``minimo`` partidas o
        ``max_meses`` meses: alcanza para la forma reciente y el rating previo.
        """
        archives = self._get(f"{BASE_URL}/{usuario.lower()}/games/archives").get("archives", [])
        games: list[dict[str, Any]] = []
        for month_url in reversed(archives[-max_meses:]):
            games.extend(g for g in self._get(month_url).get("games", []) if es_valida(g))
            if len(games) >= minimo:
                break
        return sorted(games, key=lambda g: (g.get("end_time", 0), g.get("url", "")), reverse=True)


def es_valida(game: dict[str, Any]) -> bool:
    """Mismo alcance que el dataset: rated, ajedrez estándar, bullet/blitz/rapid, con PGN."""
    return (
        game.get("rules") == "chess" and bool(game.get("rated")) and game.get("time_class") in RITMOS
        and bool(game.get("pgn"))
    )


def color_de(game: dict[str, Any], usuario: str) -> str | None:
    for color in ("white", "black"):
        if str(game.get(color, {}).get("username", "")).lower() == usuario.lower():
            return color
    return None


def resultado(game: dict[str, Any]) -> str:
    if game["white"].get("result") == "win":
        return "Gana Blancas"
    if game["black"].get("result") == "win":
        return "Gana Negras"
    return "Empate"


def puntaje(game: dict[str, Any], color: str) -> str:
    """G (ganó), T (tablas) o P (perdió), desde el lado de ``color``."""
    code = game[color].get("result")
    if code == "win":
        return "G"
    return "T" if code in DRAW_RESULTS else "P"


def control_de_tiempo(game: dict[str, Any]) -> tuple[float, float]:
    """Tiempo base e incremento en segundos, de ``time_control`` (``"180+2"``)."""
    base, _, increment = str(game.get("time_control", "")).partition("+")
    return float(base), float(increment or 0)


def rating_previo(partidas: Iterable[dict[str, Any]], game: dict[str, Any], usuario: str) -> float | None:
    """Rating de ``usuario`` al cerrar su partida anterior del mismo ritmo (None si no está)."""
    previas = [
        g for g in partidas
        if g.get("time_class") == game.get("time_class") and g.get("end_time", 0) < game.get("end_time", 0)
        and color_de(g, usuario) is not None
    ]
    if not previas:
        return None
    anterior = max(previas, key=lambda g: g.get("end_time", 0))
    return float(anterior[color_de(anterior, usuario)]["rating"])


def ficha(usuario: str, perfil: dict[str, Any], estadisticas: dict[str, Any],
          partidas: list[dict[str, Any]]) -> dict[str, Any]:
    """Lo que la app muestra de un jugador: rating actual y forma reciente por ritmo."""
    ratings, forma = {}, {}
    for ritmo in RITMOS:
        ratings[ritmo] = estadisticas.get(f"chess_{ritmo}", {}).get("last", {}).get("rating")
        propias = [g for g in partidas if g["time_class"] == ritmo]
        ultimas = [puntaje(g, color_de(g, usuario)) for g in propias[:FORMA_VENTANA]]
        racha = 0
        for p in ultimas:  # newest first: count the run of equal decisive results
            if p == "T" or (racha and p != ultimas[0]):
                break
            racha += 1
        forma[ritmo] = {"ultimas": ultimas, "racha": racha if ultimas and ultimas[0] == "G" else -racha}
    return {
        "usuario": perfil.get("username", usuario),
        "nombre": perfil.get("name"),
        "avatar": perfil.get("avatar"),
        "url": perfil.get("url"),
        "titulo": perfil.get("title"),
        "ratings": ratings,
        "forma": forma,
    }


def resumen(game: dict[str, Any]) -> dict[str, Any]:
    """Una partida para el listado (los ratings son los posteriores: sólo se muestran)."""
    base, increment = control_de_tiempo(game)
    return {
        "url": game["url"],
        "fin": game.get("end_time"),
        "ritmo": game["time_class"],
        "tiempo_base_seg": base,
        "incremento_seg": increment,
        "blancas": {"usuario": game["white"]["username"], "rating": game["white"].get("rating")},
        "negras": {"usuario": game["black"]["username"], "rating": game["black"].get("rating")},
        "resultado": resultado(game),
    }
