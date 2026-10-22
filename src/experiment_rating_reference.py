"""Referencia inicial de tres resultados, para diagnóstico; no reemplaza la app.

Usa ratings anteriores observados, cuya antigüedad/procedencia puede ser parcial.
Selecciona por CV temporal purgada y declara el período final como ya observado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.model_validation import temporal_game_folds
from src.predict import RESULT_ORDER


def rating_features(frame: pd.DataFrame, incidental: bool, max_incidental_age_days: float | None = None) -> pd.DataFrame:
    """Only observed prior ratings; no target posterior rating or incomplete form."""
    result = frame[["TimeClass", "tiempo_base_seg", "incremento_seg", "EsTorneo"]].copy()
    ratings = frame[["rating_blancas", "rating_negras"]].copy()
    ages = frame[["age_days_blancas", "age_days_negras"]].copy()
    for side in ["blancas", "negras"]:
        if not incidental:
            missing_source = ~frame[f"source_owner_{side}"].eq(True)
            ratings.loc[missing_source, f"rating_{side}"] = np.nan
            ages.loc[missing_source, f"age_days_{side}"] = np.nan
        elif max_incidental_age_days is not None:
            too_old = ~frame[f"source_owner_{side}"].eq(True) & (
                ages[f"age_days_{side}"].isna() | ages[f"age_days_{side}"].gt(max_incidental_age_days))
            ratings.loc[too_old, f"rating_{side}"] = np.nan
            ages.loc[too_old, f"age_days_{side}"] = np.nan
        result[f"rating_known_{side}"] = ratings[f"rating_{side}"].notna().astype(float)
        result[f"rating_incidental_{side}"] = (ratings[f"rating_{side}"].notna() & ~frame[f"source_owner_{side}"].eq(True)).astype(float)
        result[f"age_log1p_{side}"] = np.log1p(ages[f"age_days_{side}"])
    result["rating_difference"] = ratings["rating_blancas"] - ratings["rating_negras"]
    result["rating_mean_known"] = ratings.mean(axis=1)
    for column in result:
        result[column] = result[column].astype(str) if column == "TimeClass" else pd.to_numeric(result[column]).astype(float)
    return result


def purged_folds(games: pd.DataFrame, n_splits: int = 5):
    """Remove training games whose closing time is unavailable at validation start."""
    folds = []
    for train, valid in temporal_game_folds(games["GameUrl"], games["StartTime"], n_splits=n_splits):
        boundary = games.iloc[valid]["StartTime"].min()
        train = train[(games.iloc[train]["EndTime"] < boundary).to_numpy()]
        if not len(train):
            raise ValueError("Fold sin entrenamiento tras purgar partidas solapadas")
        assert not set(games.iloc[train]["GameUrl"]) & set(games.iloc[valid]["GameUrl"])
        assert games.iloc[train]["EndTime"].max() < boundary
        folds.append((train, valid))
    return folds


def make_reference(features: pd.DataFrame) -> Pipeline:
    numeric = [column for column in features if column != "TimeClass"]
    preprocessing = ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                              ("scale", StandardScaler())]), numeric),
        ("rhythm", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["TimeClass"]),
    ])
    return Pipeline([("preprocessing", preprocessing),
                     ("classifier", LogisticRegression(C=1.0, max_iter=2000, random_state=42))])


def score(model, features, target) -> dict:
    raw = model.predict_proba(features)
    p = raw[:, [list(model.classes_).index(label) for label in RESULT_ORDER]]
    actual = target.astype(str).to_numpy()[:, None] == np.asarray(RESULT_ORDER)[None, :]
    return dict(n=len(features), log_loss=float(log_loss(target, raw, labels=model.classes_)),
                brier=float(np.square(p - actual).sum(axis=1).mean()),
                predicted_mean=p.mean(axis=0).tolist(), actual_mean=actual.mean(axis=0).tolist())


def neutral_grid(model, incidental: bool, max_incidental_age_days: float | None = None) -> list[dict]:
    """Hold level/rhythm/history availability fixed while changing relative Elo."""
    rows = []
    for rhythm, seconds in [("bullet", 60), ("blitz", 180), ("rapid", 600)]:
        for center in [1000, 1500, 2000, 2400, 2800, 3200]:
            for gap in [-400, -200, 0, 200, 400]:
                rows.append(dict(TimeClass=rhythm, tiempo_base_seg=seconds, incremento_seg=0, EsTorneo=False,
                    rating_blancas=center + gap / 2, rating_negras=center - gap / 2,
                    age_days_blancas=.001, age_days_negras=.001,
                    source_owner_blancas=True, source_owner_negras=True, center=center, gap=gap))
    frame = pd.DataFrame(rows)
    p = model.predict_proba(rating_features(frame, incidental, max_incidental_age_days))
    for label in RESULT_ORDER:
        frame[label] = p[:, list(model.classes_).index(label)]
    records = frame[["TimeClass", "center", "gap", *RESULT_ORDER]].to_dict(orient="records")
    for _, group in frame.groupby(["TimeClass", "center"], observed=True):
        if (np.diff(group.sort_values("gap")["Gana Blancas"].to_numpy()) < -1e-8).any():
            raise ValueError("Referencia con inversión de rating en la grilla neutral")
    return records


def run(root: Path, output: Path):
    protocol = yaml.safe_load((root / "config/evaluacion_mejora_app.yaml").read_text())
    games = pd.read_parquet(root / "data/processed/partidas_ajedrez_clean.parquet")
    observed = pd.read_parquet(root / "data/processed/auditoria_cobertura/ratings_previos_observados.parquet")
    columns = [c for c in observed if c.startswith(("rating_", "age_days_", "source_owner_"))]
    count = len(games)
    frame = games.merge(observed[["GameUrl", *columns]], on="GameUrl", how="left", validate="one_to_one")
    assert len(frame) == count, "Fan-out al adjuntar ratings observados"
    cutoff = pd.Timestamp(protocol["regression_period"]["train_before"])
    train = frame[frame["EndTime"] < cutoff].reset_index(drop=True)
    evaluation = frame[frame["StartTime"] >= cutoff].reset_index(drop=True)
    folds = purged_folds(train, protocol["selection"]["folds"])
    output.mkdir(parents=True, exist_ok=True)
    results = dict(protocol="config/evaluacion_mejora_app.yaml", initial_position_only=True,
                   fresh_holdout=False, candidates={})
    results["input_sha256"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [root / "config/evaluacion_mejora_app.yaml",
                     root / "data/processed/partidas_ajedrez_clean.parquet",
                     root / "data/processed/auditoria_cobertura/ratings_previos_observados.parquet"]
    }
    assignments = []
    for fold, (train_ids, valid_ids) in enumerate(folds):
        for role, ids in [("train", train_ids), ("validation", valid_ids)]:
            assignments.append(pd.DataFrame(dict(GameUrl=train.iloc[ids]["GameUrl"].to_numpy(), fold=fold, role=role)))
    pd.concat(assignments).to_parquet(output / "fold_assignments.parquet", index=False)
    # Model specifications are fixed here; no hyperparameter search on observed evaluation.
    specs = [("own_ratings_reference", False, None), ("observed_ratings_reference", True, None),
             ("observed_ratings_max30d_reference", True, 30)]
    for name, incidental, age_limit in specs:
        print(f"CV temporal: {name}", flush=True)
        x = rating_features(train, incidental, age_limit)
        candidate = dict(folds=[])
        for fold, (train_ids, valid_ids) in enumerate(folds):
            model = make_reference(x)
            model.fit(x.iloc[train_ids], train.iloc[train_ids]["resultado"])
            metrics = score(model, x.iloc[valid_ids], train.iloc[valid_ids]["resultado"])
            metrics.update(fold=fold, n_train=len(train_ids))
            candidate["folds"].append(metrics)
        losses = np.array([fold["log_loss"] for fold in candidate["folds"]])
        candidate.update(cv_log_loss_mean=float(losses.mean()), cv_log_loss_sd=float(losses.std(ddof=1)))
        model = make_reference(x)
        model.fit(x, train["resultado"])
        candidate["observed_evaluation"] = score(model, rating_features(evaluation, incidental, age_limit), evaluation["resultado"])
        candidate["neutral_rating_grid"] = neutral_grid(model, incidental, age_limit)
        results["candidates"][name] = candidate
        joblib.dump(dict(model=model, features=list(x), incidental=incidental, max_incidental_age_days=age_limit,
                         purpose="diagnostic_reference_initial_only_not_app_artifact"), output / f"{name}.joblib")
    own = results["candidates"]["own_ratings_reference"]["folds"]
    enriched = results["candidates"]["observed_ratings_reference"]["folds"]
    differences = np.array([a["log_loss"] - b["log_loss"] for a, b in zip(enriched, own)])
    results["paired_cv_enriched_minus_own"] = dict(mean=float(differences.mean()), sd=float(differences.std(ddof=1)))
    (output / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("models/experiments/rating_reference"))
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.output_dir)
