"""Piloto sin red: ratings previos de rivales que ya aparecen en los JSON locales.

No cambia los historiales del modelo: una aparición incidental aporta un rating
observado con antigüedad, nunca una ventana completa de forma reciente.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping

import numpy as np
import pandas as pd

from src.player_selection import load_selection


def read_observations(paths: Mapping[str, Path]) -> tuple[pd.DataFrame, dict]:
    """Read both colors; retain source provenance and reject conflicting duplicates."""
    rows = []
    raw_games = excluded = 0
    for owner, path in paths.items():
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for game in payload.get("games", []):
            raw_games += 1
            if not (game.get("rated") and game.get("rules") == "chess"
                    and game.get("time_class") in ["bullet", "blitz", "rapid"] and game.get("pgn")):
                excluded += 1
                continue
            for color in ["white", "black"]:
                player = game.get(color, {})
                username = str(player.get("username", "")).lower()
                try:
                    rating, end = float(player["rating"]), float(game["end_time"])
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"Observación incompleta: {path}, {game.get('url')}, {color}") from error
                if not username or not game.get("url") or not np.isfinite([rating, end]).all() or rating < 0 or end <= 0:
                    raise ValueError(f"Observación inválida: {path}, {game.get('url')}, {color}")
                rows.append(dict(username=username, GameUrl=game["url"], time_class=game["time_class"],
                                 rating=rating, end_time=end, source_owner=username == owner.lower()))
    observations = pd.DataFrame(rows, columns=["username", "GameUrl", "time_class", "rating", "end_time", "source_owner"])
    keys = ["username", "GameUrl"]
    if not observations.empty:
        conflicts = observations.groupby(keys)[["time_class", "rating", "end_time"]].nunique().gt(1).any(axis=1)
        if conflicts.any():
            raise ValueError(f"Copias contradictorias: {list(conflicts[conflicts].index[:10])}")
    before = len(observations)
    # Prefer an account's own archive when the same observation appears in two files.
    observations = observations.sort_values("source_owner", ascending=False).drop_duplicates(keys)
    assert not observations.duplicated(keys).any()
    metadata = dict(raw_games=raw_games, excluded_out_of_scope=excluded,
                    duplicated_observations=before - len(observations), observations=len(observations),
                    accounts=int(observations["username"].nunique()))
    return observations.reset_index(drop=True), metadata


def lookup_previous_ratings(games: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    """One row per game/color; only observations ending strictly before its start."""
    assert games["GameUrl"].is_unique, "Una fila objetivo por partida"
    if games["StartTime"].isna().any():
        raise ValueError("No se puede consultar el pasado sin StartTime")
    starts = pd.to_datetime(games["StartTime"], utc=True)
    seconds = ((starts - pd.Timestamp("1970-01-01", tz="UTC")) / pd.Timedelta(seconds=1)).to_numpy(dtype=float)
    queries = []
    for color, side in [("White", "blancas"), ("Black", "negras")]:
        queries.append(pd.DataFrame(dict(query_id=np.arange(len(games)), side=side,
            username=games[color].astype(str).str.lower().to_numpy(),
            time_class=games["TimeClass"].astype(str).to_numpy(), at=seconds,
            target_url=games["GameUrl"].to_numpy())))
    left = pd.concat(queries, ignore_index=True).sort_values("at", kind="stable")
    right = observations.copy()
    for key in ["username", "time_class"]:
        right[key] = right[key].astype(str)
    right = right.sort_values(["end_time", "GameUrl"], kind="stable")
    right["end_time"] = right["end_time"].astype(float)
    count = len(left)
    if right.empty:
        result = left.copy()
        for column in ["GameUrl", "rating", "end_time", "source_owner"]:
            result[column] = np.nan
    else:
        result = pd.merge_asof(left, right, left_on="at", right_on="end_time",
            by=["username", "time_class"], direction="backward", allow_exact_matches=False)
        assert len(result) == count, "Fan-out al consultar ratings previos"
    assert len(result) == 2 * len(games)
    assert not result.duplicated(["query_id", "side"]).any()
    available = result["rating"].notna()
    assert (result.loc[available, "end_time"] < result.loc[available, "at"]).all()
    assert (result.loc[available, "GameUrl"] != result.loc[available, "target_url"]).all(), "Fuga de la partida objetivo"
    result["age_days"] = (result["at"] - result["end_time"]) / 86400
    return result.sort_values(["query_id", "side"], kind="stable").reset_index(drop=True)


def coverage_table(games: pd.DataFrame, lookup: pd.DataFrame, cutoff: str) -> pd.DataFrame:
    """Create a game-level table without merging or using posterior target ratings."""
    output = games[["GameUrl", "TimeClass", "StartTime", "EndTime"]].reset_index(drop=True).copy()
    output["partition"] = np.select(
        [output["EndTime"] < pd.Timestamp(cutoff), output["StartTime"] >= pd.Timestamp(cutoff)],
        ["train", "observed_evaluation"], default="crossing_excluded")
    for value in ["rating", "age_days", "source_owner"]:
        wide = lookup.pivot(index="query_id", columns="side", values=value).reindex(range(len(games)))
        for side in ["blancas", "negras"]:
            output[f"{value}_{side}"] = wide[side].to_numpy()
    return output


def summarize(table: pd.DataFrame, source: str) -> list[dict]:
    rows = []
    for (partition, rhythm), group in table.groupby(["partition", "TimeClass"], observed=True):
        known = group[["rating_blancas", "rating_negras"]].notna()
        both = known.all(axis=1)
        row = dict(source=source, partition=str(partition), ritmo=str(rhythm), n=len(group),
            both=int(both.sum()), one=int((known.sum(axis=1) == 1).sum()), neither=int((~known.any(axis=1)).sum()))
        for days in [1, 7, 30]:
            fresh = group[["age_days_blancas", "age_days_negras"]].le(days).all(axis=1)
            row[f"both_within_{days}_days"] = int((both & fresh).sum())
        for minimum, maximum in [(0, 100), (100, 200), (200, 400), (400, float("inf"))]:
            gap = (group["rating_blancas"] - group["rating_negras"]).abs()
            row[f"gap_{minimum}_{maximum}"] = int((both & gap.ge(minimum) & gap.lt(maximum)).sum())
        rows.append(row)
    return rows


def run(root: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    games = pd.read_parquet(root / "data/processed/partidas_ajedrez_clean.parquet")
    paths = {user: root / f"data/raw/chesscom_{user}_raw.json"
             for user in load_selection(root / "config/jugadores_seleccionados.yaml")}
    observations, metadata = read_observations(paths)
    cutoff = "2026-07-04T01:29:25+00:00"
    tables, summary = {}, []
    for source, selected in [("own_archives", observations[observations["source_owner"]]),
                             ("including_incidental", observations)]:
        lookup = lookup_previous_ratings(games, selected)
        table = coverage_table(games, lookup, cutoff)
        tables[source] = table
        summary.extend(summarize(table, source))
    enriched = tables["including_incidental"]
    enriched.to_parquet(output_dir / "ratings_previos_observados.parquet", index=False)
    pd.DataFrame(summary).to_csv(output_dir / "cobertura.csv", index=False)
    result = dict(metadata=metadata, cutoff=cutoff, summary=summary,
        limitations=["Incidental ratings are last observed proxies, not necessarily the latest account rating.",
                     "No form, streak or full session statistics are derived from incidental appearances.",
                     "Partition after cutoff has already been inspected; it is not a fresh holdout."])
    (output_dir / "informe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/auditoria_cobertura"))
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.output_dir)
