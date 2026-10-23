"""Predicción jugada a jugada con el modelo de la Entrega 3, para la app de la Entrega 4.

Las columnas que usa el modelo se definen acá y el notebook 04 las importa: así el
entrenamiento y la app arman exactamente la misma tabla. ``predecir`` recibe el PGN de
una partida y lo que se sabía antes de empezar, recalcula las features de posición y
reloj en cada ply con ``game_cut_features`` (la misma función que arma el dataset) y
devuelve la probabilidad de cada resultado en cada jugada.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import chess.pgn
import joblib
import pandas as pd

from src.history_transformer import HISTORY_INPUTS
from src.live_features import game_cut_features
from src.rating_history import FORM_COLUMNS, STYLE_COLUMNS

RESULT_ORDER = ["Gana Blancas", "Empate", "Gana Negras"]
MODEL_PATH = Path("models/modelo_en_vivo.joblib")

# Lo que se sabe antes de la primera jugada. El rating previo sale del historial de la
# cuenta o, para un rival, de las partidas descargadas donde aparece; si no hay, NaN.
PRE_GAME = ["TimeClass", "tiempo_base_seg", "incremento_seg", "EsTorneo", "elo_blancas_previo", "elo_negras_previo"]
# Forma reciente de cada lado (src/rating_history.py), con la misma regla anti-fuga.
FORM = [f"{column}_{side}" for column in FORM_COLUMNS for side in ("blancas", "negras")]
# Estilo con el reloj de cada lado (src/rating_history.py): pierde por tiempo, juega apurado.
STYLE = [f"{column}_{side}" for column in STYLE_COLUMNS for side in ("blancas", "negras")]
CLOCKS = [
    "reloj_blancas_seg", "reloj_negras_seg", "reloj_frac_blancas", "reloj_frac_negras", "diferencia_reloj_seg",
    "gasto_reciente_blancas_seg", "gasto_reciente_negras_seg",
]
# Posición y relojes en el corte (src/live_features.py). corte_ply es el ply actual.
LIVE = [
    "corte_ply", "turno_blancas", "en_jaque", "movilidad", "promociones", "balance_material",
    "material_no_peon_frac", "material_blancas", "material_negras", "jaques_blancas", "jaques_negras",
    "capturas_blancas", "capturas_negras", "enroco_blancas", "enroco_negras", "derechos_enroque_blancas",
    "derechos_enroque_negras", *CLOCKS,
]
# Calidad de la posición más allá del conteo de material (src/live_features.py). El
# notebook 04 prueba cada grupo por separado y deja los que superan su regla.
POSITION_GROUPS = {
    "material colgado": ["material_colgado_blancas", "material_colgado_negras"],
    "ataques al rey": ["ataques_al_rey_blancas", "ataques_al_rey_negras"],
    "peones pasados": ["peones_pasados_blancas", "peones_pasados_negras"],
    "movilidad de cada bando": ["movilidad_blancas", "movilidad_negras"],
}
POSITION = [column for group in POSITION_GROUPS.values() for column in group]
CATEGORICAL = ["TimeClass", "matchup_apertura"]


def model_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Las columnas del modelo con tipos fijos: categóricas como texto, el resto float.

    Una columna que falta queda NaN (por ejemplo, la forma del rival). Los booleanos pasan
    a 0/1. No aprende nada de los datos: es la misma transformación en entrenamiento y en
    la app.
    """
    frame = df.reindex(columns=columns)
    for column in columns:
        if column in CATEGORICAL:
            frame[column] = frame[column].astype(str)
        else:
            frame[column] = pd.to_numeric(frame[column]).astype("float64")
    return frame


def model_input_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Entrada del Pipeline con observaciones del historial, aún sin agregarlas."""
    frame = model_frame(df, columns)
    for column in ["TimeClass", *HISTORY_INPUTS]:
        if column in df:
            frame[column] = df[column]
    return frame


def cargar_modelo(path: Path | str = MODEL_PATH) -> dict[str, Any]:
    """Carga el artefacto que guarda el notebook 04 (pipelines y columnas)."""
    return joblib.load(path)


def predecir(
    pgn: str, contexto: Mapping[str, Any], modelo: Mapping[str, Any], en_curso: bool = False
) -> pd.DataFrame:
    """Probabilidad de cada resultado en cada ply de la partida (0 = antes de mover).

    ``contexto`` trae lo que se sabía antes de empezar: ``TimeClass``, ``tiempo_base_seg``
    e ``incremento_seg`` son obligatorios; el rating previo y la forma de cada lado, si se
    conocen (lo que falta queda NaN, como el rival en entrenamiento). Con el Pipeline
    de historial, también acepta ``StartTime`` y ``historial_blancas/negras`` (tuplas de
    observaciones de ``player_history_payloads``); el transformador deriva las columnas
    al consultar ese inicio y excluye cierres simultáneos, solapados o futuros.
    ``modelo`` es el
    artefacto del notebook 04: ``resultado`` (clasificador), ``columnas`` y, si está,
    ``plies_restantes`` (regresor).

    Devuelve una fila por ply en el que la partida sigue en curso: en una partida
    terminada, todos los plies anteriores al final. Con ``en_curso=True`` (una partida
    que se está jugando) también la posición actual, después de la última jugada. El
    modelo se entrenó con cortes hasta el ply 120; más allá, extrapola.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("PGN ilegible")
    plies = sum(1 for _ in game.mainline_moves())
    rows, _ = game_cut_features(
        pgn, range(plies + 1), float(contexto["tiempo_base_seg"]), float(contexto["incremento_seg"]),
        in_progress=en_curso,
    )
    frame = pd.DataFrame(rows)
    for key, value in contexto.items():
        frame[key] = [value] * len(frame) if key.startswith("historial_") else value
    classifier = modelo["resultado"]
    has_history = "historial" in getattr(classifier, "named_steps", {})
    prepare = model_input_frame if has_history else model_frame
    features = prepare(frame, list(modelo["columnas"]))

    proba = classifier.predict_proba(features)
    classes = list(classifier.classes_)
    result = pd.DataFrame({"ply": frame["corte_ply"].to_numpy()})
    for label in RESULT_ORDER:
        # Order by the model's own classes_, never by position.
        result[label] = proba[:, classes.index(label)] if label in classes else 0.0
    if "plies_restantes" in modelo:
        result["plies_restantes"] = modelo["plies_restantes"].predict(features).clip(min=1)
    return result
