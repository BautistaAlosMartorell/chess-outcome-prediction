"""Selección de jugadores por banda de ELO, congelada después de la primera corrida.

Punto de entrada: ``load_or_create_selection``, usado por la tarea ``listar_jugadores``
del DAG y por el CLI (``python -m src.pipeline``).

- Si ya existe el archivo de selección (``player_selection.selection_path``), se lee y se
  devuelve la misma lista: todas las corridas siguientes descargan los mismos jugadores.
- Si no existe (primera corrida), se arman los pools de candidatos definidos en
  ``player_selection.pools`` con las listas públicas de la PubAPI (titulados y jugadores
  por país), se barajan con una semilla fija, se valida cada candidato y se completan los
  cupos por banda de ELO. El resultado se escribe una sola vez y queda congelado.

Cada pool declara las bandas que alimenta: cuando todas sus bandas están llenas, el pool
se deja de recorrer sin gastar requests. El avance se guarda en un checkpoint para que un
reintento continúe donde quedó en vez de empezar de cero.

No depende de ninguna cuenta inicial ni del parquet de una corrida anterior.
"""

from __future__ import annotations

import copy
import json
import random
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

import requests
import yaml

from src.download_data import DataDownloader
from src.utils import setup_logger

logger = setup_logger(__name__)

PUBAPI_ROOT = "https://api.chess.com/pub"
STATS_TIME_CLASSES = ("chess_bullet", "chess_blitz", "chess_rapid")
# Persist the checkpoint at least every N consumed candidates, even without validations.
CHECKPOINT_EVERY = 100


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
    """Selección completa: política, pools, candidatos evaluados y seleccionados."""

    policy: dict[str, Any]
    pool_sizes: dict[str, int]
    evaluated: list[CandidateValidation]
    selected: dict[str, list[str]]
    skipped: dict[str, int] = field(default_factory=dict)
    consumed: dict[str, int] = field(default_factory=dict)

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
            "pool_sizes": self.pool_sizes,
            "candidates_consumed": self.consumed,
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
    """Arma los pools de candidatos, los baraja con semilla fija y llena cada banda."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        api_get: Callable[[str], dict[str, Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.policy = config["player_selection"]
        self.pools_config: dict[str, dict[str, Any]] = self.policy["pools"]
        self.target_per_band: dict[str, int] = self.policy["target_per_band"]
        self.bands: dict[str, list[int]] = config["elo"]["bandas"]
        self.min_games: int = self.policy["min_eligible_games"]
        self.max_games: int = self.policy["max_games_per_candidate"]
        self.random_state: int = self.policy["random_state"]
        self.request_delay: float = config["download"]["request_delay_seconds"]
        self.selection_path = Path(self.policy["selection_path"])
        self.snapshot_dir = self.selection_path.parent
        self.checkpoint_path = self.selection_path.with_name(
            f"{self.selection_path.stem}.parcial{self.selection_path.suffix}"
        )
        self._check_pools()

        downloader_config = copy.deepcopy(config)
        downloader_config["download"]["until_month"] = self.policy["cutoff"]
        downloader_config["chess_com"]["max_games_per_user"] = self.max_games
        self.downloader = DataDownloader(downloader_config)
        self.base_url = self.downloader.base_url
        self._api_get = api_get or self.downloader._get_json
        self._sleep = sleep

    def _check_pools(self) -> None:
        """Every target band must be fed by some pool, or it could never fill."""
        covered = {band for pool in self.pools_config.values() for band in pool["bands"]}
        missing = set(self.target_per_band) - covered
        if missing:
            raise ValueError(f"Bandas sin ningún pool que las alimente: {sorted(missing)}")
        for name, pool in self.pools_config.items():
            if not pool.get("titles") and not pool.get("countries"):
                raise ValueError(f"El pool {name} no declara 'titles' ni 'countries'")

    def _get_json(self, url: str) -> dict[str, Any]:
        payload = self._api_get(url)
        self._sleep(self.request_delay)
        return payload

    # -- Pools de candidatos --------------------------------------------------

    def _snapshot(self, name: str, url: str) -> list[str]:
        """Return the ``players`` list of ``url``, cached as a raw JSON snapshot.

        The snapshot is written once and reused afterwards, so a retry in the middle
        of a selection works over exactly the same pools.
        """
        path = self.snapshot_dir / f"{name}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = self._get_json(url)
            _atomic_write_text(path, json.dumps(payload, ensure_ascii=False))
        return [str(username) for username in payload.get("players", [])]

    def _pool_lists(self, pool: dict[str, Any]) -> list[tuple[str, str, str]]:
        """(snapshot name, URL, source label) of every public list in a pool."""
        lists = [(f"titled_{title}", f"{PUBAPI_ROOT}/titled/{title}", f"titulo:{title}")
                 for title in pool.get("titles", [])]
        lists += [(f"country_{iso}", f"{PUBAPI_ROOT}/country/{iso}/players", f"pais:{iso}")
                  for iso in pool.get("countries", [])]
        return lists

    def fetch_pools(self) -> dict[str, dict[str, str]]:
        """Build ``{pool: {username: source}}`` from the public lists of each pool.

        A username is kept only in the first pool (config order) that lists it, so it
        is never evaluated twice.
        """
        claimed: set[str] = set()
        pools: dict[str, dict[str, str]] = {}
        for pool_name, pool in self.pools_config.items():
            sources: dict[str, set[str]] = {}
            spellings: dict[str, str] = {}
            for snapshot_name, url, source in self._pool_lists(pool):
                try:
                    players = self._snapshot(snapshot_name, url)
                except (requests.RequestException, ValueError) as exc:
                    logger.warning("No se pudo obtener %s, se sigue sin esa lista: %s", url, exc)
                    continue
                logger.info("Lista %s: %d jugadores", source, len(players))
                for username in players:
                    key = _normalise_username(username)
                    if not key or key in claimed:
                        continue
                    sources.setdefault(key, set()).add(source)
                    spellings.setdefault(key, username)
            claimed.update(sources)
            pools[pool_name] = {spellings[key]: ",".join(sorted(src)) for key, src in sources.items()}
            logger.info("Pool %s: %d candidatos únicos", pool_name, len(pools[pool_name]))
        return pools

    def shuffled_pools(self, pools: dict[str, dict[str, str]]) -> dict[str, list[tuple[str, str]]]:
        """Sort each pool alphabetically and shuffle it with the fixed seed.

        One RNG shuffles the pools in config order, so the order depends only on the
        snapshots and ``random_state``.
        """
        rng = random.Random(self.random_state)
        shuffled: dict[str, list[tuple[str, str]]] = {}
        for pool_name in self.pools_config:
            ordered = sorted(
                pools.get(pool_name, {}).items(),
                key=lambda item: (_normalise_username(item[0]), item[0]),
            )
            rng.shuffle(ordered)
            shuffled[pool_name] = ordered
        return shuffled

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
            if validated_band is None:
                return self._rejected(
                    candidate,
                    "elo_validado_fuera_de_bandas",
                    eligible_games=len(ratings),
                    validated_median_elo=validated_median,
                    archives_checked=checked,
                )

            # The band comes from the validated median, not from the /stats estimate: a
            # candidate whose history lands one band off still counts, as long as that
            # band is open (the caller checks). Validations are the expensive part.
            return CandidateValidation(
                username=candidate.username,
                band=validated_band,
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

    # -- Checkpoint -----------------------------------------------------------

    def policy_snapshot(self) -> dict[str, Any]:
        return {
            "source": self.policy["source"],
            "pools": self.pools_config,
            "cutoff": self.policy["cutoff"],
            "random_state": self.random_state,
            "min_eligible_games": self.min_games,
            "max_games_per_candidate": self.max_games,
            "target_per_band": self.target_per_band,
            "bands": {band: self.bands[band] for band in self.target_per_band},
        }

    def _load_checkpoint(self) -> dict[str, Any] | None:
        """Previous partial progress, only if it was made under the same policy."""
        if not self.checkpoint_path.exists():
            return None
        state = yaml.safe_load(self.checkpoint_path.read_text(encoding="utf-8")) or {}
        if state.get("policy") != self.policy_snapshot():
            logger.warning(
                "Checkpoint %s hecho con otra política: se ignora y se empieza de cero.",
                self.checkpoint_path,
            )
            return None
        logger.info(
            "Retomando la selección desde el checkpoint %s (%s)",
            self.checkpoint_path,
            {band: len(users) for band, users in state["selected"].items()},
        )
        return state

    def _save_checkpoint(self, result: SelectionResult) -> None:
        payload = {
            "policy": result.policy,
            "consumed": result.consumed,
            "selected": result.selected,
            "skipped": dict(result.skipped),
            "evaluated": [asdict(item) for item in result.evaluated],
        }
        _atomic_write_text(
            self.checkpoint_path,
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        )

    # -- Selección ----------------------------------------------------------

    def select(self, pools: dict[str, dict[str, str]]) -> SelectionResult:
        """Recorre los pools barajados en ronda y valida hasta llenar cada banda.

        - Un pool se deja de recorrer cuando todas las bandas que declara están llenas:
          sus candidatos restantes ya no se consultan.
        - Un candidato cuya banda estimada ya está llena se saltea sin validar.
        - La banda final la fija la mediana validada, no la estimación: si cae en otra
          banda que sigue abierta, el candidato entra ahí igual.
        - El avance se guarda en un checkpoint; si la tarea se corta, el reintento sigue
          desde ahí.

        Tolerante: si los pools se agotan con alguna banda incompleta, se loguea un
        warning por banda y se devuelve lo conseguido.
        """
        target_bands = set(self.target_per_band)
        queues = self.shuffled_pools(pools)
        state = self._load_checkpoint() or {}
        result = SelectionResult(
            policy=self.policy_snapshot(),
            pool_sizes={name: len(queue) for name, queue in queues.items()},
            evaluated=[CandidateValidation(**item) for item in state.get("evaluated", [])],
            selected={band: list(state.get("selected", {}).get(band, [])) for band in self.target_per_band},
            skipped=Counter(state.get("skipped", {})),
            consumed={name: int(state.get("consumed", {}).get(name, 0)) for name in queues},
        )
        selected, skipped, consumed = result.selected, result.skipped, result.consumed

        def open_band(band: str) -> bool:
            return band in target_bands and len(selected[band]) < self.target_per_band[band]

        def pool_active(name: str) -> bool:
            return consumed[name] < len(queues[name]) and any(
                open_band(band) for band in self.pools_config[name]["bands"]
            )

        since_checkpoint = 0
        # Round-robin: one candidate per active pool per turn, in config order.
        while any(open_band(band) for band in target_bands):
            active = [name for name in queues if pool_active(name)]
            if not active:
                break
            for pool_name in active:
                if not pool_active(pool_name):
                    continue
                username, source = queues[pool_name][consumed[pool_name]]
                consumed[pool_name] += 1
                since_checkpoint += 1

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
                if not open_band(band):
                    skipped[f"banda_llena:{band}"] += 1
                    if since_checkpoint >= CHECKPOINT_EVERY:
                        self._save_checkpoint(result)
                        since_checkpoint = 0
                    continue

                validation = self.validate_candidate(Candidate(username, band, estimated, source))
                if validation.accepted and not open_band(validation.band):
                    # Validated into a different band that is already full.
                    validation = replace(
                        validation,
                        accepted=False,
                        reason=f"banda_llena_tras_validar:{validation.band}",
                    )
                result.evaluated.append(validation)
                if validation.accepted:
                    band = validation.band
                    selected[band].append(validation.username)
                    logger.info(
                        "%s (%s) aceptado para %s (%d/%d)",
                        username, source, band, len(selected[band]), self.target_per_band[band],
                    )
                else:
                    logger.info("%s rechazado para %s: %s", username, band, validation.reason)
                self._save_checkpoint(result)
                since_checkpoint = 0

        result.skipped = dict(sorted(skipped.items()))
        for band, target in self.target_per_band.items():
            if len(selected[band]) < target:
                logger.warning(
                    "Banda %s: solo %d/%d jugadores seleccionados (pools agotados)",
                    band, len(selected[band]), target,
                )
        return result

    def discard_checkpoint(self) -> None:
        self.checkpoint_path.unlink(missing_ok=True)


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
    result = selector.select(selector.fetch_pools())

    # An outage during selection must not freeze a useless list: below the download
    # minimum nothing is written (the checkpoint stays), so the next run continues.
    min_users = config["download"].get("min_users_ok", 1)
    if len(result.usernames) < min_users:
        raise InsufficientSelectionError(
            f"Solo {len(result.usernames)} jugadores seleccionados (mínimo {min_users}); "
            "no se congela la selección."
        )

    write_selection(result, path)
    selector.discard_checkpoint()
    logger.info(
        "Selección congelada en %s: %d jugadores %s",
        path, len(result.usernames),
        {band: len(users) for band, users in result.selected.items()},
    )
    return result.usernames
