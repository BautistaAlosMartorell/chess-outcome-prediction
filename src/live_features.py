"""Dataset de predicción en vivo: una fila por (partida, corte de medio-movimientos).

El Parquet tidy tiene una fila por partida y no se toca. Esta tabla derivada reproduce
cada partida jugada a jugada con python-chess desde el PGN **crudo** (el único lugar
donde quedan los relojes ``%clk``; ``moves_text`` ya los perdió) y guarda, en cada
corte, sólo lo que un observador podía ver en ese instante: la posición y los relojes.

Regla anti-fuga: ninguna feature de un corte ``k`` puede depender de una jugada
posterior a ``k``. Los targets (``resultado`` y ``plies_restantes``) sí miran el final,
porque son lo que se quiere predecir. El contexto de la partida (ritmo, matchup,
historial) no se copia acá: se une desde el Parquet tidy por ``GameUrl``.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import chess
import chess.pgn
import pandas as pd

from src.utils import setup_logger

logger = setup_logger(__name__)

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
# 2 × (2 caballos + 2 alfiles + 2 torres + dama) = 2 × (6 + 6 + 10 + 9)
MAX_NON_PAWN_MATERIAL = 62
# Ventana para el tiempo gastado reciente: las últimas 5 jugadas propias (10 plies).
RECENT_OWN_MOVES = 5

COLOR_SUFFIX = {chess.WHITE: "blancas", chess.BLACK: "negras"}


def _material(board: chess.Board, color: chess.Color) -> tuple[int, int]:
    """Material total y material sin peones de un bando, en puntos clásicos."""
    total = non_pawn = 0
    for piece_type, value in PIECE_VALUES.items():
        points = value * len(board.pieces(piece_type, color))
        total += points
        if piece_type != chess.PAWN:
            non_pawn += points
    return total, non_pawn


def _hanging_material(board: chess.Board, color: chess.Color) -> int:
    """Puntos de las piezas de ``color`` atacadas por el rival y sin ningún defensor."""
    hanging = 0
    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        if board.is_attacked_by(not color, square) and not board.is_attacked_by(color, square):
            hanging += PIECE_VALUES[piece.piece_type]
    return hanging


def _king_attacks(board: chess.Board, color: chess.Color) -> int:
    """Ataques rivales sobre la casilla del rey de ``color`` y las que lo rodean."""
    king = board.king(color)
    if king is None:
        return 0
    zone = chess.SquareSet(chess.BB_KING_ATTACKS[king]) | chess.SquareSet(chess.BB_SQUARES[king])
    return sum(len(board.attackers(not color, square)) for square in zone)


def _passed_pawns(board: chess.Board, color: chess.Color) -> int:
    """Peones de ``color`` sin peones rivales delante, en su columna ni en las vecinas."""
    enemy_pawns = board.pieces(chess.PAWN, not color)
    passed = 0
    for square in board.pieces(chess.PAWN, color):
        file, rank = chess.square_file(square), chess.square_rank(square)
        ahead = range(rank + 1, 8) if color == chess.WHITE else range(rank - 1, -1, -1)
        blockers = (chess.square(f, r) for f in (file - 1, file, file + 1) if 0 <= f < 8 for r in ahead)
        passed += not any(blocker in enemy_pawns for blocker in blockers)
    return passed


def _side_mobility(board: chess.Board, color: chess.Color) -> int:
    """Jugadas pseudo-legales de ``color`` en la posición, le toque mover o no."""
    view = board.copy(stack=False)
    view.turn = color
    return view.pseudo_legal_moves.count()


def _recent_time_spent(clocks: list[float], increment: float) -> float | None:
    """Segundos gastados en las últimas ``RECENT_OWN_MOVES`` jugadas propias.

    ``clocks`` arranca con el tiempo base y suma el reloj después de cada jugada
    propia. Lo gastado es lo que bajó el reloj más los incrementos recibidos.
    """
    if len(clocks) <= RECENT_OWN_MOVES:
        return None
    return clocks[-1 - RECENT_OWN_MOVES] - clocks[-1] + RECENT_OWN_MOVES * increment


def game_cut_features(
    pgn: str,
    cuts: Iterable[int],
    base_seconds: float,
    increment_seconds: float,
) -> tuple[list[dict[str, Any]], int]:
    """Features de posición y reloj en cada corte alcanzado por la partida.

    Devuelve las filas de los cortes ``k`` con ``k`` estrictamente menor que la
    cantidad total de plies (en el ply ``k`` la partida sigue en curso) y esa
    cantidad total, para validarla contra ``cantidad_jugadas``. El corte 0 es la
    posición inicial con los relojes completos: ahí ``gasto_reciente_*`` queda NaN
    porque todavía no hubo jugadas.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("PGN ilegible")
    cut_set = set(cuts)
    last_cut = max(cut_set)

    board = game.board()
    checks = {chess.WHITE: 0, chess.BLACK: 0}
    captures = {chess.WHITE: 0, chess.BLACK: 0}
    castled = {chess.WHITE: False, chess.BLACK: False}
    promotions = 0
    clocks: dict[chess.Color, list[float]] = {chess.WHITE: [base_seconds], chess.BLACK: [base_seconds]}
    clocks_complete = True
    snapshots: dict[int, dict[str, Any]] = {}
    if 0 in cut_set:
        # Cut 0 is the game before the first move: what is known pre-game.
        snapshots[0] = _snapshot(
            board, 0, checks, captures, castled, 0, clocks, base_seconds, increment_seconds,
        )

    ply = 0
    for node in game.mainline():
        ply += 1
        if ply > last_cut:
            continue  # only count the remaining plies: nothing after the last cut is read
        move = node.move
        mover = board.turn
        captures[mover] += board.is_capture(move)
        castled[mover] |= board.is_castling(move)
        promotions += move.promotion is not None
        board.push(move)
        checks[mover] += board.is_check()
        clock = node.clock()
        if clock is None:
            clocks_complete = False
        else:
            clocks[mover].append(clock)

        if ply in cut_set:
            snapshots[ply] = _snapshot(
                board, ply, checks, captures, castled, promotions,
                clocks if clocks_complete else None, base_seconds, increment_seconds,
            )

    rows = [snapshots[k] for k in sorted(snapshots) if k < ply]
    return rows, ply


def _snapshot(
    board: chess.Board,
    ply: int,
    checks: dict[chess.Color, int],
    captures: dict[chess.Color, int],
    castled: dict[chess.Color, bool],
    promotions: int,
    clocks: dict[chess.Color, list[float]] | None,
    base_seconds: float,
    increment_seconds: float,
) -> dict[str, Any]:
    """Foto de la posición y los relojes después de ``ply`` medio-movimientos."""
    row: dict[str, Any] = {
        "corte_ply": ply,
        "turno_blancas": board.turn == chess.WHITE,
        "en_jaque": board.is_check(),
        "movilidad": board.legal_moves.count(),
        "promociones": promotions,
    }
    non_pawn_total = 0
    for color, suffix in COLOR_SUFFIX.items():
        total, non_pawn = _material(board, color)
        non_pawn_total += non_pawn
        row[f"material_{suffix}"] = total
        row[f"jaques_{suffix}"] = checks[color]
        row[f"capturas_{suffix}"] = captures[color]
        row[f"enroco_{suffix}"] = castled[color]
        row[f"derechos_enroque_{suffix}"] = board.has_castling_rights(color)
        # Position quality beyond the material count: what a player reads off the board.
        row[f"material_colgado_{suffix}"] = _hanging_material(board, color)
        row[f"ataques_al_rey_{suffix}"] = _king_attacks(board, color)
        row[f"peones_pasados_{suffix}"] = _passed_pawns(board, color)
        row[f"movilidad_{suffix}"] = _side_mobility(board, color)
        if clocks is None:
            row[f"reloj_{suffix}_seg"] = None
            row[f"reloj_frac_{suffix}"] = None
            row[f"gasto_reciente_{suffix}_seg"] = None
        else:
            remaining = clocks[color][-1]
            row[f"reloj_{suffix}_seg"] = remaining
            row[f"reloj_frac_{suffix}"] = remaining / base_seconds if base_seconds else None
            row[f"gasto_reciente_{suffix}_seg"] = _recent_time_spent(clocks[color], increment_seconds)
    row["balance_material"] = row["material_blancas"] - row["material_negras"]
    row["material_no_peon_frac"] = non_pawn_total / MAX_NON_PAWN_MATERIAL
    if clocks is None:
        row["diferencia_reloj_seg"] = None
    else:
        row["diferencia_reloj_seg"] = row["reloj_blancas_seg"] - row["reloj_negras_seg"]
    return row


def _iter_raw_games(raw_paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    for path in raw_paths:
        with Path(path).open("r", encoding="utf-8") as file:
            yield from json.load(file).get("games", [])


def build_cut_dataset(clean_df: pd.DataFrame, raw_paths: Iterable[Path], cuts: Iterable[int]) -> pd.DataFrame:
    """Arma la tabla (partida, corte) para las partidas del Parquet tidy.

    Cada ``GameUrl`` del Parquet tiene que encontrar exactamente un PGN crudo y su
    cantidad de plies reproducida tiene que coincidir con ``cantidad_jugadas``; si no,
    se corta con un error que lista los casos (no se descartan en silencio).
    """
    cuts = sorted(set(int(c) for c in cuts))
    games = clean_df.set_index("GameUrl")[["tiempo_base_seg", "incremento_seg", "cantidad_jugadas", "resultado"]]
    pending = set(games.index)

    rows: list[dict[str, Any]] = []
    ply_mismatches: list[tuple[str, int, int]] = []
    for game in _iter_raw_games(raw_paths):
        url = game.get("url")
        if url not in pending:
            continue  # outside the clean universe, or already seen from another account
        pending.discard(url)
        info = games.loc[url]
        game_rows, total_plies = game_cut_features(
            game["pgn"], cuts, float(info["tiempo_base_seg"]), float(info["incremento_seg"])
        )
        if total_plies != int(info["cantidad_jugadas"]):
            ply_mismatches.append((url, total_plies, int(info["cantidad_jugadas"])))
        for row in game_rows:
            row["GameUrl"] = url
        rows.extend(game_rows)

    if pending:
        raise ValueError(f"{len(pending)} partidas del Parquet sin PGN crudo, por ejemplo {sorted(pending)[:3]}")
    if ply_mismatches:
        raise ValueError(
            f"{len(ply_mismatches)} partidas con plies reproducidos != cantidad_jugadas, "
            f"por ejemplo {ply_mismatches[:3]}"
        )

    cut_df = pd.DataFrame(rows)
    targets = clean_df[["GameUrl", "resultado", "cantidad_jugadas"]]
    rows_before = len(cut_df)
    # Many-to-one on the unique key GameUrl: the row count must not change.
    cut_df = cut_df.merge(targets, on="GameUrl", how="left", validate="many_to_one")
    assert len(cut_df) == rows_before, "Fan-out detectado al unir los targets"
    cut_df["plies_restantes"] = cut_df["cantidad_jugadas"] - cut_df["corte_ply"]
    cut_df = cut_df.drop(columns="cantidad_jugadas")

    assert not cut_df.duplicated(["GameUrl", "corte_ply"]).any(), "Clave (GameUrl, corte_ply) repetida"
    assert (cut_df["plies_restantes"] > 0).all(), "Un corte no puede estar en o después del final"
    front = ["GameUrl", "corte_ply", "resultado", "plies_restantes"]
    cut_df = cut_df[front + [c for c in cut_df.columns if c not in front]]
    # Same reason as the tidy table: the order must not depend on the order of raw_paths.
    cut_df = cut_df.sort_values(["GameUrl", "corte_ply"], kind="stable").reset_index(drop=True)
    logger.info(
        "Dataset de cortes: %d filas de %d partidas; filas por corte: %s",
        len(cut_df), cut_df["GameUrl"].nunique(), cut_df["corte_ply"].value_counts().sort_index().to_dict(),
    )
    return cut_df
