"""API de la app: el modelo de la Entrega 3 jugada a jugada, más la PubAPI de Chess.com.

Desde la raíz del repo, con el modelo ya generado por ``notebooks/04_modelado.ipynb``::

    pip install -r requirements.txt -r api/requirements.txt
    uvicorn api.main:app --reload

El frontend (``web/``) la llama en ``http://localhost:8000``. No hay otra fuente de
features: todo pasa por ``src.predict.predecir``, la misma función que el notebook
verificó contra el camino de entrenamiento.
"""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import chess
import chess.pgn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import chesscom
from src.predict import MODEL_PATH, RESULT_ORDER, cargar_modelo, predecir
from src.utils import load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURVE_KEYS = {"Gana Blancas": "gana_blancas", "Empate": "empate", "Gana Negras": "gana_negras"}


def ritmo(base_seg: float, incremento_seg: float) -> str:
    """Ritmo con la regla de Chess.com: duración estimada = base + 40 × incremento."""
    estimated = base_seg + 40 * incremento_seg
    if estimated < 180:
        return "bullet"
    return "blitz" if estimated < 600 else "rapid"


def pgn_de_jugadas(jugadas: list[str], relojes_seg: list[float] | None) -> str:
    """PGN con ``%clk`` a partir de jugadas en SAN; una jugada ilegal es un 422."""
    board, game = chess.Board(), chess.pgn.Game()
    node: chess.pgn.GameNode = game
    for i, san in enumerate(jugadas):
        try:
            move = board.parse_san(san)
        except ValueError as error:
            raise HTTPException(422, f"Jugada ilegal en el ply {i + 1}: {san}") from error
        board.push(move)
        node = node.add_variation(move)
        if relojes_seg is not None:
            node.set_clock(relojes_seg[i])
    game.headers["Result"] = "*"
    return str(game)


def curva(pgn: str, contexto: dict[str, Any], modelo: dict[str, Any], en_curso: bool) -> list[dict[str, Any]]:
    """La predicción de cada ply, con nombres de campo para el frontend."""
    prediction = predecir(pgn, contexto, modelo, en_curso=en_curso)
    points = []
    for row in prediction.to_dict(orient="records"):
        point = {"ply": int(row["ply"]), **{CURVE_KEYS[label]: float(row[label]) for label in RESULT_ORDER}}
        if "plies_restantes" in row:
            point["plies_restantes"] = float(row["plies_restantes"])
        points.append(point)
    return points


class PedidoJugar(BaseModel):
    """Una partida que se está jugando en la app, hasta la última jugada."""

    jugadas: list[str] = Field(default_factory=list, description="Jugadas en SAN desde la posición inicial")
    relojes_seg: list[float] | None = Field(None, description="Reloj de quien movió, después de cada jugada")
    tiempo_base_seg: float = Field(gt=0)
    incremento_seg: float = Field(ge=0)
    elo_blancas_previo: float | None = None
    elo_negras_previo: float | None = None
    en_curso: bool = True


def create_app(modelo: dict[str, Any] | None = None, cliente: chesscom.ChessComClient | None = None) -> FastAPI:
    """La app con el modelo y el cliente dados; si faltan, se cargan al arrancar."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.modelo is None:
            path = PROJECT_ROOT / MODEL_PATH
            if not path.exists():
                raise RuntimeError(f"No está {MODEL_PATH}: correr notebooks/04_modelado.ipynb para generarlo")
            app.state.modelo = cargar_modelo(path)
        if app.state.cliente is None:
            config = load_config(PROJECT_ROOT / "config" / "config.yaml")
            app.state.cliente = chesscom.ChessComClient(config["chess_com"]["user_agent"])
        yield

    app = FastAPI(title="Ajedrez en vivo", lifespan=lifespan)
    app.state.modelo, app.state.cliente = modelo, cliente
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"],
    )

    def jugador(fetch):
        try:
            return fetch()
        except chesscom.JugadorNoEncontrado as error:
            raise HTTPException(404, "No existe ese usuario en Chess.com") from error

    @app.get("/salud")
    def salud() -> dict[str, Any]:
        modelo_actual = app.state.modelo
        return {"modelo": modelo_actual.get("familia"), "entrenado_hasta": modelo_actual.get("entrenado_hasta"),
                "columnas": len(modelo_actual["columnas"]), "rango_rating": modelo_actual.get("rango_rating")}

    @app.post("/predecir")
    def predecir_partida(pedido: PedidoJugar) -> dict[str, Any]:
        if pedido.relojes_seg is not None and len(pedido.relojes_seg) != len(pedido.jugadas):
            raise HTTPException(422, "Tiene que haber un reloj por jugada")
        contexto = {
            "TimeClass": ritmo(pedido.tiempo_base_seg, pedido.incremento_seg),
            "tiempo_base_seg": pedido.tiempo_base_seg,
            "incremento_seg": pedido.incremento_seg,
            "EsTorneo": False,
            "elo_blancas_previo": pedido.elo_blancas_previo,
            "elo_negras_previo": pedido.elo_negras_previo,
        }
        pgn = pgn_de_jugadas(pedido.jugadas, pedido.relojes_seg)
        return {"ritmo": contexto["TimeClass"], "curva": curva(pgn, contexto, app.state.modelo, pedido.en_curso)}

    @app.get("/jugadores/{usuario}")
    def ficha(usuario: str) -> dict[str, Any]:
        cliente = app.state.cliente
        return jugador(lambda: chesscom.ficha(
            usuario, cliente.perfil(usuario), cliente.estadisticas(usuario), cliente.partidas(usuario)
        ))

    @app.get("/jugadores/{usuario}/partidas")
    def partidas(usuario: str, limite: int = Query(20, ge=1, le=50)) -> list[dict[str, Any]]:
        games = jugador(lambda: app.state.cliente.partidas(usuario))
        return [chesscom.resumen(g) for g in games[:limite]]

    @app.get("/jugadores/{usuario}/analisis")
    def analisis(usuario: str, url: str) -> dict[str, Any]:
        """Una partida terminada del usuario, jugada a jugada, con la curva del modelo."""
        cliente = app.state.cliente
        games = jugador(lambda: cliente.partidas(usuario))
        game = next((g for g in games if g["url"] == url), None)
        if game is None:
            raise HTTPException(404, "Esa partida no está entre las últimas del usuario")
        base, increment = chesscom.control_de_tiempo(game)
        contexto = {"TimeClass": game["time_class"], "tiempo_base_seg": base, "incremento_seg": increment,
                    "EsTorneo": "tournament" in game}
        for color, side in (("white", "blancas"), ("black", "negras")):
            player = game[color]["username"]
            try:
                history = games if player.lower() == usuario.lower() else cliente.partidas(player)
            except (chesscom.JugadorNoEncontrado, OSError):
                history = []  # a closed or unreachable account: its prior rating stays unknown
            contexto[f"elo_{side}_previo"] = chesscom.rating_previo(history, game, player)

        parsed = chess.pgn.read_game(io.StringIO(game["pgn"]))
        jugadas, relojes, board = [], [], parsed.board()
        for node in parsed.mainline():
            jugadas.append(board.san(node.move))
            board.push(node.move)
            relojes.append(node.clock())
        return {
            "partida": chesscom.resumen(game),
            "contexto": contexto,
            "final": parsed.headers.get("Termination"),
            "jugadas": jugadas,
            "relojes_seg": relojes,
            "curva": curva(game["pgn"], contexto, app.state.modelo, en_curso=False),
        }

    return app


app = create_app()
