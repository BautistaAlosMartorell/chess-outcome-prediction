"""Selección de jugadores por banda de ELO, congelada después de la primera corrida.

Punto de entrada: ``load_or_create_selection``, usado por la tarea ``listar_jugadores``
del DAG y por el CLI (``python -m src.pipeline``).

- Si ya existe el archivo de selección (``player_selection.selection_path``), se lee y se
  devuelve la misma lista: todas las corridas siguientes descargan los mismos jugadores.
- Si no existe (primera corrida), se arma el universo de candidatos con las listas
  públicas de jugadores por país y de titulados de la PubAPI, se baraja con una semilla
  fija, se valida cada candidato y se completan los cupos por banda de ELO. El resultado
  se escribe una sola vez y queda congelado.

No depende de ninguna cuenta inicial ni del parquet de una corrida anterior.
"""

from __future__ import annotations

import copy
import json
import random
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests
import yaml

from src.download_data import DataDownloader
from src.utils import setup_logger

logger = setup_logger(__name__)

PUBAPI_ROOT = "https://api.chess.com/pub"
STATS_TIME_CLASSES = ("chess_bullet", "chess_blitz", "chess_rapid")


@dataclass(frozen=True)
class Candidate:
    """Jugador candidato con la banda estimada por sus estadísticas actuales."""

    username: str
    band: str
    estimated_elo: float
    source: str


@dataclass(frozen=True)
class CandidateValidation:
    """Resultado auditable de validar un candidato contra la PubAPI."""

    username: str
    band: str
    accepted: bool
    reason: str
    estimated_elo: float
    source: str = ""
    eligible_games: int = 0
    validated_median_elo: float | None = None
    archives_checked: int = 0


@dataclass
class SelectionResult:
    """Selección completa: política, pool, candidatos evaluados y seleccionados."""

    policy: dict[str, Any]
    pool_size: int
    evaluated: list[CandidateValidation]
    selected: dict[str, list[str]]
    skipped: dict[str, int] = field(default_factory=dict)

    @property
    def usernames(self) -> list[str]:
        """Lista plana en el orden de las bandas, sin duplicados."""
        seen: set[str] = set()
        combined: list[str] = []
        for usernames in self.selected.values():
            for username in usernames:
                key = _normalise_username(username)
                if key not in seen:
                    combined.append(username)
                    seen.add(key)
        return combined

    @property
    def is_complete(self) -> bool:
        targets = self.policy["target_per_band"]
        return all(len(self.selected.get(band, [])) == target for band, target in targets.items())

    def to_manifest(self) -> dict[str, Any]:
        """Convierte el resultado a tipos serializables por YAML."""
        return {
            "status": "complete" if self.is_complete else "incomplete",
            "policy": self.policy,
            "pool_size": self.pool_size,
            "selected": self.selected,
            "usernames": self.usernames,
            "skipped_before_validation": self.skipped,
            "evaluated": [asdict(item) for item in self.evaluated],
        }


class InsufficientSelectionError(RuntimeError):
    """La selección quedó por debajo del mínimo de cuentas de la descarga."""


def _normalise_username(value: Any) -> str:
    return str(value).strip().casefold()


def _band_for_elo(elo: float, bands: dict[str, list[int]], target_bands: set[str]) -> str | None:
    """Clasifica con intervalos [inferior, superior), sin solapamientos."""
    for name, limits in bands.items():
        if name not in target_bands:
            continue
        lower, upper = limits
        if lower <= elo < upper:
            return name
    return None


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


class PlayerSelector:
    """Arma el pool de candidatos, lo baraja con semilla fija y llena cada banda."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        api_get: Callable[[str], dict[str, Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.policy = config["player_selection"]
        self.countries: list[str] = self.policy["countries"]
        self.titles: list[str] = self.policy["titles"]
        self.target_per_band: dict[str, int] = self.policy["target_per_band"]
        self.bands: dict[str, list[int]] = config["elo"]["bandas"]
        self.min_games: int = self.policy["min_eligible_games"]
        self.max_games: int = self.policy["max_games_per_candidate"]
        self.random_state: int = self.policy["random_state"]
        self.request_delay: float = config["download"]["request_delay_seconds"]
        self.selection_path = Path(self.policy["selection_path"])
        self.snapshot_dir = self.selection_path.parent

        downloader_config = copy.deepcopy(config)
        downloader_config["download"]["until_month"] = self.policy["cutoff"]
        downloader_config["chess_com"]["max_games_per_user"] = self.max_games
        self.downloader = DataDownloader(downloader_config)
        self.base_url = self.downloader.base_url
        self._api_get = api_get or self.downloader._get_json
        self._sleep = sleep

    def _get_json(self, url: str) -> dict[str, Any]:
        payload = self._api_get(url)
        self._sleep(self.request_delay)
        return payload

    # -- Pool de candidatos -------------------------------------------------

    def _snapshot(self, name: str, url: str) -> list[str]:
        """Return the ``players`` list of ``url``, cached as a raw JSON snapshot.

        The snapshot is written once and reused afterwards, so a retry in the middle
        of a selection works over exactly the same pool.
        """
        path = self.snapshot_dir / f"{name}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = self._get_json(url)
            _atomic_write_text(path, json.dumps(payload, ensure_ascii=False))
        return [str(username) for username in payload.get("players", [])]

    def fetch_candidate_pool(self) -> dict[str, str]:
        """Build ``{normalised_username: source}`` from country and titled lists."""
        sources: dict[str, set[str]] = {}
        spellings: dict[str, str] = {}
        lists = [(f"country_{iso}", f"{PUBAPI_ROOT}/country/{iso}/players", f"pais:{iso}")
                 for iso in self.countries]
        lists += [(f"titled_{title}", f"{PUBAPI_ROOT}/titled/{title}", f"titulo:{title}")
                  for title in self.titles]
        for name, url, source in lists:
            try:
                players = self._snapshot(name, url)
            except (requests.RequestException, ValueError) as exc:
                logger.warning("No se pudo obtener %s, se sigue sin esa lista: %s", url, exc)
                continue
            logger.info("Lista %s: %d jugadores", source, len(players))
            for username in players:
                key = _normalise_username(username)
                if not key:
                    continue
                sources.setdefault(key, set()).add(source)
                spellings.setdefault(key, username)
        return {spellings[key]: ",".join(sorted(src)) for key, src in sources.items()}

    def shuffled_pool(self, pool: dict[str, str]) -> list[tuple[str, str]]:
        """Sort alphabetically and shuffle with the fixed seed (reproducible order)."""
        ordered = sorted(pool.items(), key=lambda item: (_normalise_username(item[0]), item[0]))
        random.Random(self.random_state).shuffle(ordered)
        return ordered

    # -- Pre-filtro y validación --------------------------------------------

    def estimate_elo(self, username: str) -> float | None:
        """Rating of the bullet/blitz/rapid class with the most games, from ``/stats``."""
        stats = self._get_json(f"{self.base_url}/{username.lower()}/stats")
        best: tuple[int, float] | None = None
        for time_class in STATS_TIME_CLASSES:
            entry = stats.get(time_class) or {}
            record = entry.get("record") or {}
            games = sum(int(record.get(key, 0)) for key in ("win", "loss", "draw"))
            rating = (entry.get("last") or {}).get("rating")
            if games == 0 or not isinstance(rating, (int, float)) or isinstance(rating, bool):
                continue
            if best is None or games > best[0]:
                best = (games, float(rating))
        return None if best is None else best[1]

    @staticmethod
    def _rating_for(game: dict[str, Any], username: str) -> int | None:
        expected = _normalise_username(username)
        for color in ("white", "black"):
            player = game.get(color) or {}
            if _normalise_username(player.get("username", "")) != expected:
                continue
            rating = player.get("rating")
            if isinstance(rating, (int, float)) and not isinstance(rating, bool):
                return int(rating)
        return None

    def validate_candidate(self, candidate: Candidate) -> CandidateValidation:
        """Valida perfil, actividad, volumen y mediana de un candidato."""
        try:
            username_path = candidate.username.lower()
            profile = self._get_json(f"{self.base_url}/{username_path}")
            status = str(profile.get("status", "")).casefold()
            if not status:
                return self._rejected(candidate, "perfil_sin_estado")
            if status.startswith("closed") or "fair_play" in status:
                return self._rejected(candidate, f"cuenta_no_activa:{status}")

            archives_payload = self._get_json(f"{self.base_url}/{username_path}/games/archives")
            archives = [
                url
                for url in archives_payload.get("archives", [])
                if self.downloader._archive_in_window(url)
            ]
            if not archives:
                return self._rejected(candidate, "sin_archivos_antes_del_corte")

            ratings: list[int] = []
            checked = 0
            for archive_url in reversed(archives):
                games = self._get_json(archive_url).get("games", [])
                checked += 1
                for game in reversed(games):
                    if not self.downloader._is_eligible(game):
                        continue
                    rating = self._rating_for(game, candidate.username)
                    if rating is not None:
                        ratings.append(rating)
                    if len(ratings) >= self.max_games:
                        break
                if len(ratings) >= self.max_games:
                    break

            if len(ratings) < self.min_games:
                return self._rejected(
                    candidate,
                    "partidas_elegibles_insuficientes",
                    eligible_games=len(ratings),
                    archives_checked=checked,
                )

            validated_median = float(statistics.median(ratings))
            validated_band = _band_for_elo(
                validated_median,
                self.bands,
                set(self.target_per_band),
            )
            if validated_band != candidate.band:
                return self._rejected(
                    candidate,
                    f"elo_validado_fuera_de_banda:{validated_band or 'ninguna'}",
                    eligible_games=len(ratings),
                    validated_median_elo=validated_median,
                    archives_checked=checked,
                )

            return CandidateValidation(
                username=candidate.username,
                band=candidate.band,
                accepted=True,
                reason="aceptado",
                estimated_elo=candidate.estimated_elo,
                source=candidate.source,
                eligible_games=len(ratings),
                validated_median_elo=validated_median,
                archives_checked=checked,
            )
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            return self._rejected(candidate, f"error_api:{type(exc).__name__}:{exc}")

    @staticmethod
    def _rejected(
        candidate: Candidate,
        reason: str,
        *,
        eligible_games: int = 0,
        validated_median_elo: float | None = None,
        archives_checked: int = 0,
    ) -> CandidateValidation:
        return CandidateValidation(
            username=candidate.username,
            band=candidate.band,
            accepted=False,
            reason=reason,
            estimated_elo=candidate.estimated_elo,
            source=candidate.source,
            eligible_games=eligible_games,
            validated_median_elo=validated_median_elo,
            archives_checked=archives_checked,
        )

    # -- Selección ----------------------------------------------------------

    def _policy_snapshot(self) -> dict[str, Any]:
        return {
            "source": self.policy["source"],
            "countries": self.countries,
            "titles": self.titles,
            "cutoff": self.policy["cutoff"],
            "random_state": self.random_state,
            "min_eligible_games": self.min_games,
            "max_games_per_candidate": self.max_games,
            "target_per_band": self.target_per_band,
            "bands": {band: self.bands[band] for band in self.target_per_band},
        }

    def select(self, pool: dict[str, str]) -> SelectionResult:
        """Recorre el pool barajado y valida candidatos hasta llenar cada banda.

        Tolerante: si el pool se agota con alguna banda incompleta, se loguea un
        warning por banda y se devuelve lo conseguido.
        """
        target_bands = set(self.target_per_band)
        selected: dict[str, list[str]] = {band: [] for band in self.target_per_band}
        evaluated: list[CandidateValidation] = []
        skipped: Counter[str] = Counter()

        def full() -> bool:
            return all(len(selected[b]) >= t for b, t in self.target_per_band.items())

        for username, source in self.shuffled_pool(pool):
            if full():
                break
            try:
                estimated = self.estimate_elo(username)
            except (requests.RequestException, ValueError, KeyError, TypeError):
                skipped["stats_no_disponibles"] += 1
                continue
            if estimated is None:
                skipped["sin_partidas_bullet_blitz_rapid"] += 1
                continue
            band = _band_for_elo(estimated, self.bands, target_bands)
            if band is None:
                skipped["fuera_de_bandas"] += 1
                continue
            if len(selected[band]) >= self.target_per_band[band]:
                skipped[f"banda_llena:{band}"] += 1
                continue

            validation = self.validate_candidate(Candidate(username, band, estimated, source))
            evaluated.append(validation)
            if validation.accepted:
                selected[band].append(validation.username)
                logger.info(
                    "%s aceptado para %s (%d/%d)",
                    username, band, len(selected[band]), self.target_per_band[band],
                )
            else:
                logger.info("%s rechazado para %s: %s", username, band, validation.reason)

        result = SelectionResult(
            policy=self._policy_snapshot(),
            pool_size=len(pool),
            evaluated=evaluated,
            selected=selected,
            skipped=dict(sorted(skipped.items())),
        )
        for band, target in self.target_per_band.items():
            if len(selected[band]) < target:
                logger.warning(
                    "Banda %s: solo %d/%d jugadores seleccionados (pool agotado)",
                    band, len(selected[band]), target,
                )
        return result


def write_selection(result: SelectionResult, path: str | Path) -> Path:
    """Guarda la selección (lista congelada + manifiesto) de forma atómica."""
    destination = Path(path)
    payload = yaml.safe_dump(result.to_manifest(), allow_unicode=True, sort_keys=False)
    _atomic_write_text(destination, payload)
    return destination


def load_selection(path: str | Path) -> list[str]:
    """Lee la lista congelada de un archivo de selección existente."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    usernames = payload.get("usernames") or []
    if not usernames:
        raise ValueError(f"El archivo de selección {path} no tiene usernames")
    return [str(username) for username in usernames]


def load_or_create_selection(
    config: dict[str, Any],
    *,
    selector: PlayerSelector | None = None,
) -> list[str]:
    """Devuelve la lista de jugadores a descargar, creándola sólo si no existe.

    La primera corrida selecciona y escribe ``player_selection.selection_path``; las
    siguientes leen ese archivo, así que descargan exactamente los mismos jugadores.
    Para volver a seleccionar hay que borrar el archivo a mano.
    """
    path = Path(config["player_selection"]["selection_path"])
    if path.exists():
        usernames = load_selection(path)
        logger.info("Selección congelada reutilizada (%s): %d jugadores", path, len(usernames))
        return usernames

    logger.info("No existe %s: primera corrida, se seleccionan jugadores por banda.", path)
    selector = selector or PlayerSelector(config)
    result = selector.select(selector.fetch_candidate_pool())

    # An outage during selection must not freeze a useless list: below the download
    # minimum nothing is written, so the next run selects again.
    min_users = config["download"].get("min_users_ok", 1)
    if len(result.usernames) < min_users:
        raise InsufficientSelectionError(
            f"Solo {len(result.usernames)} jugadores seleccionados (mínimo {min_users}); "
            "no se congela la selección."
        )

    write_selection(result, path)
    logger.info(
        "Selección congelada en %s: %d jugadores %s",
        path, len(result.usernames),
        {band: len(users) for band, users in result.selected.items()},
    )
    return result.usernames
