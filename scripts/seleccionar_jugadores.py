#!/usr/bin/env python3
"""CLI manual para proponer una ampliación reproducible de la muestra."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running the file directly from the repository root without installation.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.player_selection import (  # noqa: E402
    InsufficientCandidatesError,
    PlayerSelector,
    apply_selection_to_config,
    write_manifest,
)
from src.utils import load_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Selecciona jugadores intermedios y avanzados fuera del DAG principal."
    )
    parser.add_argument("--config", default="config/config.yaml", help="Configuración del proyecto")
    parser.add_argument("--parquet", help="Parquet fuente; por defecto usa paths.clean_parquet")
    parser.add_argument("--manifest", help="Ruta del manifiesto; por defecto usa la configuración")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actualiza chess_com.usernames después de generar una selección completa",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    policy = config["player_selection"]
    parquet_path = Path(args.parquet or config["paths"]["clean_parquet"])
    manifest_path = Path(args.manifest or policy["manifest_path"])

    if not parquet_path.exists():
        raise FileNotFoundError(f"No se encontró el Parquet procesado: {parquet_path}")

    dataset = pd.read_parquet(parquet_path)
    selector = PlayerSelector(config)
    try:
        result = selector.select_from_dataframe(dataset)
    except InsufficientCandidatesError as exc:
        exc.result.policy["source_parquet"] = str(parquet_path)
        write_manifest(exc.result, manifest_path)
        print(f"Selección incompleta. Manifiesto: {manifest_path}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    result.policy["source_parquet"] = str(parquet_path)
    write_manifest(result, manifest_path)
    print(yaml.safe_dump(result.to_manifest()["selected"], allow_unicode=True, sort_keys=False))
    print(f"Manifiesto guardado en: {manifest_path}")

    if args.apply:
        usernames = apply_selection_to_config(
            config_path,
            policy["seed_usernames"],
            result.selected,
        )
        print(f"Configuración actualizada: {len(usernames)} usuarios en {config_path}")
    else:
        print("Vista previa solamente: config.yaml no fue modificado. Use --apply para aplicarla.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
