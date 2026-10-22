"""Revisa el modelo final mediante el endpoint real de análisis de la app.

python -m api.audit_predictions --snapshot /tmp/auditoria-app-fuentes.json \
    --output /tmp/auditoria-app.json
Una segunda ejecución reutiliza el snapshot sin consultar la red.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from fastapi.testclient import TestClient

from api.chesscom import ChessComClient
from api.main import create_app
from src.predict import FORM, cargar_modelo, predecir
from src.utils import load_config


class SnapshotClient(ChessComClient):
    """Capture public API responses, or replay an immutable local snapshot."""

    def __init__(self, user_agent: str, responses: dict, replay: bool):
        super().__init__(user_agent)
        self.responses, self.replay = responses, replay

    def _get(self, url):
        if url in self.responses:
            return self.responses[url]
        if self.replay:
            raise ValueError(f"URL ausente del snapshot: {url}")
        value = super()._get(url)
        self.responses[url] = value
        return value


def run(snapshot: Path, output: Path, active_accounts: bool = False):
    root = Path(__file__).resolve().parents[1]
    artifact = cargar_modelo(root / "models/modelo_en_vivo.joblib")
    replay = snapshot.exists()
    source = json.loads(snapshot.read_text()) if replay else {"responses": {}, "captured_at": datetime.now(timezone.utc).isoformat()}
    client = SnapshotClient(load_config(root / "config/config.yaml")["chess_com"]["user_agent"], source["responses"], replay)
    selected = yaml.safe_load((root / "config/jugadores_seleccionados.yaml").read_text())["selected"]
    if active_accounts:
        local = pd.read_parquet(root / "data/processed/partidas_ajedrez_clean.parquet", columns=["White", "Black", "EndTime"])
        latest = pd.concat([local[[color, "EndTime"]].rename(columns={color: "user"}) for color in ["White", "Black"]])
        latest = latest.assign(user=latest["user"].str.lower()).groupby("user")["EndTime"].max()
        selected = {level: sorted(accounts, key=lambda user: latest.get(user.lower(), pd.Timestamp("1900-01-01", tz="UTC")), reverse=True)
                    for level, accounts in selected.items()}
    results = []
    try:
        with TestClient(create_app(modelo=artifact, cliente=client)) as http:
            for level, accounts in selected.items():
                user = accounts[0]
                print(f"Revisando app: {level}, {user}...", flush=True)
                games = client.partidas(user)
                if not games:
                    results.append(dict(nivel=level, usuario=user, error="Sin partidas elegibles"))
                    continue
                # Include the latest game and the largest displayed rating gap among
                # the latest 40; posterior ratings select examples only, never predict.
                candidates = [games[0], max(games[:40], key=lambda g: abs(g["white"]["rating"] - g["black"]["rating"]))]
                for game in {g["url"]: g for g in candidates}.values():
                    response = http.get(f"/jugadores/{user}/analisis", params={"url": game["url"]})
                    response.raise_for_status()
                    result = response.json()
                    context = result["contexto"]
                    start = result["curva"][0]
                    p = np.array([start[k] for k in ["gana_blancas", "empate", "gana_negras"]])
                    all_p = np.array([[point[k] for k in ["gana_blancas", "empate", "gana_negras"]] for point in result["curva"]])
                    assert np.isfinite(all_p).all() and (all_p >= 0).all() and (all_p <= 1).all()
                    np.testing.assert_allclose(all_p.sum(axis=1), 1, atol=1e-9)
                    # Replay the endpoint's public pre-game context through the model.
                    base = dict(context, TimeClass=game["time_class"],
                        tiempo_base_seg=result["partida"]["tiempo_base_seg"],
                        incremento_seg=result["partida"]["incremento_seg"], EsTorneo="tournament" in game)
                    direct = predecir(game["pgn"], base, artifact)
                    np.testing.assert_allclose(direct[["Gana Blancas", "Empate", "Gana Negras"]], all_p, atol=1e-12)
                    missing = dict(base)
                    for column in FORM:
                        missing[column] = None
                    no_form = predecir(game["pgn"], missing, artifact).iloc[0]
                    # Realistic one-minute perturbation changes only White's pause.
                    changed = dict(base)
                    pause = changed.get("minutos_desde_anterior_blancas")
                    pause_shift = None
                    if pause is not None:
                        changed["minutos_desde_anterior_blancas"] += 1
                        pause_shift = 100 * (predecir(game["pgn"], changed, artifact).iloc[0]["Gana Blancas"] - p[0])
                    results.append(dict(nivel_muestra=level, usuario=user, url=game["url"],
                        blancas=game["white"]["username"], negras=game["black"]["username"],
                        ritmo=game["time_class"], contexto=context, resultado=result["partida"]["resultado"],
                        inicial=start, sin_forma={k: float(no_form[k]) for k in ["Gana Blancas", "Empate", "Gana Negras"]},
                        un_minuto_mas_blancas_pp=pause_shift,
                        cortes=[point for point in result["curva"] if point["ply"] in [20, 60]],
                        n_plies=len(result["jugadas"]), paridad_api_modelo=True))
    finally:
        if not replay:
            snapshot.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    output.write_text(json.dumps(dict(captured_at=source["captured_at"], active_accounts=active_accounts, partidas=results), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resultados de la app: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path("/tmp/auditoria-app-fuentes.json"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/auditoria-app.json"))
    parser.add_argument("--active-accounts", action="store_true", help="Elegir la cuenta con cierre local más reciente por banda")
    args = parser.parse_args()
    run(args.snapshot, args.output, args.active_accounts)
