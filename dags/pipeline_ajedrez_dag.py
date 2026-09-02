"""DAG del pipeline de partidas de ajedrez — Proyecto Integrador UTN FRM 2026.

Pregunta de investigación:
    ¿Qué combinación de ELO, apertura, modalidad de ritmo y color de piezas
    predice el resultado y la duración de una partida de ajedrez online?

Fuente: PubAPI pública de Chess.com (sin autenticación).

Estructura del grafo:
    descarga_partidas
        └── limpieza_y_parseo
                └── feature_engineering
                        └── exportar_dataset
                                └── verificar_calidad

Cada tarea mapea 1:1 a un módulo de src/:
    - descarga_partidas    → src/download_data.py (DataDownloader)
    - limpieza_y_parseo   → src/clean_data.py    (DataCleaner)
    - feature_engineering → src/feature_engineering.py (FeatureEngineer)
    - exportar_dataset    → src/pipeline.py (exporta parquet + CSV + summary)
    - verificar_calidad   → assert de los 7 criterios de calidad del dataset
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración del DAG
# ---------------------------------------------------------------------------
DEFAULT_ARGS = {
    "owner": "proyecto-integrador",
    "retries": 1,
    "email_on_failure": False,
}

CONFIG_PATH = "/project/config/config.yaml"
RAW_DIR = Path("/project/data/raw")
PROCESSED_DIR = Path("/project/data/processed")


# ---------------------------------------------------------------------------
# Tareas
# ---------------------------------------------------------------------------


def tarea_descarga(**context) -> None:
    """Descarga hasta max_games_per_user partidas rated de cada usuario configurado.

    Es idempotente: si el JSON ya existe en data/raw/, la descarga se saltea.
    Los archivos crudos se guardan tal cual llegan de la API (capa bronce).
    """
    from src.download_data import DataDownloader
    from src.utils import load_config

    config = load_config(CONFIG_PATH)
    downloader = DataDownloader(config)
    paths = downloader.download_all()
    log.info("Descarga completa. Archivos: %s", list(paths.values()))

    # Push paths to XCom so downstream tasks can read them
    context["ti"].xcom_push(key="raw_paths", value={u: str(p) for u, p in paths.items()})


def tarea_limpieza(**context) -> None:
    """Parsea los JSON crudos, deduplica por GameUrl y filtra partidas inválidas.

    Filtra: rated=True, rules=chess, TimeClass in {bullet, blitz, rapid},
    resultado no nulo, ELOs presentes, al menos 1 jugada.
    """
    from src.clean_data import DataCleaner
    from src.utils import load_config

    config = load_config(CONFIG_PATH)

    # Recover raw_paths from previous task or reconstruct from config
    raw_paths_str = context["ti"].xcom_pull(key="raw_paths", task_ids="descarga_partidas")
    if raw_paths_str:
        raw_paths = {u: Path(p) for u, p in raw_paths_str.items()}
    else:
        template = config["chess_com"]["raw_filename_template"]
        raw_paths = {
            u: RAW_DIR / template.format(username=u)
            for u in config["chess_com"]["usernames"]
        }

    cleaner = DataCleaner(config)
    df, raw_count = cleaner.clean(raw_paths)
    df = cleaner.optimize_dtypes(df)

    # Serialize to a temp parquet so the next task picks it up
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    interim_path = PROCESSED_DIR / "_interim_clean.parquet"
    df.to_parquet(interim_path, index=False)
    context["ti"].xcom_push(key="raw_row_count", value=raw_count)
    log.info("Limpieza completa: %d / %d partidas retenidas → %s", len(df), raw_count, interim_path)


def tarea_features(**context) -> None:
    """Genera features derivadas sobre el DataFrame limpio.

    Features agregadas:
        - diferencia_elo, elo_promedio, favorito
        - nivel_promedio (bandas de ELO del config)
        - modalidad (Bullet / Blitz / Rapid)
        - es_sorpresa (1 si ganó el de menor ELO)
        - familia_apertura (clasificación ECO A-E)
    """
    import pandas as pd

    from src.feature_engineering import FeatureEngineer
    from src.utils import load_config

    config = load_config(CONFIG_PATH)
    interim_path = PROCESSED_DIR / "_interim_clean.parquet"
    df = pd.read_parquet(interim_path)

    engineer = FeatureEngineer(config)
    df = engineer.transform(df)

    df.to_parquet(interim_path, index=False)
    log.info("Features generadas. Columnas finales: %s", list(df.columns))


def tarea_exportar(**context) -> None:
    """Exporta el dataset final en tres formatos:

    - data/processed/partidas_ajedrez_clean.parquet  (completo, comprimido)
    - data/processed/partidas_ajedrez_clean_sample.csv (muestra de hasta 5 000 filas)
    - data/processed/data_summary.json              (métricas de calidad)
    """
    import json

    import pandas as pd

    from src.pipeline import build_summary
    from src.utils import load_config

    config = load_config(CONFIG_PATH)
    interim_path = PROCESSED_DIR / "_interim_clean.parquet"
    df = pd.read_parquet(interim_path)

    raw_count = context["ti"].xcom_pull(key="raw_row_count", task_ids="limpieza_y_parseo") or len(df)

    # Parquet completo
    parquet_path = Path(config["paths"]["clean_parquet"])
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
    log.info("Parquet guardado: %s (%d filas)", parquet_path, len(df))

    # CSV muestra
    sample_size = min(config["processing"]["sample_size"], len(df))
    sample_path = Path(config["paths"]["clean_sample_csv"])
    df.sample(n=sample_size, random_state=config["processing"]["random_state"]).to_csv(
        sample_path, index=False
    )
    log.info("CSV muestra guardado: %s (%d filas)", sample_path, sample_size)

    # Summary JSON
    summary = build_summary(df, raw_count)
    summary_path = Path(config["paths"]["summary_json"])
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    log.info("Resumen guardado: %s", summary_path)

    # Cleanup interim file
    interim_path.unlink(missing_ok=True)


def tarea_verificar_calidad(**context) -> None:
    """Verifica los 7 criterios de calidad del dataset.

    Falla el DAG (raise AssertionError) si algún criterio no se cumple,
    garantizando que cualquier corrida en verde implica un dataset válido.

    Criterios:
        1. Clave sin duplicados (GameUrl)
        2. Volumen mínimo de 1 000 filas
        3. Al menos 5 columnas útiles
        4. Mezcla de tipos (numérico + categórico + fecha)
        5. Nulos conocidos (ninguna columna desconocida al 100 %)
        6. Sin columnas vacías (0 % de nulos en columna objetivo)
        7. Columna objetivo presente y sin nulos
    """
    import pandas as pd

    from src.utils import load_config

    config = load_config(CONFIG_PATH)
    parquet_path = Path(config["paths"]["clean_parquet"])
    df = pd.read_parquet(parquet_path)

    log.info("=== Verificación de calidad del dataset ===")
    log.info("Shape: %s", df.shape)

    # 1. Clave sin duplicados
    assert df["GameUrl"].is_unique, (
        f"❌ Criterio 1 FALLÓ: GameUrl tiene {df['GameUrl'].duplicated().sum()} duplicados"
    )
    log.info("✅ Criterio 1: clave GameUrl sin duplicados")

    # 2. Volumen mínimo
    assert len(df) >= 1_000, (
        f"❌ Criterio 2 FALLÓ: solo {len(df)} filas (mínimo 1 000)"
    )
    log.info("✅ Criterio 2: volumen suficiente (%d filas)", len(df))

    # 3. Ancho mínimo
    assert df.shape[1] >= 5, (
        f"❌ Criterio 3 FALLÓ: solo {df.shape[1]} columnas (mínimo 5)"
    )
    log.info("✅ Criterio 3: ancho suficiente (%d columnas)", df.shape[1])

    # 4. Mezcla de tipos
    dtypes = df.dtypes.astype(str)
    has_numeric = dtypes.str.contains("int|float").any()
    has_categorical = (dtypes == "category").any() or (dtypes == "object").any()
    assert has_numeric and has_categorical, (
        "❌ Criterio 4 FALLÓ: falta mezcla de tipos (numérico + categórico)"
    )
    log.info("✅ Criterio 4: mezcla de tipos presente")

    # 5 & 6. Sin columnas vacías
    empty_cols = list(df.columns[df.isna().all()])
    assert not empty_cols, (
        f"❌ Criterio 5/6 FALLÓ: columnas al 100 % nulas: {empty_cols}"
    )
    log.info("✅ Criterio 5/6: no hay columnas vacías")

    # 7. Columna objetivo presente y sin nulos
    assert "resultado" in df.columns, "❌ Criterio 7 FALLÓ: columna 'resultado' no existe"
    null_target = df["resultado"].isna().sum()
    assert null_target == 0, (
        f"❌ Criterio 7 FALLÓ: columna objetivo 'resultado' tiene {null_target} nulos"
    )
    log.info("✅ Criterio 7: columna objetivo 'resultado' sin nulos")

    # Summary to log
    log.info("=== Dataset aprobado ✅ ===")
    log.info("Filas: %d | Columnas: %d", *df.shape)
    log.info("Distribución resultado:\n%s", df["resultado"].value_counts().to_string())
    log.info("Nulos por columna (solo las que tienen):\n%s",
             df.isna().sum()[df.isna().sum() > 0].to_string() or "ninguna")


# ---------------------------------------------------------------------------
# Definición del DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="pipeline_ajedrez_chesscom",
    description="Pipeline completo: descarga Chess.com → limpieza → features → CSV verificado",
    default_args=DEFAULT_ARGS,
    schedule_interval=None,   # manual — se dispara desde la UI o con CLI
    start_date=days_ago(1),
    catchup=False,
    tags=["ajedrez", "utn-frm", "entrega-1"],
    doc_md=__doc__,
) as dag:

    descarga = PythonOperator(
        task_id="descarga_partidas",
        python_callable=tarea_descarga,
    )

    limpieza = PythonOperator(
        task_id="limpieza_y_parseo",
        python_callable=tarea_limpieza,
    )

    features = PythonOperator(
        task_id="feature_engineering",
        python_callable=tarea_features,
    )

    exportar = PythonOperator(
        task_id="exportar_dataset",
        python_callable=tarea_exportar,
    )

    verificar = PythonOperator(
        task_id="verificar_calidad",
        python_callable=tarea_verificar_calidad,
    )

    # Grafo lineal: cada etapa depende de la anterior
    descarga >> limpieza >> features >> exportar >> verificar
