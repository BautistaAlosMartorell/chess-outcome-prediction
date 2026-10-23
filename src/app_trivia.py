"""Banco reproducible de trivia: partidas de test, sin selección por acierto."""
from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path

import chess.pgn
import numpy as np
import pandas as pd

from src.predict import RESULT_ORDER, model_input_frame, predecir


def candidatos_trivia(test: pd.DataFrame) -> pd.DataFrame:
    """Only ongoing reference cuts with both observed clocks are eligible."""
    candidates = test.loc[test.corte_ply.isin([20, 40, 60])].copy()
    candidates = candidates.loc[candidates[["reloj_blancas_seg", "reloj_negras_seg"]].notna().all(axis=1)]
    assert not candidates.duplicated(["GameUrl", "corte_ply"]).any()
    return candidates.sort_values(["GameUrl", "corte_ply"])


def construir_trivia(test, pred, games, paths, artifact, random_state, limit=60):
    candidates = candidatos_trivia(test)
    by_url = {url: group for url, group in candidates.groupby("GameUrl", sort=True)}
    rng = np.random.default_rng(random_state)
    urls = list(by_url)
    order = rng.permutation(len(urls))
    # Scan local archives once, keeping only eligible games; no network access.
    raw = {}
    for path in paths.values():
        for game in json.loads(Path(path).read_text(encoding="utf-8")).get("games", []):
            if game.get("url") in by_url:
                raw.setdefault(game["url"], game)
    metadata = games.set_index("GameUrl")
    assert metadata.index.is_unique
    probabilities = pred.set_index(["GameUrl", "corte_ply"])
    assert probabilities.index.is_unique
    cases, excluded = [], Counter()
    attempted = 0
    for i in order:
        if len(cases) >= limit:
            break
        attempted += 1
        url = urls[i]
        if url not in raw:
            excluded["sin_pgn_local"] += 1
            continue
        parsed = chess.pgn.read_game(io.StringIO(raw[url]["pgn"]))
        if parsed is None or parsed.errors:
            raise ValueError(f"PGN inválido en trivia: {url}")
        board, moves, clocks = parsed.board(), [], []
        positions = {0: board.fen()}
        for node in parsed.mainline():
            moves.append(board.san(node.move))
            board.push(node.move)
            clocks.append(node.clock())
            positions[len(moves)] = board.fen()
        eligible = [int(k) for k in by_url[url].corte_ply
                    if k < len(moves) and not chess.Board(positions[k]).is_game_over()]
        if not eligible:
            excluded["sin_posicion_no_terminal"] += 1
            continue
        cut = int(rng.choice(eligible))
        row = by_url[url].loc[by_url[url].corte_ply.eq(cut)].iloc[0]
        context = {key: row[key] for key in ["TimeClass", "tiempo_base_seg", "incremento_seg", "EsTorneo",
                                             "StartTime", "historial_blancas", "historial_negras"]}
        derived = artifact["resultado"].named_steps["historial"].transform(
            model_input_frame(pd.DataFrame([context]), artifact["columnas"])).iloc[0]
        ratings = {f"elo_{s}_previo": None if pd.isna(derived[f"elo_{s}_previo"]) else float(derived[f"elo_{s}_previo"])
                   for s in ("blancas", "negras")}
        curve = predecir(raw[url]["pgn"], context, artifact)
        point = curve.loc[curve.ply.eq(cut)].iloc[0]
        expected = probabilities.loc[(url, cut)]
        np.testing.assert_allclose([point[r] for r in RESULT_ORDER],
                                   [expected[c] for c in ["p_blancas", "p_empate", "p_negras"]], atol=1e-9, rtol=0)
        public_curve = [{"ply": int(r["ply"]), "gana_blancas": float(r["Gana Blancas"]),
                         "empate": float(r["Empate"]), "gana_negras": float(r["Gana Negras"]),
                         **({"plies_restantes": float(r["plies_restantes"])} if "plies_restantes" in r else {})}
                        for r in curve.to_dict("records") if r["ply"] <= 120]
        game = metadata.loc[url]
        analysis = {
            "partida": {"url": url, "fin": int(pd.Timestamp(game.EndTime).timestamp()), "ritmo": str(row.TimeClass),
                        "tiempo_base_seg": float(row.tiempo_base_seg), "incremento_seg": float(row.incremento_seg),
                        "blancas": {"usuario": str(game.White), "rating": ratings["elo_blancas_previo"]},
                        "negras": {"usuario": str(game.Black), "rating": ratings["elo_negras_previo"]},
                        "resultado": str(game.resultado)},
            "contexto": ratings, "final": str(game.Termination), "jugadas": moves, "relojes_seg": clocks,
            "curva": public_curve,
        }
        cases.append({"id": f"caso-{len(cases) + 1:03}", "ply": cut, "fen": positions[cut], "analisis": analysis})
    if len(cases) < 3:
        raise ValueError("Se necesitan al menos tres partidas elegibles para la trivia")
    index = {"casos": [c["id"] for c in cases], "semilla": int(random_state), "universo_test": int(test.GameUrl.nunique()),
             "partidas_con_corte_y_relojes": len(urls), "partidas_inspeccionadas": attempted, "exclusiones_en_sorteo": dict(excluded),
             "criterio": "Cortes 20/40/60 con ambos relojes, anteriores al final y no terminales. Sin filtrar por resultado, confianza o acierto."}
    return index, cases
