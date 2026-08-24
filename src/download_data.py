"""Descarga automatizada de partidas de ajedrez desde la API de Lichess.

Endpoint real: ``GET /api/games/user/{username}``, documentado en
https://github.com/lichess-org/api (``doc/specs/tags/games/api-games-user-username.yaml``).
No requiere autenticación para uso anónimo (throttle de 20 partidas/segundo).
Devuelve un stream de partidas en PGN de texto plano.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils import setup_logger

logger = setup_logger(__name__)


class DataDownloader:
    """Descarga partidas de ajedrez de una lista de usuarios de Lichess.

    Parameters
    ----------
    config : dict[str, Any]
        Configuración cargada desde ``config/config.yaml``. Se usan las
        claves ``lichess`` (usuarios, filtros) y ``download`` (timeout,
        reintentos).
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        lichess_cfg = config["lichess"]
        self.base_url: str = lichess_cfg["base_url"]
        self.usernames: list[str] = lichess_cfg["usernames"]
        self.max_games_per_user: int = lichess_cfg["max_games_per_user"]
        self.perf_types: str = lichess_cfg["perf_types"]
        self.rated_only: bool = lichess_cfg["rated_only"]
        self.raw_filename_template: str = lichess_cfg["raw_filename_template"]
        self.raw_dir = Path(config["paths"]["raw_dir"])
        self.timeout: int = config["download"]["timeout_seconds"]
        self.max_retries: int = config["download"]["max_retries"]
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Construye una sesión de requests con reintentos y backoff exponencial."""
        session = requests.Session()
        # Lichess rejects the generic ``python-requests`` user agent in some
        # environments. Identify this client explicitly, as expected for API
        # consumers, so valid anonymous exports are not mistaken for bot traffic.
        session.headers.update(
            {
                "User-Agent": (
                    "epl-injury-type-prediction/1.0 "
                    "(+https://github.com/BautistaAlosMartorell/"
                    "epl-injury-type-prediction)"
                )
            }
        )
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.config["download"]["backoff_factor"],
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        return session

    def download_user_games(self, username: str, dest_path: str | Path) -> Path:
        """Descarga las partidas de un usuario y las guarda como PGN (idempotente).

        Si el archivo de destino ya existe, se saltea la descarga.

        Parameters
        ----------
        username : str
            Nombre de usuario de Lichess.
        dest_path : str or Path
            Ruta local de destino del archivo PGN.

        Returns
        -------
        Path
            Ruta al archivo guardado (o ya existente).

        Raises
        ------
        requests.exceptions.RequestException
            Si la descarga falla tras agotar los reintentos configurados.
        """
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            logger.info("Ya existe %s — se saltea la descarga de %s.", dest, username)
            return dest

        params = {
            "max": self.max_games_per_user,
            "opening": "true",
            "rated": "true" if self.rated_only else "false",
            "perfType": self.perf_types,
            "moves": "true",
            "clocks": "false",
            "evals": "false",
        }
        headers = {"Accept": "application/x-chess-pgn"}
        url = f"{self.base_url}/{username}"

        logger.info("Descargando partidas de %s -> %s", username, dest)
        try:
            for attempt in range(self.max_retries + 1):
                response = self._session.get(
                    url, params=params, headers=headers, timeout=self.timeout, stream=True
                )
                if response.status_code != 429 or attempt == self.max_retries:
                    break

                retry_after = response.headers.get("Retry-After", "60")
                wait_seconds = max(60, int(retry_after)) if retry_after.isdigit() else 60
                response.close()
                logger.warning(
                    "Lichess limitó la descarga de %s (429). Reintentando en %d segundos.",
                    username,
                    wait_seconds,
                )
                time.sleep(wait_seconds)

            response.raise_for_status()
            tmp_path = dest.with_suffix(dest.suffix + ".part")
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            tmp_path.rename(dest)
        except requests.exceptions.RequestException:
            logger.error("Falló la descarga de partidas de %s.", username)
            raise

        logger.info("Descarga completa: %s", dest)
        return dest

    def download_all(self) -> dict[str, Path]:
        """Descarga las partidas de todos los usuarios configurados.

        Returns
        -------
        dict[str, Path]
            Mapeo nombre de usuario -> ruta local del PGN descargado.
        """
        results: dict[str, Path] = {}
        for username in self.usernames:
            dest = self.raw_dir / self.raw_filename_template.format(username=username)
            results[username] = self.download_user_games(username, dest)
        return results


if __name__ == "__main__":
    from src.utils import load_config

    cfg = load_config("config/config.yaml")
    downloader = DataDownloader(cfg)
    downloader.download_all()
