"""Construye los datos y gráficos de la app de la Entrega 4.

Toma lo que produce el pipeline (los JSON crudos, ``partidas_ajedrez_clean.parquet`` y
``partidas_cortes.parquet``), los reportes que exportan los notebooks 02 y 04 y el
modelo guardado, y escribe en ``web/public/app/``:

- ``resumen.json``: los números que cita el texto de la app (portada, embudo, hipótesis,
  tablas del modelo).
- ``graficos/<seccion>.json``: una spec de Vega-Lite por gráfico, generada con Altair
  (``src/app_charts.py``).

El test se recalcula con el modelo guardado y el build falla si no da lo mismo que el
notebook 04. Si cambian los datos: correr el DAG, los notebooks 02 y 04, y de nuevo
``python -m src.build_app``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from src import app_charts
from src.app_trivia import construir_trivia
from src.app_data import REPORTE_EDA, REPORTE_MODELADO, leer_reporte
from src.clean_data import DataCleaner
from src.history_transformer import HISTORY_INPUTS, attach_player_histories, player_history_payloads
from src.player_selection import load_selection
from src.predict import MODEL_PATH, PRE_GAME, RESULT_ORDER, cargar_modelo, model_input_frame
from src.utils import load_config, setup_logger

logger = setup_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SALIDA = Path("web/public/app")
# Test games shown in Explorá: a stratified sample keeps the page light (see the README).
PARTIDAS_EXPLORA = 2000
# The model is deterministic: the rebuilt test must match notebook 04 up to float noise.
TOLERANCIA = 1e-6
# Above this the page gets slow to load; the test in tests/test_build_app.py checks it too.
MAXIMO_MB = 5.0


def raw_paths(config: dict[str, Any]) -> dict[str, Path]:
    """Los JSON crudos de la lista congelada, como los lee el notebook 04."""
    usernames = load_selection(PROJECT_ROOT / config["player_selection"]["selection_path"])
    template = config["chess_com"]["raw_filename_template"]
    return {u: PROJECT_ROOT / config["paths"]["raw_dir"] / template.format(username=u) for u in usernames}


def embudo(config: dict[str, Any], paths: dict[str, Path], partidas: int) -> list[dict[str, Any]]:
    """Cuántas filas quedan después de cada paso de la limpieza del pipeline."""
    cleaner = DataCleaner(config)
    df, _ = cleaner.clean(paths)
    assert len(df) == partidas, "La limpieza no reproduce el Parquet: correr el DAG de nuevo"
    return [{"paso": name, "filas": count} for name, count in cleaner.pasos]


def partidas_vivas(games: pd.DataFrame, cuts: pd.DataFrame) -> pd.DataFrame:
    """Fracción de partidas de cada ritmo que todavía tiene fila en cada corte."""
    rows_before = len(cuts)
    rhythm = cuts[["GameUrl", "corte_ply"]].merge(games[["GameUrl", "TimeClass"]], on="GameUrl", how="left",
                                                  validate="many_to_one")
    assert len(rhythm) == rows_before, "Fan-out al unir el ritmo"
    counts = rhythm.groupby(["TimeClass", "corte_ply"], observed=True).size().rename("partidas").reset_index()
    counts["TimeClass"] = counts["TimeClass"].astype(str)
    total = games["TimeClass"].astype(str).value_counts()
    counts["siguen"] = counts["partidas"] / counts["TimeClass"].map(total)
    return counts


def filas_de_test(games: pd.DataFrame, cuts: pd.DataFrame, paths: dict[str, Path],
                  artifact: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Las filas (partida, corte) de train y de test, armadas como en el notebook 04."""
    histories = player_history_payloads(paths, games[["GameUrl", "StartTime"]], rivales=artifact["historial_rivales"])
    games = attach_player_histories(games, histories)
    split_time = games["StartTime"].quantile(0.8)
    assert split_time == pd.Timestamp(artifact["entrenado_hasta"]), "El corte temporal no es el del modelo guardado"
    context = ["GameUrl", "White", "Black", *PRE_GAME, *HISTORY_INPUTS]
    rows_before = len(cuts)
    data = cuts.merge(games.reindex(columns=context), on="GameUrl", how="left", validate="many_to_one")
    assert len(data) == rows_before, "Fan-out al unir el contexto de la partida"
    train_games = set(games.loc[games["EndTime"] < split_time, "GameUrl"])
    test_games = set(games.loc[games["StartTime"] >= split_time, "GameUrl"])
    train = data[data["GameUrl"].isin(train_games)].reset_index(drop=True)
    test = data[data["GameUrl"].isin(test_games)].reset_index(drop=True)
    return train, test


def predecir_test(train: pd.DataFrame, test: pd.DataFrame, artifact: dict[str, Any]) -> pd.DataFrame:
    """Probabilidades del modelo guardado y del piso (proporciones de train) en cada fila de test."""
    model = artifact["resultado"]
    classes = list(model.classes_)
    proba = model.predict_proba(model_input_frame(test, artifact["columnas"]))
    prior = train["resultado"].astype(str).value_counts(normalize=True).reindex(classes).to_numpy()
    result = test[["GameUrl", "corte_ply", "balance_material", "resultado"]].copy()
    result["resultado"] = result["resultado"].astype(str)
    for label, column in zip(RESULT_ORDER, ["p_blancas", "p_empate", "p_negras"]):
        result[column] = proba[:, classes.index(label)]
        result[f"piso_{column}"] = prior[classes.index(label)]
    return result


def _log_loss(frame: pd.DataFrame, prefix: str = "") -> float:
    # sklearn reads the probability columns in sorted label order: Empate, Gana Blancas, Gana Negras.
    columns = [f"{prefix}p_empate", f"{prefix}p_blancas", f"{prefix}p_negras"]
    return float(log_loss(frame["resultado"], frame[columns].to_numpy(), labels=sorted(RESULT_ORDER)))


def curva_de_test(pred: pd.DataFrame) -> pd.DataFrame:
    """Log-loss del modelo y del piso en cada corte del test."""
    rows = []
    for cut, group in pred.groupby("corte_ply"):
        model, floor = _log_loss(group), _log_loss(group, "piso_")
        rows.append({"corte_ply": int(cut), "partidas": len(group), "modelo": model, "piso": floor,
                     "mejora": 1 - model / floor})
    return pd.DataFrame(rows)


def verificar_contra_notebook(pred: pd.DataFrame, curva: pd.DataFrame, reporte: dict[str, Any]) -> dict[str, float]:
    """Falla si el test reconstruido no da lo mismo que el notebook 04."""
    test = {"log_loss": _log_loss(pred), "log_loss piso": _log_loss(pred, "piso_")}
    for key, value in test.items():
        if abs(value - reporte["test"][key]) > TOLERANCIA:
            raise AssertionError(f"Test {key}: {value:.6f} acá contra {reporte['test'][key]:.6f} en el notebook 04")
    notebook = pd.DataFrame(reporte["test_por_corte"])
    notebook = notebook[notebook["población"] == "todas"].set_index("corte_ply")
    mine = curva.set_index("corte_ply")
    gap = (mine["modelo"] - notebook.loc[mine.index, "log_loss"]).abs().max()
    if gap > TOLERANCIA:
        raise AssertionError(f"La log-loss por corte difiere del notebook 04 hasta en {gap:.2e}")
    return test


def muestra_explora(pred: pd.DataFrame, games: pd.DataFrame, random_state: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Partidas de test para Explorá, estratificadas por ritmo y nivel, con todas sus filas."""
    info = games.set_index("GameUrl").loc[pred["GameUrl"].unique()]
    fraction = min(1.0, PARTIDAS_EXPLORA / len(info))
    chosen = info.groupby(["TimeClass", "nivel_promedio"], observed=True).sample(frac=fraction, random_state=random_state)
    chosen = chosen.sort_values("StartTime", kind="stable")
    ids = pd.Series(np.arange(len(chosen)), index=chosen.index)

    # A fixed horizontal offset per game, so equal material values do not stack on one line.
    rng = np.random.default_rng(random_state)
    partidas = pd.DataFrame({
        "id": ids.to_numpy(),
        "url": chosen.index,
        "blancas": [f"{w} ({we:.0f})" for w, we in zip(chosen["White"], chosen["WhiteElo"])],
        "negras": [f"{b} ({be:.0f})" for b, be in zip(chosen["Black"], chosen["BlackElo"])],
        "titulo": [f"{w} contra {b}, {tc}: {r.lower()}" for w, b, tc, r in
                   zip(chosen["White"], chosen["Black"], chosen["TimeClass"].astype(str), chosen["resultado"].astype(str))],
        "TimeClass": chosen["TimeClass"].astype(str).to_numpy(),
        "nivel_promedio": chosen["nivel_promedio"].astype(str).to_numpy(),
        "resultado": chosen["resultado"].astype(str).to_numpy(),
        "final": chosen["Termination"].astype(str).to_numpy(),
        "desplazamiento": rng.uniform(-0.35, 0.35, len(ids)).round(2),
    })
    # Per-game fields live in `partidas`; each (game, cut) row keeps only what changes with the cut.
    filas = pred.loc[pred["GameUrl"].isin(ids.index), ["GameUrl", "corte_ply", "balance_material",
                                                        "p_blancas", "p_empate", "p_negras"]].copy()
    filas.insert(0, "id", filas.pop("GameUrl").map(ids))
    filas[["p_blancas", "p_empate", "p_negras"]] = filas[["p_blancas", "p_empate", "p_negras"]].round(3)
    return filas.sort_values(["id", "corte_ply"]).reset_index(drop=True), partidas


def _registros(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def resumen(games: pd.DataFrame, config: dict[str, Any], pasos: list[dict[str, Any]], vivas: pd.DataFrame,
            eda: dict[str, Any], modelado: dict[str, Any], curva: pd.DataFrame, test: dict[str, float],
            artifact: dict[str, Any], n_explora: int) -> dict[str, Any]:
    """Los números que cita el texto de la app, todos calculados acá o leídos de los notebooks."""
    by_cut = curva.set_index("corte_ply")
    alive_60 = vivas[vivas["corte_ply"] == 60].set_index("TimeClass")
    return {
        "portada": {
            "partidas": len(games),
            "cuentas": len(load_selection(PROJECT_ROOT / config["player_selection"]["selection_path"])),
            "mejora_antes_de_mover": float(by_cut.loc[0, "mejora"]),
            "mejora_ply_60": float(by_cut.loc[60, "mejora"]),
            "mejora_test": 1 - test["log_loss"] / test["log_loss piso"],
        },
        "datos": {
            "fuente": "PubAPI pública de Chess.com",
            "hasta_mes": config["download"]["until_month"],
            "desde": games["Date"].min().strftime("%Y-%m-%d"),
            "hasta": games["Date"].max().strftime("%Y-%m-%d"),
            "filas_cortes": int(modelado["corrida"]["filas_cortes"]),
            "cortes": config["live_prediction"]["cortes_ply"],
            "embudo": pasos,
            "siguen_al_ply_60": {k: float(v) for k, v in alive_60["siguen"].items()},
            "siguen_al_ply_60_total": float(alive_60["partidas"].sum() / len(games)),
            "siguen_al_ply_120_total": float(vivas.loc[vivas["corte_ply"] == 120, "partidas"].sum() / len(games)),
            "por_ritmo": games["TimeClass"].astype(str).value_counts().to_dict(),
            "por_nivel": games["nivel_promedio"].astype(str).value_counts().to_dict(),
            "columnas_con_fuga": modelado["columnas_con_fuga"],
        },
        "hallazgos": {
            "poblacion_comun": eda["poblacion_comun"],
            "hipotesis_antes": eda["hipotesis_antes"],
            "hipotesis_durante": eda["hipotesis_durante"],
            "eta2_material": eda["eta2_material"],
            "eta2_reloj": eda["eta2_reloj"],
        },
        "modelo": {
            "familia": artifact["familia"],
            "corrida": modelado["corrida"],
            "comparacion": modelado["comparacion"],
            "decision": modelado["decision"],
            "grilla": modelado["grilla"],
            "mejores_hiperparametros": modelado["mejores_hiperparametros"],
            "balanceo": modelado["balanceo"],
            "ratings_rivales": modelado["ratings_rivales"],
            "columnas_finales": len(artifact["columnas"]),
            "test": modelado["test"],
            "test_por_corte": _registros(curva),
            "confusion_por_fila": modelado["confusion_por_fila"],
            "confusion_por_columna": modelado["confusion_por_columna"],
            "errores_desde_ply_60": modelado["errores_desde_ply_60"],
            "importancia": modelado["importancia"][:10],
            "duracion_test": modelado["duracion_test"],
            "rango_rating": artifact["rango_rating"],
        },
        "explora": {"partidas": n_explora, "niveles": list(config["elo"]["bandas"])},
    }


def escribir(nombre: str, contenido: dict[str, Any]) -> Path:
    path = PROJECT_ROOT / SALIDA / nombre
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contenido, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = path.stat().st_size / 1e6
    assert size < MAXIMO_MB, f"{path} pesa {size:.1f} MB: achicar PARTIDAS_EXPLORA"
    logger.info("Escrito %s (%.2f MB)", path.relative_to(PROJECT_ROOT), size)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.parse_args()
    started = time.perf_counter()
    config = load_config(PROJECT_ROOT / "config" / "config.yaml")
    random_state = config["processing"]["random_state"]
    eda = leer_reporte(PROJECT_ROOT / REPORTE_EDA)
    modelado = leer_reporte(PROJECT_ROOT / REPORTE_MODELADO)
    artifact = cargar_modelo(PROJECT_ROOT / MODEL_PATH)

    games = pd.read_parquet(PROJECT_ROOT / config["paths"]["clean_parquet"])
    cuts = pd.read_parquet(PROJECT_ROOT / config["paths"]["cortes_parquet"])
    paths = raw_paths(config)
    pasos = embudo(config, paths, len(games))
    vivas = partidas_vivas(games, cuts)

    train, test = filas_de_test(games, cuts, paths, artifact)
    pred = predecir_test(train, test, artifact)
    curva = curva_de_test(pred)
    test_metrics = verificar_contra_notebook(pred, curva, modelado)
    logger.info("Test reconstruido: log-loss %.4f contra %.4f del piso, igual que el notebook 04",
                test_metrics["log_loss"], test_metrics["log_loss piso"])

    trivia_index, trivia_cases = construir_trivia(test, pred, games, paths, artifact, random_state)
    # Publish the index last so it never points to missing cases.
    for case in trivia_cases:
        escribir(f"trivia/{case['id']}.json", case)
    escribir("trivia/index.json", trivia_index)

    filas, partidas = muestra_explora(pred, games, random_state)
    eta2 = pd.concat([
        pd.DataFrame(eda["eta2_material"]).assign(variable="Material"),
        pd.DataFrame(eda["eta2_reloj"])[["corte_ply", "eta2_controlado"]]
        .rename(columns={"eta2_controlado": "eta2"}).assign(variable="Reloj, a igual material"),
    ], ignore_index=True)
    curva_larga = pd.concat([
        curva.assign(serie="Modelo", log_loss=curva["modelo"]), curva.assign(serie="Piso", log_loss=curva["piso"]),
    ])[["serie", "corte_ply", "log_loss", "mejora", "partidas"]]

    escribir("resumen.json", resumen(games, config, pasos, vivas, eda, modelado, curva, test_metrics, artifact,
                                     len(partidas)))
    escribir("graficos/datos.json", app_charts.partidas_vivas(vivas).to_dict())
    escribir("graficos/hallazgos.json", app_charts.senal_por_corte(eta2).to_dict())
    escribir("graficos/modelo.json", app_charts.modelo_contra_piso(curva_larga).to_dict())
    escribir("graficos/explora.json",
             app_charts.explora(filas, partidas, list(config["elo"]["bandas"])))
    logger.info("App construida en %.0f s", time.perf_counter() - started)


if __name__ == "__main__":
    main()
