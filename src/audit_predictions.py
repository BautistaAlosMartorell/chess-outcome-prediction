"""Auditoría descriptiva del artefacto vigente, sin entrenar ni consultar la red.

Ejecutar desde la raíz: python -m src.audit_predictions --output /tmp/auditoria.json
Las probabilidades se contrastan con frecuencias de grupos, no con un único ganador.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.history_transformer import attach_player_histories, player_history_payloads
from src.live_features import game_cut_features
from src.player_selection import load_selection
from src.predict import FORM, MODEL_PATH, RESULT_ORDER, cargar_modelo, model_input_frame


LEVELS = ["principiante", "intermedio", "avanzado", "experto", "top_mundial", "elite"]


def summarize(frame: pd.DataFrame, groups: list[str]) -> list[dict]:
    """One equally weighted observation per game within each reported cut/group."""
    output = []
    for key, group in frame.groupby(groups, observed=True, dropna=False, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        p = group[[f"p{i}" for i in range(3)]].to_numpy()
        y = group["resultado"].astype(str).to_numpy()
        actual = y[:, None] == np.asarray(RESULT_ORDER)[None, :]
        row = dict(zip(groups, (str(v) for v in key)))
        row.update(n=len(group), log_loss=float(-np.log(np.clip(p[actual], 1e-15, 1)).mean()))
        row["brier"] = float(np.square(p - actual).sum(axis=1).mean())
        for i, label in enumerate(["blancas", "tablas", "negras"]):
            row[f"pred_{label}"] = float(p[:, i].mean())
            row[f"real_{label}"] = float(actual[:, i].mean())
        row["max_error_pp"] = float(100 * np.abs(p.mean(axis=0) - actual.mean(axis=0)).max())
        if "duration_pred" in group:
            row["mae_plies"] = float((group["duration_pred"] - group["plies_restantes"]).abs().mean())
            row["duration_bias_plies"] = float((group["duration_pred"] - group["plies_restantes"]).mean())
        output.append(row)
    return output


def run(root: Path) -> dict:
    artifact_path = root / MODEL_PATH
    artifact = cargar_modelo(artifact_path)
    classifier = artifact["resultado"]
    columns = artifact["columnas"]
    games = pd.read_parquet(root / "data/processed/partidas_ajedrez_clean.parquet")
    assert games["GameUrl"].is_unique
    future = games[games["StartTime"] >= pd.Timestamp(artifact["entrenado_hasta"])].copy()
    paths = {u: root / f"data/raw/chesscom_{u}_raw.json"
             for u in load_selection(root / "config/jugadores_seleccionados.yaml")}
    print("Derivando historiales causales...", flush=True)
    histories = player_history_payloads(paths, games[["GameUrl", "StartTime"]])
    all_context = attach_player_histories(games, histories)
    context = all_context[all_context["StartTime"] >= pd.Timestamp(artifact["entrenado_hasta"])].copy()
    training = all_context[all_context["EndTime"] < pd.Timestamp(artifact["entrenado_hasta"])]
    training_derived = classifier.named_steps["historial"].transform(model_input_frame(training, columns))
    training_ratings = training_derived[["elo_blancas_previo", "elo_negras_previo"]]
    cuts = pd.read_parquet(root / "data/processed/partidas_cortes.parquet")
    cuts = cuts[cuts["GameUrl"].isin(future["GameUrl"]) & cuts["corte_ply"].isin([0, 20, 60])]
    assert not cuts.duplicated(["GameUrl", "corte_ply"]).any()
    fixed = ["GameUrl", "TimeClass", "tiempo_base_seg", "incremento_seg", "EsTorneo",
             "StartTime", "historial_blancas", "historial_negras", "White", "Black"]
    count = len(cuts)
    rows = cuts.merge(context[fixed], on="GameUrl", how="left", validate="many_to_one")
    assert len(rows) == count, "Fan-out al unir el contexto de auditoría"
    rows = rows.reset_index(drop=True)
    features = model_input_frame(rows, columns)
    derived = classifier.named_steps["historial"].transform(features)
    downstream = classifier[1:]
    class_order = [list(classifier.classes_).index(label) for label in RESULT_ORDER]

    def probabilities(frame):
        p = downstream.predict_proba(frame)[:, class_order]
        assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
        np.testing.assert_allclose(p.sum(axis=1), 1, atol=1e-9)
        return p

    print(f"Evaluando {len(rows)} cortes de {len(future)} partidas futuras...", flush=True)
    p = probabilities(derived)
    # Bypassing history for controlled probes must match the complete Pipeline.
    np.testing.assert_allclose(p[:128], classifier.predict_proba(features.iloc[:128])[:, class_order], atol=1e-12)
    rows[["p0", "p1", "p2"]] = p
    if "plies_restantes" in artifact:
        rows["duration_pred"] = artifact["plies_restantes"].predict(features).clip(min=1)
    ratings = derived[["elo_blancas_previo", "elo_negras_previo"]]
    rows["cobertura"] = np.select(
        [ratings.notna().all(axis=1), ratings.notna().any(axis=1)],
        ["ambos", "un_lado"], default="ninguno")
    # Group only by ratings available before the game; never substitute posterior Elo.
    rows["nivel"] = pd.cut(ratings.mean(axis=1), [0, 1200, 1800, 2200, 2600, 3000, np.inf],
                           labels=LEVELS, right=False).astype("string").fillna("sin_rating")
    rows["ritmo"] = rows["TimeClass"].astype(str)
    initial = rows[rows["corte_ply"] == 0].copy()
    assert len(initial) == len(future), "Falta alguna posición inicial"
    early = derived.loc[initial.index].copy()
    early_p = initial[["p0", "p1", "p2"]].to_numpy()
    both = initial[initial["cobertura"] == "ambos"].copy()
    delta = ratings.loc[both.index, "elo_blancas_previo"] - ratings.loc[both.index, "elo_negras_previo"]
    both["diferencia"] = pd.cut(delta, [-np.inf, -400, -200, -100, 100, 200, 400, np.inf],
                               labels=["< -400", "-400 a -200", "-200 a -100", "-100 a 100",
                                       "100 a 200", "200 a 400", ">= 400"], right=False).astype(str)

    # Reliability bins are classwise, using the same games for all three classes.
    reliability = []
    for i, label in enumerate(RESULT_ORDER):
        data = initial.copy()
        data["bin"] = np.minimum((data[f"p{i}"] * 10).astype(int), 9)
        for bin_id, group in data.groupby("bin"):
            reliability.append(dict(clase=label, bin=int(bin_id), n=len(group),
                                    pred=float(group[f"p{i}"].mean()),
                                    real=float(group["resultado"].eq(label).mean())))

    # Missingness probes use the existing imputer; they are not retrained ablations.
    print("Midiendo sensibilidad a ratings, pausas y faltantes...", flush=True)
    probes = {}
    for name, selected in [("sin_forma", FORM),
                           ("sin_pausas", [f"minutos_desde_anterior_{s}" for s in ["blancas", "negras"]])]:
        changed = early.copy()
        changed[selected] = np.nan
        altered = probabilities(changed)
        shift = 100 * np.abs(altered[:, 0] - early_p[:, 0])
        probes[name] = dict(mean_abs_white_pp=float(shift.mean()), p95_abs_white_pp=float(np.quantile(shift, .95)),
                            max_abs_white_pp=float(shift.max()),
                            favorite_flip_rate=float(((altered[:, 0] > altered[:, 2]) !=
                                                      (early_p[:, 0] > early_p[:, 2])).mean()))

    known_w = early["elo_blancas_previo"].notna()
    changed = early.loc[known_w].copy()
    changed["elo_blancas_previo"] += 200
    shift = 100 * (probabilities(changed)[:, 0] - early_p[known_w, 0])
    rating_probe = initial.loc[known_w, ["nivel"]].copy()
    rating_probe["shift"] = shift
    rating_sensitivity = []
    for level, group in rating_probe.groupby("nivel"):
        rating_sensitivity.append(dict(nivel=str(level), n=len(group), mean_white_pp=float(group["shift"].mean()),
                                       decrease_rate=float((group["shift"] < -1e-8).mean()),
                                       change_under_1pp_rate=float((group["shift"].abs() < 1).mean())))

    in_range = (early.loc[known_w, "elo_blancas_previo"] + 200 <= artifact["rango_rating"][1]).to_numpy()
    in_range_shift = shift[in_range]
    probes["rating_mas_200_dentro_rango"] = dict(n=len(in_range_shift),
        mean_white_pp=float(in_range_shift.mean()), decrease_rate=float((in_range_shift < -1e-8).mean()))

    # Compare Elo effects on the same neutral initial board, with both ratings known.
    board_rows, _ = game_cut_features("1. e4 *", [0], 180, 0)
    grid = []
    for center in [1000, 1500, 2000, 2400, 2800, 3200]:
        for difference in [-200, 0, 200]:
            grid.append(dict(board_rows[0], TimeClass="blitz", tiempo_base_seg=180, incremento_seg=0,
                EsTorneo=False, elo_blancas_previo=center + difference / 2,
                elo_negras_previo=center - difference / 2, center=center, difference=difference))
    grid_frame = pd.DataFrame(grid)
    grid_p = probabilities(model_input_frame(grid_frame, columns)[columns])
    grid_frame[["p_blancas", "p_tablas", "p_negras"]] = grid_p

    known_pause = early["minutos_desde_anterior_blancas"].notna()
    changed = early.loc[known_pause].copy()
    changed["minutos_desde_anterior_blancas"] += 1
    shift = 100 * (probabilities(changed)[:, 0] - early_p[known_pause, 0])
    probes["un_minuto_mas_blancas"] = dict(n=len(shift), mean_white_pp=float(shift.mean()),
        p95_abs_white_pp=float(np.quantile(np.abs(shift), .95)), max_abs_white_pp=float(np.abs(shift).max()),
        over_5pp_rate=float((np.abs(shift) > 5).mean()))

    # Enumerate real examples for both the diagnostic and manual reproducibility.
    examples = []
    for _, group in both.groupby("nivel", observed=True):
        for index in group.sort_values("GameUrl").head(2).index:
            row = both.loc[index]
            examples.append(dict(url=row["GameUrl"], blancas=row["White"], negras=row["Black"],
                nivel=row["nivel"], ritmo=row["ritmo"], resultado=str(row["resultado"]),
                elo_blancas=float(ratings.loc[index].iloc[0]), elo_negras=float(ratings.loc[index].iloc[1]),
                p_blancas=float(row["p0"]), p_tablas=float(row["p1"]), p_negras=float(row["p2"])))
    strong = both.loc[delta.abs() >= 100]
    white_favored = delta.loc[strong.index] > 0
    model_white_favored = strong["p0"] > strong["p2"]
    return dict(
        metadata=dict(model_sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                      entrenado_hasta=str(artifact["entrenado_hasta"]), rango_rating=artifact.get("rango_rating"),
                      n_games=len(future), n_cuts=len(rows),
                      training_games=len(training), training_both_ratings=int(training_ratings.notna().all(axis=1).sum()),
                      start=str(future["StartTime"].min()), end=str(future["StartTime"].max())),
        por_corte=summarize(rows, ["corte_ply"]),
        por_nivel=summarize(rows, ["corte_ply", "nivel"]),
        por_ritmo=summarize(rows, ["corte_ply", "ritmo"]),
        por_nivel_ritmo=summarize(initial, ["nivel", "ritmo"]),
        por_cobertura=summarize(initial, ["cobertura"]),
        por_nivel_cobertura=summarize(initial, ["nivel", "cobertura"]),
        por_diferencia=summarize(both, ["diferencia"]),
        por_nivel_diferencia=summarize(both, ["nivel", "diferencia"]),
        reliability=reliability, missingness_probes=probes, rating_sensitivity=rating_sensitivity,
        neutral_rating_grid=grid_frame[["center", "difference", "p_blancas", "p_tablas", "p_negras"]].to_dict(orient="records"),
        favorite_disagreement=dict(n=len(strong), rate=float((white_favored != model_white_favored).mean())
                                   if len(strong) else None), examples=examples)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/auditoria-probabilidades.json"))
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[1])
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Auditoría guardada en {args.output}")
