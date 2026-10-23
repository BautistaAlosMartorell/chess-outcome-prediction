"""Pruebas de la API de la app (sin red: Chess.com y el modelo son falsos)."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
from sklearn.dummy import DummyClassifier

from src.predict import LIVE, PRE_GAME, model_frame

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi.testclient import TestClient

    from api import chesscom
    from api.main import create_app, ritmo

PGN = '[Event "Live Chess"]\n[Result "1-0"]\n[Termination "ana won by resignation"]\n\n' \
      '1. e4 {[%clk 0:02:59]} 1... e5 {[%clk 0:02:58]} 2. Nf3 {[%clk 0:02:55]} 2... Nc6 {[%clk 0:02:50]} 1-0'


def _game(url: str, end: int, white: tuple[str, int, str], black: tuple[str, int, str], tc: str = "blitz") -> dict:
    return {
        "url": url, "end_time": end, "time_class": tc, "time_control": "180+2", "rules": "chess", "rated": True,
        "pgn": f'[UTCDate "1970.01.01"]\n[UTCTime "{datetime.fromtimestamp(end - 50, timezone.utc):%H:%M:%S}"]\n' + PGN,
        "white": {"username": white[0], "rating": white[1], "result": white[2]},
        "black": {"username": black[0], "rating": black[1], "result": black[2]},
    }


class FakeChessCom:
    """Ana's last games, newest first; Beto's history only has the game before g3."""

    GAMES = {
        "ana": [
            _game("g3", 300, ("ana", 1530, "win"), ("beto", 1490, "resigned")),
            _game("g2", 200, ("carla", 1600, "resigned"), ("ana", 1520, "win")),
            _game("g1", 100, ("ana", 1510, "timeout"), ("dani", 1400, "win")),
            _game("r1", 250, ("ana", 1300, "agreed"), ("eli", 1300, "agreed"), tc="rapid"),
        ],
        "beto": [_game("b0", 150, ("beto", 1480, "win"), ("fede", 1500, "checkmated"))],
    }

    def perfil(self, usuario):
        if usuario.lower() not in self.GAMES:
            raise chesscom.JugadorNoEncontrado(usuario)
        return {"username": usuario, "name": "Ana", "avatar": None, "url": f"https://www.chess.com/member/{usuario}"}

    def estadisticas(self, usuario):
        return {"chess_blitz": {"last": {"rating": 1530}}}

    def partidas(self, usuario, minimo=40, max_meses=3):
        if usuario.lower() not in self.GAMES:
            raise chesscom.JugadorNoEncontrado(usuario)
        return sorted(self.GAMES[usuario.lower()], key=lambda g: g["end_time"], reverse=True)


@unittest.skipUnless(HAS_FASTAPI, "la API necesita api/requirements.txt")
class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        columns = PRE_GAME + LIVE
        X = model_frame(pd.DataFrame({"TimeClass": ["blitz"] * 4}), columns)
        model = {"resultado": DummyClassifier(strategy="prior").fit(X, ["Gana Blancas", "Gana Blancas", "Empate", "Gana Negras"]),
                 "columnas": columns, "familia": "prueba"}
        self.client = TestClient(create_app(model, FakeChessCom()))

    def test_deployed_frontend_can_send_prediction_preflight(self) -> None:
        with patch.dict("os.environ", {"CORS_ORIGINS": "https://chess.example, https://preview.example"}):
            client = TestClient(create_app(self.client.app.state.modelo, FakeChessCom()))
        response = client.options("/predecir", headers={
            "Origin": "https://preview.example", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://preview.example")

    def test_unknown_frontend_is_not_granted_cors_access(self) -> None:
        response = self.client.options("/predecir", headers={
            "Origin": "https://unknown.example", "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_live_game_gets_one_point_per_ply_including_the_current_one(self) -> None:
        response = self.client.post("/predecir", json={
            "jugadas": ["e4", "e5", "Nf3"], "relojes_seg": [179, 178, 175], "tiempo_base_seg": 180, "incremento_seg": 2,
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ritmo"], "blitz")
        self.assertEqual([p["ply"] for p in body["curva"]], [0, 1, 2, 3])
        point = body["curva"][-1]
        self.assertAlmostEqual(point["gana_blancas"] + point["empate"] + point["gana_negras"], 1)
        self.assertAlmostEqual(point["gana_blancas"], 0.5)

    def test_illegal_move_or_missing_clock_is_rejected(self) -> None:
        illegal = self.client.post("/predecir", json={"jugadas": ["e4", "e4"], "tiempo_base_seg": 180, "incremento_seg": 0})
        self.assertEqual(illegal.status_code, 422)
        clocks = self.client.post("/predecir", json={"jugadas": ["e4"], "relojes_seg": [], "tiempo_base_seg": 180, "incremento_seg": 0})
        self.assertEqual(clocks.status_code, 422)

    def test_player_card_has_rating_and_recent_form(self) -> None:
        card = self.client.get("/jugadores/ana").json()
        self.assertEqual(card["ratings"]["blitz"], 1530)
        self.assertEqual(card["forma"]["blitz"], {"ultimas": ["G", "G", "P"], "racha": 2})
        self.assertEqual(card["forma"]["rapid"], {"ultimas": ["T"], "racha": 0})
        self.assertEqual(self.client.get("/jugadores/nadie").status_code, 404)

    def test_analysis_uses_the_rating_before_the_game_never_after(self) -> None:
        body = self.client.get("/jugadores/ana/analisis", params={"url": "g3"}).json()
        # Ana's rating after g2 (1520), not after g3 (1530); Beto's from his own history (1480).
        self.assertEqual(body["contexto"]["elo_blancas_previo"], 1520)
        self.assertEqual(body["contexto"]["elo_negras_previo"], 1480)
        # Ana's last blitz close (g2) was 50 s before g3 started; Beto's (b0), 100 s.
        self.assertAlmostEqual(body["contexto"]["antiguedad_rating_dias_blancas"], 50 / 86400)
        self.assertAlmostEqual(body["contexto"]["antiguedad_rating_dias_negras"], 100 / 86400)
        self.assertEqual(body["contexto"]["diferencia_elo_previa"], 1520 - 1480)
        self.assertEqual(body["jugadas"], ["e4", "e5", "Nf3", "Nc6"])
        self.assertEqual(body["relojes_seg"], [179, 178, 175, 170])
        self.assertEqual([p["ply"] for p in body["curva"]], [0, 1, 2, 3])  # finished: no point after the last move
        self.assertEqual(self.client.get("/jugadores/ana/analisis", params={"url": "otra"}).status_code, 404)

    def test_analysis_excludes_games_that_finished_after_the_target_started(self) -> None:
        games = {**FakeChessCom.GAMES, "ana": [*FakeChessCom.GAMES["ana"],
            _game("overlap", 275, ("ana", 9999, "win"), ("rival", 1000, "resigned")),
            _game("simultaneous", 250, ("ana", 8888, "win"), ("rival", 1000, "resigned"))]}
        self.client.app.state.cliente.GAMES = games
        response = self.client.get("/jugadores/ana/analisis", params={"url": "g3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contexto"]["elo_blancas_previo"], 1520)

    def test_analysis_derives_recent_form_from_earlier_games(self) -> None:
        target = _game("g3", 300, ("ana", 9999, "resigned"), ("beto", 1490, "win"))
        history = [_game(f"prior-{i}", 100 + i, ("ana", 1500 + i, "win"), ("rival", 1500, "resigned"))
                   for i in range(11)]
        self.client.app.state.cliente.GAMES = {**FakeChessCom.GAMES, "ana": [target, *history]}
        response = self.client.get("/jugadores/ana/analisis", params={"url": "g3"})
        self.assertEqual(response.status_code, 200)
        context = response.json()["contexto"]
        self.assertEqual(context["elo_blancas_previo"], 1510)
        self.assertEqual(context["forma_ultimas10_blancas"], 1)
        self.assertEqual(context["tendencia_rating_blancas"], 10)

    def test_live_import_passes_history_and_fixed_start_to_the_model(self) -> None:
        with patch("api.main.curva", return_value=[]) as predict:
            response = self.client.post("/predecir", json={
                "tiempo_base_seg": 180, "incremento_seg": 2,
                "usuario_blancas": "ana", "inicio_partida": "1970-01-01T00:04:10Z",
            })
        self.assertEqual(response.status_code, 200)
        context = predict.call_args.args[1]
        self.assertEqual(context["StartTime"].timestamp(), 250)
        self.assertEqual(len(context["historial_blancas"]), 4)
        self.assertTrue(all(isinstance(row, tuple) for row in context["historial_blancas"]))

    def test_rating_sent_by_the_caller_is_current_so_zero_days_old(self) -> None:
        with patch("api.main.curva", return_value=[]) as predict:
            self.client.post("/predecir", json={"tiempo_base_seg": 180, "incremento_seg": 2, "elo_blancas_previo": 1500})
        context = predict.call_args.args[1]
        self.assertEqual(context["antiguedad_rating_dias_blancas"], 0.0)
        self.assertNotIn("antiguedad_rating_dias_negras", context)

    def test_missing_start_never_uses_a_rating_from_before_the_finish(self) -> None:
        game = dict(FakeChessCom.GAMES["ana"][0], pgn=PGN)
        self.assertIsNone(chesscom.rating_previo(FakeChessCom.GAMES["ana"], game, "ana"))

    def test_health_reports_the_rating_range_seen_in_training(self) -> None:
        self.assertIsNone(self.client.get("/salud").json()["rango_rating"])  # model without it: no range
        self.client.app.state.modelo["rango_rating"] = [100.0, 3500.0]
        self.assertEqual(self.client.get("/salud").json()["rango_rating"], [100.0, 3500.0])

    def test_time_class_follows_chess_com(self) -> None:
        self.assertEqual([ritmo(60, 0), ritmo(180, 2), ritmo(300, 0), ritmo(600, 0)], ["bullet", "blitz", "blitz", "rapid"])



@unittest.skipUnless(HAS_FASTAPI, "la API necesita api/requirements.txt")
class ApiTrainingParityTest(unittest.TestCase):
    """The API builds histories from Chess.com archives; training, from the downloaded JSON.

    For real games between two selected accounts whose downloads (capped at 1.000 games
    per account) both cover the game and at least 11 earlier games of its rhythm, both
    sources hold the same observations, so the derived pre-game columns (and the model's
    probabilities) must coincide.
    """

    def test_real_games_get_the_same_history_columns_as_in_training(self) -> None:
        import json
        from itertools import islice
        from pathlib import Path

        import numpy as np

        from src.history_transformer import HISTORY_FEATURES, PlayerHistoryTransformer, attach_player_histories, player_history_payloads
        from src.player_selection import load_selection
        from src.predict import MODEL_PATH, cargar_modelo, predecir

        root = Path(__file__).resolve().parents[1]
        clean = root / "data/processed/partidas_ajedrez_clean.parquet"
        selected = load_selection(root / "config/jugadores_seleccionados.yaml")
        paths = {u.lower(): root / f"data/raw/chesscom_{u}_raw.json" for u in selected}
        if not clean.exists() or not all(path.exists() for path in paths.values()):
            self.skipTest("Regenerar los datos con el pipeline")
        games = pd.read_parquet(clean)
        both = games[games["White"].str.lower().isin(paths) & games["Black"].str.lower().isin(paths)].sort_values("GameUrl")
        raw_cache = {}

        def own_games(user):
            if user not in raw_cache:
                raw_cache[user] = json.loads(paths[user].read_text(encoding="utf-8"))["games"]
            return raw_cache[user]

        def covered(row):
            for user in (row["White"].lower(), row["Black"].lower()):
                archive = own_games(user)
                if not any(g["url"] == row["GameUrl"] for g in archive):
                    return False
                earlier = [g for g in archive if g["time_class"] == row["TimeClass"]
                           and g["end_time"] < row["StartTime"].timestamp()]
                if len(earlier) < 11:
                    return False
            return True

        picked = []
        for rhythm, group in both.groupby("TimeClass"):
            picked += list(islice((row for _, row in group.iterrows() if covered(row)), 2))
        sample = pd.DataFrame(picked)
        self.assertGreater(len(sample), 0)
        artifact = cargar_modelo(root / MODEL_PATH) if (root / MODEL_PATH).exists() else None
        for _, row in sample.iterrows():
            with self.subTest(url=row["GameUrl"]):
                users = [row["White"].lower(), row["Black"].lower()]
                subset = {u: paths[u] for u in users}
                raw = {u: own_games(u) for u in users}
                target = next(g for g in raw[users[0]] if g["url"] == row["GameUrl"])
                self.assertEqual(chesscom.inicio(target), row["StartTime"].to_pydatetime())
                training = attach_player_histories(
                    games[games["GameUrl"] == row["GameUrl"]],
                    player_history_payloads(subset, games[["GameUrl", "StartTime"]], rivales=True))
                api = training.copy()
                api["StartTime"] = chesscom.inicio(target)
                for side, user in zip(["blancas", "negras"], users):
                    api[f"historial_{side}"] = [chesscom.historial(raw[user], user)]
                derive = PlayerHistoryTransformer(HISTORY_FEATURES)
                pd.testing.assert_frame_equal(derive.fit_transform(api).reset_index(drop=True),
                                              derive.fit_transform(training).reset_index(drop=True))
                if artifact is not None:
                    context = {k: training.iloc[0][k] for k in ["TimeClass", "tiempo_base_seg", "incremento_seg", "EsTorneo",
                                                                "StartTime", "historial_blancas", "historial_negras"]}
                    api_context = dict(context, StartTime=api.iloc[0]["StartTime"],
                                       historial_blancas=api.iloc[0]["historial_blancas"],
                                       historial_negras=api.iloc[0]["historial_negras"])
                    np.testing.assert_allclose(predecir(target["pgn"], api_context, artifact).iloc[:, 1:4].to_numpy(),
                                               predecir(target["pgn"], context, artifact).iloc[:, 1:4].to_numpy(), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
