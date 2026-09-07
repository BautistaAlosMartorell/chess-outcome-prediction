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

Escrito con la TaskFlow API de Airflow 3 (``@dag`` / ``@task`` de ``airflow.sdk``).
Por XCom viajan solo metadatos (rutas y conteos); el DataFrame intermedio se
serializa en disco (``_interim_clean.parquet``) y no toca la base de metadatos.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

log = logging.getLogger(__name__)

# The Airflow worker runs with CWD = AIRFLOW_HOME (/opt/airflow), which is *not*
# a mounted volume. The relative paths in config.yaml (data/raw, data/processed)
# must resolve against the project root that docker-compose mounts from the host,
# otherwise every artifact the pipeline writes is trapped inside the container.
# Each task calls _enter_project_root() before touching the filesystem.
PROJECT_ROOT = "/project"


def _enter_project_root() -> None:
    """Set the working directory to the mounted project root (see note above)."""
    os.chdir(PROJECT_ROOT)


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
INTERIM_PATH = PROCESSED_DIR / "_interim_clean.parquet"


@dag(
    dag_id="pipeline_ajedrez_chesscom",
    description="Pipeline completo: descarga Chess.com → limpieza → features → CSV verificado",
    default_args=DEFAULT_ARGS,
    schedule=None,  # manual — se dispara desde la UI o con CLI
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    tags=["ajedrez", "utn-frm", "entrega-1"],
    doc_md=__doc__,
)
def pipeline_ajedrez_chesscom():
    """Grafo lineal de cinco tareas; las dependencias salen de pasar los returns."""

    @task(task_id="descarga_partidas")
    def descarga() -> dict[str, str]:
        """Descarga hasta max_games_per_user partidas rated de cada usuario configurado.

        Es idempotente: si el JSON ya existe en data/raw/, la descarga se saltea.
        Los archivos crudos se guardan tal cual llegan de la API (capa bronce).
        Devuelve por XCom las rutas crudas (metadatos, no datos).
        """
        from src.download_data import DataDownloader
        from src.utils import load_config

        _enter_project_root()
        config = load_config(CONFIG_PATH)
        downloader = DataDownloader(config)
        paths = downloader.download_all()
        raw_paths = {u: str(p) for u, p in paths.items()}
        log.info("Descarga completa. Archivos: %s", list(raw_paths.values()))
        return raw_paths

    @task(task_id="limpieza_y_parseo")
    def limpieza(raw_paths: dict[str, str]) -> int:
        """Parsea los JSON crudos, deduplica por GameUrl y filtra partidas inválidas.

        Filtra: rated=True, rules=chess, TimeClass in {bullet, blitz, rapid},
        resultado no nulo, ELOs presentes, al menos 5 medio-movimientos (MIN_PLIES).
        Escribe el DataFrame limpio en disco y devuelve el conteo crudo por XCom.
        """
        from src.clean_data import DataCleaner
        from src.utils import load_config

        _enter_project_root()
        config = load_config(CONFIG_PATH)

        # raw_paths llega por XCom; si viniera vacío, se reconstruye desde el config.
        if raw_paths:
            paths = {u: Path(p) for u, p in raw_paths.items()}
        else:
            template = config["chess_com"]["raw_filename_template"]
            paths = {
                u: RAW_DIR / template.format(username=u)
                for u in config["chess_com"]["usernames"]
            }

        cleaner = DataCleaner(config)
        df, raw_count = cleaner.clean(paths)
        df = cleaner.optimize_dtypes(df)

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(INTERIM_PATH, index=False)
        log.info("Limpieza completa: %d / %d partidas retenidas → %s", len(df), raw_count, INTERIM_PATH)
        return raw_count

    @task(task_id="feature_engineering")
    def feature_engineering(raw_count: int) -> int:
        """Genera features derivadas sobre el DataFrame limpio.

        Recibe ``raw_count`` solo para ordenar la cadena (depende de ``limpieza`` y
        precede a ``exportar``) y para llevar el conteo hasta el resumen; su trabajo
        real es leer y reescribir ``_interim_clean.parquet``.

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

        _enter_project_root()
        config = load_config(CONFIG_PATH)
        df = pd.read_parquet(INTERIM_PATH)

        engineer = FeatureEngineer(config)
        df = engineer.transform(df)

        df.to_parquet(INTERIM_PATH, index=False)
        log.info("Features generadas. Columnas finales: %s", list(df.columns))
        return raw_count

    @task(task_id="exportar_dataset")
    def exportar(raw_count: int) -> str:
        """Exporta el dataset final en tres formatos y devuelve la ruta del Parquet.

        - data/processed/partidas_ajedrez_clean.parquet  (completo, comprimido)
        - data/processed/partidas_ajedrez_clean_sample.csv (muestra de hasta 5 000 filas)
        - data/processed/data_summary.json              (métricas de calidad)
        """
        import json

        import pandas as pd

        from src.pipeline import build_summary
        from src.utils import load_config

        _enter_project_root()
        config = load_config(CONFIG_PATH)
        df = pd.read_parquet(INTERIM_PATH)

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
        INTERIM_PATH.unlink(missing_ok=True)
        return str(parquet_path)

    @task(task_id="verificar_calidad")
    def verificar_calidad(parquet_path: str) -> None:
        """Verifica los 7 criterios de calidad del dataset.

        Falla el DAG (raise AssertionError) si algún criterio no se cumple,
        garantizando que cualquier corrida en verde implica un dataset válido.

        Criterios:
            1. Clave sin duplicados (GameUrl)
            2. Volumen mínimo de 1 000 filas
            3. Al menos 5 columnas
            4. Mezcla de tipos (numérico + categórico + fecha)
            5. Nulos conocidos y documentados (solo en columnas de NULOS_DOCUMENTADOS)
            6. Sin columnas 100 % vacías
            7. Columnas objetivo (resultado, cantidad_jugadas) presentes y sin nulos
        """
        import pandas as pd

        # Columnas donde se aceptan nulos, con su explicación (criterio 5). Hoy el
        # pipeline descarta las filas incompletas en vez de imputar, así que el
        # conjunto está vacío: cualquier nulo inesperado hace fallar el DAG.
        nulos_documentados: dict[str, str] = {}

        _enter_project_root()
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

        # 4. Mezcla de tipos: numérico + categórico + fecha
        dtypes = df.dtypes.astype(str)
        has_numeric = dtypes.str.contains("int|float", case=False).any()
        has_categorical = dtypes.isin(["category", "object", "string", "str"]).any()
        has_datetime = dtypes.str.contains("datetime").any()
        assert has_numeric and has_categorical and has_datetime, (
            "❌ Criterio 4 FALLÓ: falta mezcla de tipos "
            f"(numérico={has_numeric}, categórico={has_categorical}, fecha={has_datetime})"
        )
        log.info("✅ Criterio 4: mezcla de tipos presente (numérico + categórico + fecha)")

        # 5. Nulos conocidos y documentados
        cols_con_nulos = set(df.columns[df.isna().any()])
        nulos_inesperados = cols_con_nulos - set(nulos_documentados)
        assert not nulos_inesperados, (
            f"❌ Criterio 5 FALLÓ: nulos no documentados en {sorted(nulos_inesperados)}"
        )
        log.info("✅ Criterio 5: nulos conocidos (columnas con nulos: %s)", sorted(cols_con_nulos) or "ninguna")

        # 6. Sin columnas 100 % vacías
        empty_cols = list(df.columns[df.isna().all()])
        assert not empty_cols, (
            f"❌ Criterio 6 FALLÓ: columnas al 100 % nulas: {empty_cols}"
        )
        log.info("✅ Criterio 6: no hay columnas 100 %% vacías")

        # 7. Columnas objetivo presentes y sin nulos
        for target in ("resultado", "cantidad_jugadas"):
            assert target in df.columns, f"❌ Criterio 7 FALLÓ: columna objetivo '{target}' no existe"
            n_nulos = int(df[target].isna().sum())
            assert n_nulos == 0, (
                f"❌ Criterio 7 FALLÓ: columna objetivo '{target}' tiene {n_nulos} nulos"
            )
        log.info("✅ Criterio 7: columnas objetivo 'resultado' y 'cantidad_jugadas' sin nulos")

        # Summary to log
        log.info("=== Dataset aprobado ✅ ===")
        log.info("Filas: %d | Columnas: %d", *df.shape)
        log.info("Distribución resultado:\n%s", df["resultado"].value_counts().to_string())
        log.info("Nulos por columna (solo las que tienen):\n%s",
                 df.isna().sum()[df.isna().sum() > 0].to_string() or "ninguna")

    # Grafo lineal: cada etapa consume el output de la anterior.
    raw_paths = descarga()
    raw_count = limpieza(raw_paths)
    raw_count_fe = feature_engineering(raw_count)
    parquet_path = exportar(raw_count_fe)
    verificar_calidad(parquet_path)


pipeline_ajedrez_chesscom()
