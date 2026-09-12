"""DAG del pipeline de partidas de ajedrez — Proyecto Integrador UTN FRM 2026.

Pregunta de investigación:
    ¿Qué combinación de ELO, apertura, modalidad de ritmo y color de piezas
    predice el resultado y la duración de una partida de ajedrez online?

Fuente: PubAPI pública de Chess.com (sin autenticación).

Estructura del grafo:
    listar_jugadores
        └── descarga_usuario  (mapeada por cuenta con .expand())
                └── consolidar_descarga
                        └── limpieza_y_parseo
                                └── ingenieria_de_caracteristicas
                                        └── verificar_calidad
                                                └── exportar_dataset

Módulos de src/ detrás de cada tarea:
    - listar_jugadores    → src/player_selection.py (PlayerSelector + bootstrap)
    - descarga_usuario / consolidar_descarga → src/download_data.py (DataDownloader)
    - limpieza_y_parseo   → src/clean_data.py    (DataCleaner)
    - ingenieria_de_caracteristicas → src/feature_engineering.py (FeatureEngineer)
    - verificar_calidad   → assert de los 7 criterios sobre el parquet INTERMEDIO
    - exportar_dataset    → src/pipeline.py (exporta parquet + CSV + summary)

La descarga se paraleliza por cuenta con dynamic task mapping (.expand()); la tolerancia a
fallos (min_users_ok / min_total_games) se evalúa en consolidar_descarga, DESPUÉS del fan-out.
La validación corre ANTES de exportar: si el dataset no cumple, ``exportar_dataset`` no
llega a correr y no se materializan artefactos finales de un dataset inválido.

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
    description="Pipeline completo: descarga Chess.com → limpieza → ingeniería de características → CSV verificado",
    default_args=DEFAULT_ARGS,
    schedule=None,  # manual — se dispara desde la UI o con CLI
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    tags=["ajedrez", "utn-frm", "entrega-1"],
    doc_md=__doc__,
)
def pipeline_ajedrez_chesscom():
    """Fan-out de descarga por cuenta (.expand()) + cadena lineal; las dependencias
    salen de pasar los returns de una tarea como argumento de la siguiente."""

    @task(task_id="listar_jugadores")
    def listar_jugadores() -> list[str]:
        """Selecciona jugadores automáticamente por banda de ELO.

        Si existe un parquet procesado de una corrida anterior, extrae candidatos
        de los oponentes observados en el parquet (rápido, sin red). Si no hay
        parquet previo (primera corrida), consulta la PubAPI para descubrir
        oponentes recientes de cada seed.

        En ambos casos valida los candidatos contra la PubAPI y selecciona por
        banda hasta cubrir los objetivos de ``player_selection.target_per_band``.

        Devuelve la lista combinada (seeds + seleccionados) como fuente del
        ``.expand()`` de descarga.
        """
        import pandas as pd

        from src.player_selection import (
            PlayerSelector,
            write_manifest,
        )
        from src.utils import load_config

        _enter_project_root()
        config = load_config(CONFIG_PATH)
        parquet_path = Path(config["paths"]["clean_parquet"])

        selector = PlayerSelector(config)

        if parquet_path.exists():
            log.info(
                "Parquet procesado encontrado (%s). Extrayendo oponentes del dataset.",
                parquet_path,
            )
            df = pd.read_parquet(parquet_path)
        else:
            log.info(
                "Sin parquet previo (%s). Descubriendo oponentes desde la API...",
                parquet_path,
            )
            df = selector.discover_opponents_from_api()

        jugadores, result = selector.build_username_list(df)

        # Save the manifest for auditability.
        manifest_path = Path(config["player_selection"]["manifest_path"])
        write_manifest(result, manifest_path)
        log.info("Manifiesto de selección guardado en %s", manifest_path)

        log.info("Jugadores a descargar (%d): %s", len(jugadores), jugadores)
        return jugadores

    # max_active_tis_per_dag=3: no es arbitrario. Cada cuenta emite requests en serie con
    # request_delay=0.25s y reintentos con backoff ante 429/5xx (ver DataDownloader). Correr
    # las 8 cuentas en paralelo multiplicaría ×8 la tasa de requests contra Chess.com y
    # dispararía rate-limiting; con 3 en paralelo el burst queda acotado, el backoff absorbe
    # algún 429 ocasional y en cold-run rinde ~3× sobre el serial. En re-runs es indistinto
    # porque las descargas idempotentes se saltean.
    @task(
        task_id="descarga_usuario",
        map_index_template="{{ username }}",  # muestra el username en el índice del map en la UI
        max_active_tis_per_dag=3,
    )
    def descarga_usuario(username: str) -> dict:
        """Descarga las partidas de UNA cuenta, tolerando su propio fallo.

        Idempotente (si el JSON ya existe, se saltea). No re-lanza la excepción: devuelve un
        dict de estado para que un usuario caído no rompa el fan-out; los mínimos se evalúan
        después en ``consolidar_descarga``.
        """
        from airflow.sdk import get_current_context

        from src.download_data import DataDownloader
        from src.utils import load_config

        get_current_context()["username"] = username  # alimenta map_index_template
        _enter_project_root()
        config = load_config(CONFIG_PATH)
        downloader = DataDownloader(config)
        dest = downloader.dest_for(username)
        try:
            path = downloader.download_user_games(username, dest)
            games = downloader.count_games(path)
            log.info("Descarga OK de %s: %d partidas → %s", username, games, path)
            return {"username": username, "path": str(path), "games": games, "ok": True}
        except Exception as exc:  # noqa: BLE001 - se degrada por usuario a propósito
            log.warning("Descarga de %s falló, se saltea: %s: %s", username, type(exc).__name__, exc)
            return {"username": username, "path": None, "games": 0, "ok": False}

    @task(task_id="consolidar_descarga")
    def consolidar_descarga(resultados: list[dict]) -> dict[str, str]:
        """Reduce los resultados mapeados: aplica los mínimos y arma las rutas crudas.

        Recibe la lista de dicts de estado de ``descarga_usuario`` (uno por cuenta), exige
        ``min_users_ok`` / ``min_total_games`` con la MISMA lógica que el CLI
        (``DataDownloader.enforce_minimums``) y devuelve por XCom las rutas de los usuarios
        exitosos (metadatos, no datos) para ``limpieza_y_parseo``.
        """
        from src.download_data import DataDownloader
        from src.utils import load_config

        _enter_project_root()
        config = load_config(CONFIG_PATH)
        downloader = DataDownloader(config)

        ok = {r["username"]: r["path"] for r in resultados if r["ok"]}
        failed = {r["username"]: "descarga falló" for r in resultados if not r["ok"]}
        total_games = sum(r["games"] for r in resultados if r["ok"])
        log.info(
            "Descarga consolidada: %d/%d usuarios OK, %d partidas crudas. Fallaron: %s",
            len(ok), len(resultados), total_games, list(failed) or "ninguno",
        )
        downloader.enforce_minimums(len(ok), total_games, failed)
        return ok

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
            # Sólo se reconstruyen rutas de usuarios cuyo JSON crudo EXISTE en disco. El
            # config lista los 8 usuarios objetivo, pero la descarga tolera fallos por
            # usuario (min_users_ok): reconstruir a ciegas para todos incluía cuentas que
            # pudieron no descargarse y hacía explotar el parseo con FileNotFoundError.
            template = config["chess_com"]["raw_filename_template"]
            paths = {
                u: RAW_DIR / template.format(username=u)
                for u in config["chess_com"]["usernames"]
                if (RAW_DIR / template.format(username=u)).exists()
            }
            if not paths:
                raise FileNotFoundError(
                    f"raw_paths vacío y no hay JSON crudos en {RAW_DIR}: "
                    "correr descarga_partidas primero."
                )
            log.warning(
                "raw_paths vacío; reconstruidas %d rutas desde disco: %s",
                len(paths), sorted(paths),
            )

        cleaner = DataCleaner(config)
        df, raw_count = cleaner.clean(paths)
        df = cleaner.optimize_dtypes(df)

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(INTERIM_PATH, index=False)
        log.info("Limpieza completa: %d / %d partidas retenidas → %s", len(df), raw_count, INTERIM_PATH)
        return raw_count

    @task(task_id="ingenieria_de_caracteristicas")
    def ingenieria_de_caracteristicas(raw_count: int) -> int:
        """Genera características derivadas sobre el DataFrame limpio.

        Recibe ``raw_count`` solo para ordenar la cadena (depende de ``limpieza`` y
        precede a ``exportar``) y para llevar el conteo hasta el resumen; su trabajo
        real es leer y reescribir ``_interim_clean.parquet``.

        Features agregadas:
            - diferencia_elo, elo_promedio
            - nivel_promedio (bandas de ELO del config)
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
        log.info("Características generadas. Columnas finales: %s", list(df.columns))
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
    def verificar_calidad(raw_count: int) -> int:
        """Verifica los 7 criterios de calidad sobre el parquet INTERMEDIO.

        Corre ANTES de ``exportar_dataset``: valida el DataFrame ya con características derivadas
        (``_interim_clean.parquet``) y, sólo si pasa, deja que ``exportar`` materialice
        los artefactos finales. Falla el DAG (raise AssertionError) si algún criterio no
        se cumple, garantizando que cualquier artefacto exportado corresponde a un dataset
        válido (antes esta tarea releía el Parquet final ya escrito).

        Recibe ``raw_count`` sólo para encadenar (depende de ``ingenieria_de_caracteristicas``) y lo
        retorna para que ``exportar`` lo use en el resumen.

        Criterios:
            1. Clave sin duplicados (GameUrl)
            2. Volumen mínimo final (quality.min_final_games)
            3. Al menos 5 columnas
            4. Mezcla de tipos (numérico + categórico + fecha)
            5. Nulos conocidos y documentados (solo en columnas de NULOS_DOCUMENTADOS)
            6. Sin columnas 100 % vacías
            7. Columnas objetivo (resultado, cantidad_jugadas) presentes y sin nulos
        """
        import pandas as pd

        from src.utils import load_config

        # Columnas donde se aceptan nulos, con su explicación (criterio 5). Hoy el
        # pipeline descarta las filas incompletas en vez de imputar, así que el
        # conjunto está vacío: cualquier nulo inesperado hace fallar el DAG.
        nulos_documentados: dict[str, str] = {}

        _enter_project_root()
        config = load_config(CONFIG_PATH)
        # Se valida el parquet intermedio (post ingeniería de características): tiene el mismo
        # contenido que el final, pero validarlo antes de exportar evita escribir
        # Parquet/CSV/summary de un dataset que no cumple.
        df = pd.read_parquet(INTERIM_PATH)

        log.info("=== Verificación de calidad del dataset ===")
        log.info("Shape: %s", df.shape)

        # 1. Clave sin duplicados
        assert df["GameUrl"].is_unique, (
            f"❌ Criterio 1 FALLÓ: GameUrl tiene {df['GameUrl'].duplicated().sum()} duplicados"
        )
        log.info("✅ Criterio 1: clave GameUrl sin duplicados")

        # 2. Volumen mínimo
        # Este es el mínimo del dataset ANALIZABLE, por eso es explícito y se toma de
        # quality.min_final_games. download.min_total_games controla otra cosa: que la
        # fuente haya entregado suficiente crudo. No se descuenta un porcentaje aquí.
        min_rows = config["quality"]["min_final_games"]
        assert len(df) >= min_rows, (
            f"❌ Criterio 2 FALLÓ: quedaron {len(df)} partidas válidas tras la limpieza "
            f"(mínimo final explícito {min_rows}; crudas leídas {raw_count})"
        )
        log.info("✅ Criterio 2: volumen suficiente (%d filas, mínimo %d)", len(df), min_rows)

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

        # 4b. Rangos plausibles de ELO (dimensión precisión — extensión propia, no
        # altera la numeración de los 7 criterios de la cátedra).
        # Rango plausible de rating Glicko de Chess.com en vivo: piso 100 (cuentas
        # nuevas/débiles rondan varios cientos; nunca ratings de un o dos dígitos) y
        # techo amplio 4000. No pretende fijar el récord histórico: deja margen a futuros
        # picos de élite y detecta solo valores claramente corruptos.
        # Un valor fuera de [100, 4000] no es un jugador real: es corrupción del dato
        # (0, negativos, ratings absurdos por un parseo mal hecho). Los descarta el DAG.
        ELO_MIN, ELO_MAX = 100, 4000
        for col in ("WhiteElo", "BlackElo"):
            fuera_rango = df[(df[col] < ELO_MIN) | (df[col] > ELO_MAX)]
            assert fuera_rango.empty, (
                f"❌ Precisión FALLÓ: {len(fuera_rango)} filas con {col} fuera de "
                f"[{ELO_MIN}, {ELO_MAX}] (min={df[col].min()}, max={df[col].max()})"
            )
        log.info(
            "✅ Precisión: WhiteElo/BlackElo dentro de [%d, %d] (rangos observados %d-%d / %d-%d)",
            ELO_MIN, ELO_MAX,
            df["WhiteElo"].min(), df["WhiteElo"].max(),
            df["BlackElo"].min(), df["BlackElo"].max(),
        )

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

        # Observabilidad de volumen (dimensión actualidad). Guarda el volumen de la última
        # corrida exitosa en una Airflow Variable y AVISA (no frena) si la corrida actual se
        # desvía mucho del baseline.
        # Umbral 5 %: `download.until_month` está congelado a propósito para esta entrega
        # (config: "2026-08"), así que la fuente no incorpora partidas nuevas y el volumen
        # debería ser estable entre corridas (una descarga desde cero reproduce el mismo
        # conjunto). Con ese contexto no hay razón legítima para que el volumen se mueva: un
        # desvío > 5 % señala un cambio real (until_month movido, filtro tocado, fuente
        # alterada) y merece revisión — pero se avisa, no se rompe el DAG, porque no invalida
        # el dataset por sí solo. Cuando en Entrega 2 se descongele until_month, este umbral
        # habrá que revisarlo (ahí sí se espera crecimiento de volumen).
        from airflow.sdk import Variable

        baseline_key = "pipeline_ajedrez_volumen_baseline"
        baseline = Variable.get(baseline_key, default=None)
        if baseline is not None and int(baseline) > 0:
            desvio = abs(len(df) - int(baseline)) / int(baseline)
            if desvio > 0.05:
                log.warning(
                    "⚠️ Volumen %d se desvía %.1f%% del baseline %s (>5%%). "
                    "until_month está congelado: revisar si cambió la config o la fuente.",
                    len(df), 100 * desvio, baseline,
                )
            else:
                log.info("Volumen %d dentro del ±5%% del baseline %s.", len(df), baseline)
        else:
            log.info("Sin baseline previo de volumen; se establece con esta corrida.")
        # La Task Execution API de Airflow 3 (PutVariable) exige que el value sea str; se
        # guarda como texto y se relee con int(...) más arriba. Pasar un int crudo rompe con
        # ValidationError sólo bajo el worker real (dags test no valida ese contrato).
        Variable.set(baseline_key, str(len(df)))
        log.info("Baseline de volumen actualizado a %d (%s).", len(df), baseline_key)

        return raw_count

    # La descarga se abre en fan-out por cuenta (.expand()) y se cierra en
    # consolidar_descarga; de ahí en adelante el grafo es lineal. La validación
    # (verificar_calidad) corre antes de exportar: si el dataset no cumple, exportar
    # no llega a escribir los artefactos finales.
    jugadores = listar_jugadores()
    resultados = descarga_usuario.expand(username=jugadores)
    raw_paths = consolidar_descarga(resultados)
    raw_count = limpieza(raw_paths)
    raw_count_fe = ingenieria_de_caracteristicas(raw_count)
    raw_count_ok = verificar_calidad(raw_count_fe)
    exportar(raw_count_ok)


pipeline_ajedrez_chesscom()
