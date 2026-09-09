"""CLI que orquesta el pipeline completo: descarga -> parseo -> limpieza -> features -> export.

Fuente: partidas de ajedrez online reales, PubAPI pública de Chess.com.

Uso
----
    python -m src.pipeline
    python -m src.pipeline --config config/config.yaml --skip-download
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

from src.clean_data import DataCleaner
from src.download_data import DataDownloader
from src.feature_engineering import FeatureEngineer
from src.utils import load_config, setup_logger

logger = setup_logger(__name__)
console = Console()


def build_summary(df: pd.DataFrame, raw_row_count: int) -> dict[str, Any]:
    """Arma el diccionario de resumen que se exporta a ``data_summary.json``.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset final, ya limpio y con features.
    raw_row_count : int
        Cantidad de registros leídos de los JSON crudos, antes de cualquier filtro.

    Returns
    -------
    dict[str, Any]
        Resumen serializable a JSON.
    """
    return {
        "partidas_raw": int(raw_row_count),
        "partidas_procesadas": int(len(df)),
        "partidas_descartadas": int(raw_row_count - len(df)),
        "tasa_retencion_pct": round(100 * len(df) / raw_row_count, 2) if raw_row_count else 0.0,
        "distribucion_resultado": df["resultado"].value_counts().to_dict(),
        "distribucion_modalidad": df["modalidad"].value_counts().to_dict(),
        "distribucion_nivel_promedio": df["nivel_promedio"].value_counts().to_dict(),
        "distribucion_familia_apertura": _opening_family_counts(df),
        "tasa_sorpresa_pct": round(100 * df["es_sorpresa"].mean(), 2),
        "cantidad_jugadas_promedio": round(float(df["cantidad_jugadas"].mean()), 1),
        "nulos_por_columna": df.isna().sum().loc[lambda s: s > 0].to_dict(),
        # Categorías "fallback": cuando el crudo no trae el dato, no queda nulo sino una
        # etiqueta de reemplazo (familia_apertura="Desconocida" si el ECO no clasifica,
        # Termination="otro" si el motivo no matchea el vocabulario conocido). Es una
        # decisión de diseño válida, pero contra la dimensión completitud esos casos son
        # missingness disfrazada: se reportan explícitamente para que sean visibles y no
        # se confundan con datos presentes de verdad.
        "categorias_fallback": _fallback_category_counts(df),
    }


def _opening_family_counts(df: pd.DataFrame) -> dict[str, int]:
    """Cuenta las seis categorías de familia ECO, incluyendo las que tienen cero filas."""
    familias = ["Flanco", "Semiabierta", "Abierta", "Cerrada", "India", "Desconocida"]
    conteos = df["familia_apertura"].value_counts().reindex(familias, fill_value=0)
    return {familia: int(conteo) for familia, conteo in conteos.items()}


def _fallback_category_counts(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Cuenta las filas que caen en categorías de reemplazo (ver ``build_summary``)."""
    total = len(df)
    fallbacks = {
        "familia_apertura": "Desconocida",  # ECO ausente o fuera de A-E
        "Termination": "otro",              # motivo de finalización no reconocido
    }
    resumen: dict[str, dict[str, Any]] = {}
    for col, etiqueta in fallbacks.items():
        n = int((df[col] == etiqueta).sum())
        resumen[f"{col}={etiqueta}"] = {
            "filas": n,
            "pct": round(100 * n / total, 2) if total else 0.0,
        }
    return resumen


def run_pipeline(config_path: str = "config/config.yaml", skip_download: bool = False) -> pd.DataFrame:
    """Ejecuta el pipeline completo de principio a fin.

    Parameters
    ----------
    config_path : str, optional
        Ruta al archivo de configuración YAML.
    skip_download : bool, optional
        Si es ``True``, no intenta descargar (asume que los PGN ya existen
        en ``data/raw``).

    Returns
    -------
    pd.DataFrame
        Dataset final, limpio y con features.
    """
    config = load_config(config_path)

    raw_dir = Path(config["paths"]["raw_dir"])
    processed_dir = Path(config["paths"]["processed_dir"])
    processed_dir.mkdir(parents=True, exist_ok=True)

    usernames = config["chess_com"]["usernames"]
    template = config["chess_com"]["raw_filename_template"]
    raw_paths = {u: raw_dir / template.format(username=u) for u in usernames}

    if not skip_download:
        downloader = DataDownloader(config)
        try:
            raw_paths = downloader.download_all()
        except Exception:
            logger.exception("La descarga de partidas falló.")
            raise
    elif not all(p.exists() for p in raw_paths.values()):
        faltantes = [str(p) for p in raw_paths.values() if not p.exists()]
        raise FileNotFoundError(
            f"--skip-download fue pasado pero faltan: {faltantes}. "
            "Corré el pipeline sin ese flag al menos una vez."
        )

    cleaner = DataCleaner(config)
    df, raw_row_count = cleaner.clean(raw_paths)
    df = cleaner.optimize_dtypes(df)

    engineer = FeatureEngineer(config)
    df = engineer.transform(df)

    clean_parquet_path = Path(config["paths"]["clean_parquet"])
    clean_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(clean_parquet_path, engine="pyarrow", compression="snappy", index=False)
    logger.info("Dataset final guardado en %s", clean_parquet_path)

    sample_path = Path(config["paths"]["clean_sample_csv"])
    sample_size = min(config["processing"]["sample_size"], len(df))
    df.sample(n=sample_size, random_state=config["processing"]["random_state"]).to_csv(
        sample_path, index=False
    )
    logger.info("Sample de validación (%d filas) guardado en %s", sample_size, sample_path)

    summary = build_summary(df, raw_row_count)
    summary_path = Path(config["paths"]["summary_json"])
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Resumen guardado en %s", summary_path)

    _print_summary_table(summary)
    return df


def _print_summary_table(summary: dict[str, Any]) -> None:
    """Imprime una tabla formateada en consola con el resumen del pipeline."""
    table = Table(title="Resumen del pipeline — Ajedrez Online (Chess.com)")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="magenta")

    table.add_row("Partidas crudas", f"{summary['partidas_raw']:,}")
    table.add_row("Partidas procesadas", f"{summary['partidas_procesadas']:,}")
    table.add_row("Registros descartados", f"{summary['partidas_descartadas']:,}")
    table.add_row("Tasa de retención", f"{summary['tasa_retencion_pct']}%")
    table.add_row("Jugadas promedio por partida", f"{summary['cantidad_jugadas_promedio']}")
    table.add_row("Tasa de sorpresas (gana el de menor ELO)", f"{summary['tasa_sorpresa_pct']}%")
    for clase, cantidad in summary["distribucion_resultado"].items():
        table.add_row(f"resultado = {clase}", f"{cantidad:,}")

    console.print(table)


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description="Pipeline de datos — Ajedrez Online (Chess.com)")
    parser.add_argument("--config", default="config/config.yaml", help="Ruta al config YAML")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="No descargar; usar los PGN ya presentes en data/raw",
    )
    args = parser.parse_args()

    run_pipeline(config_path=args.config, skip_download=args.skip_download)


if __name__ == "__main__":
    main()
