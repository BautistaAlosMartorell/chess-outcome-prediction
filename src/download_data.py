"""Descarga automatizada de partidas desde la PubAPI de Chess.com.

La API es pública y no requiere autenticación. Para cada usuario se consulta la lista
de archivos mensuales y se recorren desde el más reciente hacia atrás hasta reunir el
máximo configurado de partidas rated de ajedrez estándar en bullet, blitz o rapid.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils import setup_logger

logger = setup_logger(__name__)


class DataDownloader:
    """Descarga y consolida archivos mensuales públicos de Chess.com."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        chess_cfg = config["chess_com"]
        self.base_url: str = chess_cfg["base_url"].rstrip("/")
        self.usernames: list[str] = chess_cfg["usernames"]
        self.max_games_per_user: int = chess_cfg["max_games_per_user"]
        self.time_classes: set[str] = set(chess_cfg["time_classes"])
        self.rules: str = chess_cfg["rules"]
        self.rated_only: bool = chess_cfg["rated_only"]
        self.raw_filename_template: str = chess_cfg["raw_filename_template"]
        self.user_agent: str = chess_cfg["user_agent"]
        self.raw_dir = Path(config["paths"]["raw_dir"])
        self.timeout: int = config["download"]["timeout_seconds"]
        self.max_retries: int = config["download"]["max_retries"]
        self.request_delay: float = config["download"]["request_delay_seconds"]
        self.until_month: tuple[int, int] | None = self._parse_until_month(
            config["download"].get("until_month")
        )
        self._session = self._build_session()

    @staticmethod
    def _parse_until_month(value: str | None) -> tuple[int, int] | None:
        """Convierte ``"YYYY-MM"`` en ``(año, mes)``; ``None`` desactiva el tope."""
        if not value:
            return None
        year, month = value.split("-")
        return int(year), int(month)

    @staticmethod
    def _archive_year_month(archive_url: str) -> tuple[int, int]:
        """Extrae ``(año, mes)`` de una URL ``.../games/YYYY/MM``."""
        year, month = archive_url.rstrip("/").rsplit("/", 2)[-2:]
        return int(year), int(month)

    def _archive_in_window(self, archive_url: str) -> bool:
        """Indica si el archivo mensual entra en la ventana temporal configurada."""
        return self.until_month is None or self._archive_year_month(archive_url) <= self.until_month

    def _build_session(self) -> requests.Session:
        """Construye una sesión identificada con reintentos para errores transitorios."""
        session = requests.Session()
        session.headers.update({"User-Agent": self.user_agent, "Accept": "application/json"})
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.config["download"]["backoff_factor"],
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
        return session

    def _get_json(self, url: str) -> dict[str, Any]:
        """Obtiene una respuesta JSON y valida el estado HTTP y el formato."""
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Respuesta inesperada de Chess.com en {url}")
        return payload

    def _is_eligible(self, game: dict[str, Any]) -> bool:
        """Indica si una partida pertenece al universo definido por el proyecto."""
        return (
            game.get("rules") == self.rules
            and game.get("time_class") in self.time_classes
            and (not self.rated_only or game.get("rated") is True)
        )

    def download_user_games(self, username: str, dest_path: str | Path) -> Path:
        """Descarga hasta ``max_games_per_user`` partidas de un usuario (idempotente).

        Recorre los archivos mensuales del más reciente al más antiguo, salteando
        los posteriores a ``download.until_month`` (ventana temporal congelada), y
        se detiene al alcanzar el máximo.
        """
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            logger.info("Ya existe %s — se saltea la descarga de %s.", dest, username)
            return dest

        archives_url = f"{self.base_url}/{username.lower()}/games/archives"
        logger.info("Consultando archivos mensuales de %s", username)
        archives = self._get_json(archives_url).get("archives", [])
        if not archives:
            raise ValueError(f"Chess.com no devolvió archivos de partidas para {username}")

        selected_games: list[dict[str, Any]] = []
        used_archives: list[str] = []
        for archive_url in reversed(archives):
            if not self._archive_in_window(archive_url):
                continue
            monthly_games = self._get_json(archive_url).get("games", [])
            eligible = [game for game in reversed(monthly_games) if self._is_eligible(game)]
            remaining = self.max_games_per_user - len(selected_games)
            selected_games.extend(eligible[:remaining])
            used_archives.append(archive_url)
            logger.info(
                "%s: %d partidas elegibles acumuladas tras %s",
                username,
                len(selected_games),
                "/".join(archive_url.rsplit("/", 2)[-2:]),
            )
            if len(selected_games) >= self.max_games_per_user:
                break
            time.sleep(self.request_delay)

        if not selected_games:
            raise ValueError(f"No se encontraron partidas elegibles para {username}")

        payload = {
            "source_username": username,
            "source_archives": used_archives,
            "games": selected_games,
        }
        tmp_path = dest.with_suffix(dest.suffix + ".part")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)
        tmp_path.replace(dest)
        logger.info("Descarga completa: %s (%d partidas)", dest, len(selected_games))
        return dest

    @staticmethod
    def _count_games(path: Path) -> int:
        """Cuenta las partidas guardadas en un archivo crudo consolidado."""
        with path.open("r", encoding="utf-8") as file:
            return len(json.load(file).get("games", []))

    def download_all(self) -> dict[str, Path]:
        """Descarga las partidas de cada usuario configurado, tolerando fallos aislados.

        Si un usuario falla (cuenta borrada -> 404, sin archivos, sin partidas
        elegibles, error de red), se registra un ``warning`` y se sigue con el
        resto. Al final se exige un mínimo de usuarios y de partidas totales
        (``download.min_users_ok`` / ``download.min_total_games``): por debajo de
        eso el dataset no sirve y se corta con ``RuntimeError``.
        """
        min_users = self.config["download"].get("min_users_ok", 1)
        min_total = self.config["download"].get("min_total_games", 1)

        results: dict[str, Path] = {}
        failed: dict[str, str] = {}
        for username in self.usernames:
            dest = self.raw_dir / self.raw_filename_template.format(username=username)
            try:
                results[username] = self.download_user_games(username, dest)
            except Exception as exc:  # noqa: BLE001 - se degrada por usuario a propósito
                failed[username] = f"{type(exc).__name__}: {exc}"
                logger.warning("Descarga de %s falló, se saltea: %s", username, failed[username])
            time.sleep(self.request_delay)

        total_games = sum(self._count_games(path) for path in results.values())
        logger.info(
            "Descarga terminada: %d/%d usuarios OK, %d partidas crudas. Fallaron: %s",
            len(results),
            len(self.usernames),
            total_games,
            list(failed) or "ninguno",
        )

        if len(results) < min_users:
            raise RuntimeError(
                f"Solo {len(results)} usuarios descargados (mínimo {min_users}). Fallaron: {failed}"
            )
        if total_games < min_total:
            raise RuntimeError(
                f"Solo {total_games} partidas crudas (mínimo {min_total}). Fallaron: {failed}"
            )
        return results


if __name__ == "__main__":
    from src.utils import load_config

    cfg = load_config("config/config.yaml")
    DataDownloader(cfg).download_all()
