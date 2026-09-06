"""Funciones auxiliares compartidas por el pipeline: logging y carga de config."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Crea un logger con timestamp, nombre y nivel formateados.

    Parameters
    ----------
    name : str
        Nombre del logger (típicamente ``__name__`` del módulo que lo pide).
    level : int, optional
        Nivel mínimo de log, por defecto ``logging.INFO``.

    Returns
    -------
    logging.Logger
        Logger configurado con un único handler a stdout.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


def load_config(path: str | Path) -> dict[str, Any]:
    """Carga un archivo de configuración YAML.

    Parameters
    ----------
    path : str or Path
        Ruta al archivo YAML de configuración.

    Returns
    -------
    dict[str, Any]
        Configuración parseada.

    Raises
    ------
    FileNotFoundError
        Si el archivo de configuración no existe.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
