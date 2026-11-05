"""Comparación del modelo final entre cortes de la partida (notebook 05).

El notebook 04 decide el modelo; acá sólo se lo mide sobre el test, corte por corte, con
dos métricas a la vez:

- **log-loss**, la métrica declarada: cuánta probabilidad le dio el modelo a lo que pasó;
- **accuracy**, la decisión fija: la clase de mayor probabilidad, ¿acertó?

Y con dos controles para que la comparación entre cortes sea justa:

- **población común**: las mismas partidas en todos los cortes, para que un corte tardío no
  mejore sólo porque quedan partidas distintas (las largas);
- **intervalos por bootstrap por partida**: se re-sortean partidas, no filas, porque los
  cortes de una misma partida no son independientes. Se usa el mismo sorteo en todos los
  cortes, así la diferencia entre dos cortes también tiene su intervalo (es pareada).

Las predicciones llegan en el formato de ``src.build_app.predecir_test``: una fila por
(partida, corte) con ``resultado``, ``p_*`` del modelo y ``piso_p_*`` del piso.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, recall_score

from src.predict import RESULT_ORDER

# Sorted label order, as sklearn's classes_ (and src.build_app): Empate, Gana Blancas, Gana Negras.
CLASES = sorted(RESULT_ORDER)
COLUMNA_PROBA = {"Empate": "p_empate", "Gana Blancas": "p_blancas", "Gana Negras": "p_negras"}
METRICAS_BOOTSTRAP = ["log_loss", "log_loss piso", "mejora log_loss", "accuracy", "accuracy piso", "puntos sobre piso"]


def _probas(pred: pd.DataFrame, prefijo: str = "") -> np.ndarray:
    return pred[[f"{prefijo}{COLUMNA_PROBA[c]}" for c in CLASES]].to_numpy(dtype=float)


def perdida_por_fila(pred: pd.DataFrame, prefijo: str = "") -> np.ndarray:
    """Log-loss de cada fila: −log de la probabilidad que recibió el resultado real.

    Recorta como ``sklearn.metrics.log_loss``, así el promedio da lo mismo que esa función.
    """
    proba = _probas(pred, prefijo)
    eps = np.finfo(proba.dtype).eps
    real = pd.Categorical(pred["resultado"].astype(str), categories=CLASES).codes
    assert (real >= 0).all(), "Un resultado fuera de las tres clases"
    return -np.log(np.clip(proba[np.arange(len(pred)), real], eps, 1 - eps))


def decision(pred: pd.DataFrame) -> np.ndarray:
    """Decisión fija del modelo: la clase de mayor probabilidad (empates, la primera en orden)."""
    return np.asarray(CLASES)[_probas(pred).argmax(axis=1)]


def metricas_por_corte(pred: pd.DataFrame, clase_piso: str) -> pd.DataFrame:
    """Una fila por corte: log-loss y accuracy del modelo y del piso, lado a lado."""
    pred = pred.assign(
        _perdida=perdida_por_fila(pred), _perdida_piso=perdida_por_fila(pred, "piso_"),
        _decision=decision(pred), _real=pred["resultado"].astype(str),
    )
    rows = []
    for corte, g in pred.groupby("corte_ply", sort=True):
        log_loss, log_loss_piso = g["_perdida"].mean(), g["_perdida_piso"].mean()
        accuracy = float((g["_decision"] == g["_real"]).mean())
        accuracy_piso = float((g["_real"] == clase_piso).mean())
        rows.append({
            "corte_ply": int(corte), "filas": len(g), "partidas": g["GameUrl"].nunique(),
            "log_loss": log_loss, "log_loss piso": log_loss_piso, "mejora log_loss": 1 - log_loss / log_loss_piso,
            "accuracy": accuracy, "accuracy piso": accuracy_piso, "puntos sobre piso": 100 * (accuracy - accuracy_piso),
            "f1_macro": f1_score(g["_real"], g["_decision"], labels=RESULT_ORDER, average="macro", zero_division=0),
            "recall_empate": recall_score(g["_real"], g["_decision"], labels=["Empate"], average="macro", zero_division=0),
        })
    return pd.DataFrame(rows)


def poblacion_comun(pred: pd.DataFrame, hasta_ply: int) -> pd.DataFrame:
    """Las partidas que siguen en juego en ``hasta_ply``, en todos sus cortes hasta ese ply.

    Una partida que tiene fila en el corte k la tiene en todos los anteriores, así que cada
    corte de la población común mide exactamente las mismas partidas.
    """
    llegan = set(pred.loc[pred["corte_ply"] == hasta_ply, "GameUrl"])
    if not llegan:
        raise ValueError(f"Ninguna partida llega al ply {hasta_ply}")
    comun = pred[pred["GameUrl"].isin(llegan) & (pred["corte_ply"] <= hasta_ply)].reset_index(drop=True)
    por_corte = comun.groupby("corte_ply")["GameUrl"].nunique()
    assert (por_corte == len(llegan)).all(), "Una partida de la población común no tiene todos sus cortes"
    return comun


def replicas_bootstrap(
    pred: pd.DataFrame, clase_piso: str, n_replicas: int = 1000, random_state: int = 42,
) -> dict[str, pd.DataFrame]:
    """Bootstrap por partida: cada métrica, una tabla (réplica × corte).

    En cada réplica se sortean partidas con reposición y cada partida pesa en todos sus
    cortes la cantidad de veces que salió. El sorteo es el mismo para todos los cortes.
    """
    codigos, partidas = pd.factorize(pred["GameUrl"])
    rng = np.random.default_rng(random_state)
    # weights[r, g]: how many times game g was drawn in replicate r.
    pesos = np.stack([np.bincount(rng.integers(0, len(partidas), len(partidas)), minlength=len(partidas))
                      for _ in range(n_replicas)]).astype(np.float32)
    perdida, perdida_piso = perdida_por_fila(pred), perdida_por_fila(pred, "piso_")
    real = pred["resultado"].astype(str).to_numpy()
    acierto, acierto_piso = (decision(pred) == real).astype(float), (real == clase_piso).astype(float)
    cortes = np.sort(pred["corte_ply"].unique())
    tablas = {m: np.empty((n_replicas, len(cortes))) for m in METRICAS_BOOTSTRAP}
    corte_de_fila = pred["corte_ply"].to_numpy()
    for j, corte in enumerate(cortes):
        filas = corte_de_fila == corte
        w = pesos[:, codigos[filas]].astype(float)  # one row per game in a cut: (replicates × games of the cut)
        total = w.sum(axis=1)
        tablas["log_loss"][:, j] = w @ perdida[filas] / total
        tablas["log_loss piso"][:, j] = w @ perdida_piso[filas] / total
        tablas["accuracy"][:, j] = w @ acierto[filas] / total
        tablas["accuracy piso"][:, j] = w @ acierto_piso[filas] / total
    tablas["mejora log_loss"] = 1 - tablas["log_loss"] / tablas["log_loss piso"]
    tablas["puntos sobre piso"] = 100 * (tablas["accuracy"] - tablas["accuracy piso"])
    return {m: pd.DataFrame(v, columns=pd.Index(cortes, name="corte_ply")) for m, v in tablas.items()}


def intervalos(replicas: dict[str, pd.DataFrame], puntual: pd.DataFrame, nivel: float = 0.95) -> pd.DataFrame:
    """Valor de la muestra y percentiles del bootstrap, en formato largo (corte, métrica)."""
    a = (1 - nivel) / 2
    puntual = puntual.set_index("corte_ply")
    rows = []
    for metrica, tabla in replicas.items():
        for corte in tabla.columns:
            rows.append({"corte_ply": int(corte), "metrica": metrica, "valor": float(puntual.loc[corte, metrica]),
                         "bajo": float(tabla[corte].quantile(a)), "alto": float(tabla[corte].quantile(1 - a))})
    return pd.DataFrame(rows)


def diferencias_entre_cortes(
    replicas: dict[str, pd.DataFrame], puntual: pd.DataFrame, pares: Sequence[tuple[int, int]],
    metricas: Sequence[str] = ("accuracy", "log_loss"), nivel: float = 0.95,
) -> pd.DataFrame:
    """Cambio de cada métrica entre dos cortes (después − antes), con su intervalo pareado.

    Tiene sentido sobre la población común: así los dos cortes miden las mismas partidas.
    """
    a = (1 - nivel) / 2
    puntual = puntual.set_index("corte_ply")
    rows = []
    for metrica in metricas:
        for antes, despues in pares:
            delta = replicas[metrica][despues] - replicas[metrica][antes]
            bajo, alto = float(delta.quantile(a)), float(delta.quantile(1 - a))
            rows.append({"metrica": metrica, "desde": antes, "hasta": despues,
                         "cambio": float(puntual.loc[despues, metrica] - puntual.loc[antes, metrica]),
                         "bajo": bajo, "alto": alto, "distinto de cero": bajo > 0 or alto < 0})
    return pd.DataFrame(rows)
