"""Arnés de comparación para los ratings de rivales (docs/entregas/plan-mejora-modelo-app.md).

Reproduce la partición, la muestra de CV, los cinco folds temporales y el bosque final del
notebook 04, y evalúa variantes de columnas con la regla del 04. No modifica el dataset,
el notebook ni el artefacto de la app: escribe sólo en ``models/experiments/``.

Ejecutar desde la raíz: python -m src.experiment_rival_ratings [--variants A B C D] [--skip-grid]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.history_transformer import (
    RATING_AGE, RATING_RELATIVE, PlayerHistoryTransformer, attach_player_histories, player_history_payloads,
)
from src.live_features import game_cut_features
from src.model_validation import temporal_game_folds
from src.player_selection import load_selection
from src.predict import CATEGORICAL, FORM, LIVE, PRE_GAME, RESULT_ORDER, model_input_frame
from src.utils import load_config

# Same values as notebook 04 (cells 2 and 17): CV sample share, folds and the chosen grid point.
CV_GAME_FRACTION = 0.25
N_SPLITS = 5
FOREST_PARAMS = dict(n_estimators=200, min_samples_leaf=20, max_samples=0.3, max_features=0.3)
BASE_COLUMNS = PRE_GAME + LIVE
FINAL_COLUMNS = BASE_COLUMNS + FORM
# Grid best of notebook 04 §5 (sklearn std, ddof=0): the harness must reproduce it.
NOTEBOOK_GRID = dict(log_loss=0.8301, sd=0.0231, tolerance=0.001)

# Variants of the plan's phase 3: columns and whether histories include rival ratings.
VARIANTS = {
    "grilla_04": (BASE_COLUMNS, False),               # harness check: the 30 columns of the 04 grid
    "A": (FINAL_COLUMNS, False),                      # current app forest (40 columns)
    "B": (FINAL_COLUMNS + RATING_AGE, True),          # + rival ratings and rating age
    "C": (FINAL_COLUMNS + RATING_AGE + RATING_RELATIVE, True),  # + difference and mean
    "D": None,                                        # best of B/C without pauses and session
}
PAUSES = [f"{c}_{side}" for c in ("minutos_desde_anterior", "partidas_sesion") for side in ("blancas", "negras")]

# Control grid (plan, phase 3): initial position, both ratings known, empty form.
GRID_MEANS = [1200, 1800, 2400, 3000]
GRID_DIFFERENCES = [-400, -200, 0, 200, 400]
GRID_RHYTHMS = {"bullet": 60, "blitz": 180, "rapid": 600}
GRID_AGE_DAYS = 1.0
# A (rhythm, mean) cell counts as covered by data with this many train games whose
# known prior rating (either side) lies within +-GRID_BAND of the mean.
GRID_BAND = 200
GRID_MIN_GAMES = 100


def make_forest(columns: list[str], random_state: int) -> Pipeline:
    """The notebook 04 forest Pipeline (cell 9) with the grid winner (cell 17)."""
    categorical = [c for c in columns if c in CATEGORICAL]
    numeric = [c for c in columns if c not in CATEGORICAL]
    prep = ColumnTransformer([
        ("categoricas", OneHotEncoder(handle_unknown="ignore"), categorical),
        ("numericas", SimpleImputer(strategy="median", add_indicator=True), numeric),
    ])
    forest = RandomForestClassifier(**FOREST_PARAMS, n_jobs=-1, random_state=random_state)
    return Pipeline([("historial", PlayerHistoryTransformer(columns)), ("prep", prep), ("modelo", forest)])


def load_data(root: Path, config: dict, with_rivals: bool):
    """Games, the cut table joined with fixed context (04, cell 4) and both history sets."""
    games = pd.read_parquet(root / config["paths"]["clean_parquet"])
    cuts = pd.read_parquet(root / config["paths"]["cortes_parquet"])
    usernames = load_selection(root / config["player_selection"]["selection_path"])
    template = config["chess_com"]["raw_filename_template"]
    raw_paths = {u: root / config["paths"]["raw_dir"] / template.format(username=u) for u in usernames}
    starts = games[["GameUrl", "StartTime"]]
    histories = {False: player_history_payloads(raw_paths, starts)}
    if with_rivals:
        histories[True] = player_history_payloads(raw_paths, starts, rivales=True)
    context = ["GameUrl", "StartTime", "EndTime", "White", "Black", *PRE_GAME, *FORM]
    count = len(cuts)
    data = cuts.merge(games.reindex(columns=context), on="GameUrl", how="left", validate="many_to_one")
    assert len(data) == count, "Fan-out detectado al unir el contexto de la partida"
    return games, data, histories


def split(games: pd.DataFrame, data: pd.DataFrame, random_state: int):
    """Train/test boundary, CV sample of train games and temporal folds (04, cells 5-6)."""
    boundary = games["StartTime"].quantile(0.8)
    train_games = set(games.loc[games["EndTime"] < boundary, "GameUrl"])
    train = data[data["GameUrl"].isin(train_games)].reset_index(drop=True)
    cv_games = pd.Series(sorted(train_games)).sample(frac=CV_GAME_FRACTION, random_state=random_state)
    cv_data = train[train["GameUrl"].isin(set(cv_games))].reset_index(drop=True)
    folds = temporal_game_folds(cv_data["GameUrl"], cv_data["StartTime"], n_splits=N_SPLITS)
    for fit_rows, val_rows in folds:
        fit_part, val_part = cv_data.iloc[fit_rows], cv_data.iloc[val_rows]
        assert set(fit_part["GameUrl"]).isdisjoint(val_part["GameUrl"]), "Una partida quedó de los dos lados"
        assert fit_part["EndTime"].max() < val_part["StartTime"].min(), "Un resultado de train aún no existía al validar"
    return boundary, train, cv_data, folds


def cross_validate_variant(columns: list[str], cv_data: pd.DataFrame, folds, random_state: int, rivals: bool) -> dict:
    """Global and cut-0 log-loss per fold, as the 04 scorers compute them."""
    x = model_input_frame(cv_data, columns)
    y = cv_data["resultado"].astype(str).to_numpy()
    at_start = (cv_data["corte_ply"] == 0).to_numpy()
    per_fold = []
    for k, (fit_rows, val_rows) in enumerate(folds, start=1):
        started = time.perf_counter()
        model = make_forest(columns, random_state).fit(x.iloc[fit_rows], y[fit_rows])
        p = model.predict_proba(x.iloc[val_rows])
        start_rows = at_start[val_rows]
        per_fold.append(dict(
            fold=k,
            log_loss=float(log_loss(y[val_rows], p, labels=model.classes_)),
            log_loss_corte0=float(log_loss(y[val_rows][start_rows], p[start_rows], labels=model.classes_)),
            seconds=time.perf_counter() - started,
        ))
        print(f"  fold {k}: {per_fold[-1]['log_loss']:.4f} (corte 0 {per_fold[-1]['log_loss_corte0']:.4f})", flush=True)
    result = dict(columns=columns, n_columns=len(columns), rivales=rivals, folds=per_fold)
    for metric in ["log_loss", "log_loss_corte0"]:
        values = np.array([f[metric] for f in per_fold])
        result[metric] = dict(mean=float(values.mean()), sd=float(values.std(ddof=1)), sd_sklearn=float(values.std(ddof=0)))
    return result


def paired(candidate: dict, reference: dict) -> dict:
    """Notebook 04 rule: better globally beyond its sd and cut 0 not worse beyond its sd."""
    out = {}
    for metric in ["log_loss", "log_loss_corte0"]:
        diff = np.array([c[metric] - r[metric] for c, r in zip(candidate["folds"], reference["folds"])])
        out[metric] = dict(mean=float(diff.mean()), sd=float(diff.std(ddof=1)), per_fold=diff.tolist())
    g, c0 = out["log_loss"], out["log_loss_corte0"]
    out["gana_con_regla_04"] = bool(g["mean"] < -g["sd"] and not c0["mean"] > c0["sd"])
    return out


def grid_coverage(games: pd.DataFrame, train: pd.DataFrame, histories: dict) -> dict:
    """Train games per (rhythm, mean) with a known prior rating near that mean."""
    train_games = attach_player_histories(games[games["GameUrl"].isin(set(train["GameUrl"]))], histories)
    known = PlayerHistoryTransformer(["elo_blancas_previo", "elo_negras_previo"]).fit_transform(train_games)
    known["TimeClass"] = train_games["TimeClass"].astype(str).to_numpy()
    coverage = {}
    for rhythm in GRID_RHYTHMS:
        sub = known[known["TimeClass"] == rhythm]
        for mean in GRID_MEANS:
            near = sub[["elo_blancas_previo", "elo_negras_previo"]].sub(mean).abs().le(GRID_BAND).any(axis=1)
            coverage[(rhythm, mean)] = int(near.sum())
    return coverage


def control_grid(model: Pipeline, columns: list[str], coverage: dict) -> dict:
    """P(gana blancas) on the initial board while only the rating difference changes."""
    rows = []
    for rhythm, seconds in GRID_RHYTHMS.items():
        board, _ = game_cut_features("1. e4 *", [0], seconds, 0)
        for mean in GRID_MEANS:
            for difference in GRID_DIFFERENCES:
                rows.append(dict(board[0], TimeClass=rhythm, tiempo_base_seg=seconds, incremento_seg=0, EsTorneo=False,
                                 elo_blancas_previo=mean + difference / 2, elo_negras_previo=mean - difference / 2,
                                 antiguedad_rating_dias_blancas=GRID_AGE_DAYS, antiguedad_rating_dias_negras=GRID_AGE_DAYS,
                                 promedio=mean, diferencia=difference))
    frame = pd.DataFrame(rows)
    # No history payloads: the transformer keeps these explicit ratings and leaves form NaN.
    p = model.predict_proba(model_input_frame(frame, columns))
    order = [list(model.classes_).index(label) for label in RESULT_ORDER]
    frame[["p_blancas", "p_tablas", "p_negras"]] = p[:, order]
    cells, inversions = [], []
    for (rhythm, mean), group in frame.groupby(["TimeClass", "promedio"], sort=False):
        group = group.sort_values("diferencia")
        steps = np.diff(group["p_blancas"].to_numpy())
        covered = coverage[(rhythm, mean)] >= GRID_MIN_GAMES
        cells.append(dict(ritmo=rhythm, promedio=int(mean), partidas_train=coverage[(rhythm, mean)], con_datos=covered,
                          p_blancas=dict(zip(map(int, group["diferencia"]), map(float, group["p_blancas"])))))
        for (low, high), step in zip(zip(GRID_DIFFERENCES, GRID_DIFFERENCES[1:]), steps):
            if step < -1e-9:
                inversions.append(dict(ritmo=rhythm, promedio=int(mean), de=low, a=high,
                                       baja_pp=float(-100 * step), con_datos=covered))
    covered_steps = sum(len(GRID_DIFFERENCES) - 1 for c in cells if c["con_datos"])
    covered_inversions = sum(i["con_datos"] for i in inversions)
    return dict(cells=cells, inversions=inversions, pasos_con_datos=covered_steps,
                inversiones_con_datos=covered_inversions, pasa=covered_inversions == 0)


def print_summary(results: dict) -> None:
    print("\nVariante   cols  log-loss (sd, sd sklearn)      corte 0 (sd)")
    for name, r in results["variants"].items():
        g, c0 = r["log_loss"], r["log_loss_corte0"]
        print(f"{name:<10} {r['n_columns']:>4}  {g['mean']:.4f} ({g['sd']:.4f}, {g['sd_sklearn']:.4f})   "
              f"{c0['mean']:.4f} ({c0['sd']:.4f})")
    for name, diff in results.get("paired_vs_A", {}).items():
        g, c0 = diff["log_loss"], diff["log_loss_corte0"]
        print(f"{name} − A: global {g['mean']:+.4f} ± {g['sd']:.4f}, corte 0 {c0['mean']:+.4f} ± {c0['sd']:.4f}"
              f" → {'gana' if diff['gana_con_regla_04'] else 'no gana'}")
    if "D_parte_de" in results:
        print(f"D parte de {results['D_parte_de']} (la de menor log-loss entre B y C)")
    if "harness_check" in results:
        h = results["harness_check"]
        print(f"Chequeo del arnés: {h['log_loss']:.4f} ± {h['sd_sklearn']:.4f} frente a "
              f"{NOTEBOOK_GRID['log_loss']} ± {NOTEBOOK_GRID['sd']} → {'reproduce' if h['reproduce'] else 'NO reproduce'}")
    for name, grid in results.get("control_grid", {}).items():
        print(f"\nGrilla de control, {name}: {grid['inversiones_con_datos']} inversiones en "
              f"{grid['pasos_con_datos']} pasos con datos ({len(grid['inversions'])} en total)")
        for cell in grid["cells"]:
            values = " ".join(f"{v:.3f}" for v in cell["p_blancas"].values())
            mark = "" if cell["con_datos"] else "  (sin datos)"
            print(f"  {cell['ritmo']:<6} {cell['promedio']:>4}: {values}{mark}")


def run(root: Path, output: Path, variants: list[str], with_grid: bool) -> dict:
    config = load_config(root / "config" / "config.yaml")
    random_state = config["processing"]["random_state"]
    started = time.perf_counter()
    print("Cargando datos e historiales...", flush=True)
    names = [n for n in VARIANTS if n in variants]  # fixed order: D needs B and C
    if "D" in names and not {"B", "C"} <= set(names):
        raise ValueError("D se arma con la mejor entre B y C: correr también B y C")
    games, data, histories = load_data(root, config, with_rivals=any(n in ("B", "C", "D") for n in names))
    boundary, train, cv_data, folds = split(games, data, random_state)
    attached = {}

    def with_histories(frame: pd.DataFrame, rivals: bool) -> pd.DataFrame:
        # One CV copy per history set, reused by every variant that needs it.
        if rivals not in attached:
            attached[rivals] = attach_player_histories(frame, histories[rivals])
        return attached[rivals]

    print(f"Train: {train['GameUrl'].nunique():,} partidas · CV: {cv_data['GameUrl'].nunique():,} partidas, "
          f"{len(cv_data):,} filas · corte {boundary}", flush=True)
    results = dict(
        boundary=str(boundary), train_games=int(train["GameUrl"].nunique()), train_rows=len(train),
        cv_games=int(cv_data["GameUrl"].nunique()), cv_rows=len(cv_data), forest=FOREST_PARAMS,
        fold_sizes=[dict(train_games=int(cv_data.iloc[f]["GameUrl"].nunique()), val_games=int(cv_data.iloc[v]["GameUrl"].nunique()))
                    for f, v in folds],
        variants={},
    )
    specs = {}
    for name in names:
        if name == "D":
            best = min(["B", "C"], key=lambda n: results["variants"][n]["log_loss"]["mean"])
            columns, rivals = VARIANTS[best]
            specs[name] = ([c for c in columns if c not in PAUSES], rivals)
            results["D_parte_de"] = best
        else:
            specs[name] = VARIANTS[name]
        columns, rivals = specs[name]
        print(f"CV: {name} ({len(columns)} columnas, rivales={rivals})", flush=True)
        results["variants"][name] = cross_validate_variant(
            columns, with_histories(cv_data, rivals), folds, random_state, rivals)
    if "grilla_04" in results["variants"]:
        r = results["variants"]["grilla_04"]["log_loss"]
        results["harness_check"] = dict(log_loss=r["mean"], sd_sklearn=r["sd_sklearn"], expected=NOTEBOOK_GRID,
                                        reproduce=abs(r["mean"] - NOTEBOOK_GRID["log_loss"]) < NOTEBOOK_GRID["tolerance"])
    if "A" in results["variants"]:
        results["paired_vs_A"] = {name: paired(r, results["variants"]["A"])
                                  for name, r in results["variants"].items() if name not in ("A", "grilla_04")}
    if with_grid:
        attached.clear()  # free the CV copies before fitting on all of train
        # Coverage describes who plays at each level: use every rating observation available.
        coverage = grid_coverage(games, train, histories[max(histories)])
        results["control_grid"] = {}
        for name in names:
            if name == "grilla_04":
                continue
            columns, rivals = specs[name]
            print(f"Entrenando {name} con todo train para la grilla de control...", flush=True)
            x = model_input_frame(attach_player_histories(train, histories[rivals]), columns)
            model = make_forest(columns, random_state).fit(x, train["resultado"].astype(str).to_numpy())
            results["control_grid"][name] = control_grid(model, columns, coverage)
            del model, x
    results["seconds"] = time.perf_counter() - started
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(results)
    print(f"\nResultados en {output / 'metrics.json'} ({results['seconds'] / 60:.1f} min)")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", nargs="+", default=["grilla_04", "A", "B", "C", "D"], choices=list(VARIANTS))
    parser.add_argument("--skip-grid", action="store_true", help="no entrenar con todo train ni evaluar la grilla de control")
    parser.add_argument("--output-dir", type=Path, default=Path("models/experiments/rival_ratings"))
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.output_dir, args.variants, not args.skip_grid)
