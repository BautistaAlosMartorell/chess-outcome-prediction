"""Selección reproducible de jugadores para ampliar la muestra del proyecto.

Ejecutable desde la tarea ``listar_jugadores`` del DAG o desde la línea de comandos.
Parte de los oponentes ya observados en el parquet procesado, valida su actividad en
la PubAPI y produce una selección reproducible por banda de ELO.

Si no existe un parquet procesado de una corrida anterior (primera corrida bootstrap),
la función ``bootstrap_username_list`` devuelve solo los seed_usernames del config.
"""

from __future__ import annotations

import copy
import random
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests
import yaml

from src.download_data import DataDownloader
from src.utils import setup_logger

logger = setup_logger(__name__)


@dataclass(frozen=True)
class Candidate:
    """Jugador candidato derivado del dataset procesado."""

    username: str
    band: str
    historical_median_elo: float
    observed_games: int


@dataclass(frozen=True)
class CandidateValidation:
    """Resultado auditable de validar un candidato contra la PubAPI."""

    username: str
    band: str
    accepted: bool
    reason: str
    historical_median_elo: float
    eligible_games: int = 0
    validated_median_elo: float | None = None
    archives_checked: int = 0


@dataclass
class SelectionResult:
    """Propuesta completa, incluidos candidatos rechazados y seleccionados."""

    policy: dict[str, Any]
    candidate_counts: dict[str, int]
    evaluated: list[CandidateValidation]
    selected: dict[str, list[str]]

    def to_manifest(self) -> dict[str, Any]:
        """Convierte el resultado a tipos serializables por YAML."""
        return {
            "status": "complete" if self.is_complete else "incomplete",
            "policy": self.policy,
            "candidate_counts": self.candidate_counts,
            "selected": self.selected,
            "evaluated": [asdict(item) for item in self.evaluated],
        }

    @property
    def is_complete(self) -> bool:
        targets = self.policy["target_per_band"]
        return all(len(self.selected.get(band, [])) == target for band, target in targets.items())


class InsufficientCandidatesError(RuntimeError):
    """Indica que al menos una banda no reunió la cantidad requerida."""

    def __init__(self, result: SelectionResult) -> None:
        self.result = result
        missing = {
            band: target - len(result.selected.get(band, []))
            for band, target in result.policy["target_per_band"].items()
            if len(result.selected.get(band, [])) < target
        }
        super().__init__(f"No alcanzan los candidatos válidos por banda. Faltantes: {missing}")


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


def extract_candidate_pools(
    df: pd.DataFrame,
    seed_usernames: list[str],
    bands: dict[str, list[int]],
    target_per_band: dict[str, int],
) -> dict[str, list[Candidate]]:
    """Extrae oponentes y calcula su ELO mediano observado en ambos colores."""
    required = {"White", "Black", "WhiteElo", "BlackElo"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"El parquet no contiene las columnas requeridas: {sorted(missing)}")

    white = df[["White", "WhiteElo"]].rename(columns={"White": "username", "WhiteElo": "elo"})
    black = df[["Black", "BlackElo"]].rename(columns={"Black": "username", "BlackElo": "elo"})
    observations = pd.concat([white, black], ignore_index=True)
    observations["username"] = observations["username"].astype("string").str.strip()
    observations["normalised_username"] = observations["username"].map(_normalise_username)
    observations["elo"] = pd.to_numeric(observations["elo"], errors="coerce")

    seeds = {_normalise_username(username) for username in seed_usernames}
    observations = observations.loc[
        observations["username"].notna()
        & observations["elo"].notna()
        & observations["normalised_username"].ne("")
        & ~observations["normalised_username"].isin(seeds)
    ]

    pools = {band: [] for band in target_per_band}
    for _, group in observations.groupby("normalised_username", sort=True):
        median_elo = float(group["elo"].median())
        band = _band_for_elo(median_elo, bands, set(target_per_band))
        if band is None:
            continue
        spellings = sorted(group["username"].dropna().astype(str).unique(), key=lambda x: (x.casefold(), x))
        pools[band].append(
            Candidate(
                username=spellings[0],
                band=band,
                historical_median_elo=median_elo,
                observed_games=int(len(group)),
            )
        )

    for candidates in pools.values():
        candidates.sort(key=lambda candidate: (candidate.username.casefold(), candidate.username))
    return pools


class PlayerSelector:
    """Valida y selecciona candidatos con un orden aleatorio reproducible."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        api_get: Callable[[str], dict[str, Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.policy = config["player_selection"]
        self.seed_usernames: list[str] = self.policy["seed_usernames"]
        self.target_per_band: dict[str, int] = self.policy["target_per_band"]
        self.bands: dict[str, list[int]] = config["elo"]["bandas"]
        self.min_games: int = self.policy["min_eligible_games"]
        self.max_games: int = self.policy["max_games_per_candidate"]
        self.random_state: int = self.policy["random_state"]
        self.request_delay: float = config["download"]["request_delay_seconds"]

        downloader_config = copy.deepcopy(config)
        downloader_config["download"]["until_month"] = self.policy["cutoff"]
        downloader_config["chess_com"]["max_games_per_user"] = self.max_games
        self.downloader = DataDownloader(downloader_config)
        self.base_url = self.downloader.base_url
        self._api_get = api_get or self.downloader._get_json
        self._sleep = sleep

    def discover_opponents_from_api(self) -> pd.DataFrame:
        """Fetch recent games of seed users from the PubAPI to discover opponents.

        Used on the first run when no processed parquet exists yet. For each seed,
        fetches the most recent monthly archives (within the cutoff window) and
        collects opponent usernames and ratings from eligible games.

        Returns a DataFrame with ``White``, ``Black``, ``WhiteElo``, ``BlackElo``
        columns — the same schema that ``extract_candidate_pools`` expects.
        """
        rows: list[dict[str, Any]] = []
        # Limit how many games we sample per seed to keep discovery fast.
        # 300 recent games per seed × 8 seeds = up to 2400 observations, which
        # is plenty to build diverse candidate pools across ELO bands.
        discovery_limit = 300

        for seed in self.seed_usernames:
            try:
                username_path = seed.lower()
                logger.info("Descubriendo oponentes del seed %s...", seed)
                archives_payload = self._get_json(
                    f"{self.base_url}/{username_path}/games/archives"
                )
                archives = [
                    url
                    for url in archives_payload.get("archives", [])
                    if self.downloader._archive_in_window(url)
                ]
                if not archives:
                    logger.warning("Seed %s: sin archivos en la ventana temporal", seed)
                    continue

                games_seen = 0
                for archive_url in reversed(archives):
                    monthly = self._get_json(archive_url).get("games", [])
                    for game in reversed(monthly):
                        if not self.downloader._is_eligible(game):
                            continue
                        white = game.get("white") or {}
                        black = game.get("black") or {}
                        rows.append(
                            {
                                "White": white.get("username", ""),
                                "Black": black.get("username", ""),
                                "WhiteElo": white.get("rating", 0),
                                "BlackElo": black.get("rating", 0),
                            }
                        )
                        games_seen += 1
                        if games_seen >= discovery_limit:
                            break
                    if games_seen >= discovery_limit:
                        break

                logger.info(
                    "Seed %s: %d partidas elegibles recolectadas para descubrimiento",
                    seed, games_seen,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Error descubriendo oponentes del seed %s, se sigue: %s: %s",
                    seed, type(exc).__name__, exc,
                )

        if not rows:
            logger.warning("No se encontraron partidas de ningún seed para descubrimiento")
            return pd.DataFrame(columns=["White", "Black", "WhiteElo", "BlackElo"])

        df = pd.DataFrame(rows)
        logger.info(
            "Descubrimiento completo: %d observaciones de %d seeds",
            len(df), len(self.seed_usernames),
        )
        return df

    def _get_json(self, url: str) -> dict[str, Any]:
        payload = self._api_get(url)
        self._sleep(self.request_delay)
        return payload

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
                historical_median_elo=candidate.historical_median_elo,
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
            historical_median_elo=candidate.historical_median_elo,
            eligible_games=eligible_games,
            validated_median_elo=validated_median_elo,
            archives_checked=archives_checked,
        )

    def _run_selection(self, df: pd.DataFrame) -> tuple[
        dict[str, list[str]], list[CandidateValidation], dict[str, int],
    ]:
        """Core loop: build pools, shuffle, validate until targets are met."""
        pools = extract_candidate_pools(
            df,
            self.seed_usernames,
            self.bands,
            self.target_per_band,
        )
        rng = random.Random(self.random_state)
        evaluated: list[CandidateValidation] = []
        selected = {band: [] for band in self.target_per_band}

        for band, target in self.target_per_band.items():
            candidates = list(pools[band])
            rng.shuffle(candidates)
            logger.info(
                "Banda %s: %d candidatos disponibles, objetivo %d",
                band, len(candidates), target,
            )
            for candidate in candidates:
                logger.info(
                    "Validando %s para %s (%d/%d seleccionados)",
                    candidate.username,
                    band,
                    len(selected[band]),
                    target,
                )
                validation = self.validate_candidate(candidate)
                evaluated.append(validation)
                if validation.accepted:
                    selected[band].append(validation.username)
                    logger.info("%s aceptado para %s", validation.username, band)
                else:
                    logger.info("%s rechazado: %s", validation.username, validation.reason)
                if len(selected[band]) == target:
                    break

        candidate_counts = {band: len(pool) for band, pool in pools.items()}
        return selected, evaluated, candidate_counts

    def _build_result(self, selected, evaluated, candidate_counts) -> SelectionResult:
        """Wrap raw selection data into a SelectionResult."""
        return SelectionResult(
            policy={
                "source": self.policy["source"],
                "seed_usernames": self.seed_usernames,
                "cutoff": self.policy["cutoff"],
                "random_state": self.random_state,
                "min_eligible_games": self.min_games,
                "max_games_per_candidate": self.max_games,
                "target_per_band": self.target_per_band,
                "bands": {band: self.bands[band] for band in self.target_per_band},
            },
            candidate_counts=candidate_counts,
            evaluated=evaluated,
            selected=selected,
        )

    def select_from_dataframe(self, df: pd.DataFrame) -> SelectionResult:
        """Construye pools, los baraja y valida hasta cubrir cada objetivo.

        Raises ``InsufficientCandidatesError`` if any band falls short.
        """
        selected, evaluated, counts = self._run_selection(df)
        result = self._build_result(selected, evaluated, counts)
        if not result.is_complete:
            raise InsufficientCandidatesError(result)
        return result

    def select_lenient_from_dataframe(self, df: pd.DataFrame) -> SelectionResult:
        """Like ``select_from_dataframe`` but tolerates incomplete bands.

        Logs a warning for each band that didn't reach its target instead of
        raising. Intended for the DAG where a partial selection is still useful.
        """
        selected, evaluated, counts = self._run_selection(df)
        result = self._build_result(selected, evaluated, counts)
        if not result.is_complete:
            for band, target in self.target_per_band.items():
                got = len(result.selected.get(band, []))
                if got < target:
                    logger.warning(
                        "Banda %s: solo %d/%d jugadores seleccionados (pool: %d candidatos)",
                        band, got, target, counts.get(band, 0),
                    )
        return result

    def build_username_list(self, df: pd.DataFrame) -> tuple[list[str], SelectionResult]:
        """Run lenient selection and return a flat, deduplicated username list.

        The list starts with ``seed_usernames`` followed by the selected players,
        ready to feed the ``.expand()`` in the DAG's download task.

        Returns
        -------
        tuple[list[str], SelectionResult]
            The combined username list and the full selection result (for the manifest).
        """
        result = self.select_lenient_from_dataframe(df)
        seen: set[str] = set()
        combined: list[str] = []
        for username in self.seed_usernames:
            key = _normalise_username(username)
            if key not in seen:
                combined.append(username)
                seen.add(key)
        for usernames in result.selected.values():
            for username in usernames:
                key = _normalise_username(username)
                if key not in seen:
                    combined.append(username)
                    seen.add(key)
        logger.info(
            "Lista final: %d jugadores (seeds: %d, seleccionados: %d)",
            len(combined), len(self.seed_usernames),
            len(combined) - len(self.seed_usernames),
        )
        return combined, result


def bootstrap_username_list(config: dict[str, Any]) -> list[str]:
    """Return only the seed usernames when no processed parquet exists yet.

    This is the first-run path: the DAG downloads games for the seeds, processes
    them, and on the *next* run ``PlayerSelector.build_username_list`` can find
    opponents in the parquet to expand the sample.
    """
    seeds = config["player_selection"]["seed_usernames"]
    logger.info(
        "Modo bootstrap (sin parquet previo): usando %d seed_usernames: %s",
        len(seeds), seeds,
    )
    return list(seeds)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_manifest(result: SelectionResult, path: str | Path) -> Path:
    """Guarda el manifiesto de selección de forma atómica."""
    destination = Path(path)
    payload = yaml.safe_dump(result.to_manifest(), allow_unicode=True, sort_keys=False)
    _atomic_write_text(destination, payload)
    return destination


def apply_selection_to_config(
    config_path: str | Path,
    seed_usernames: list[str],
    selected: dict[str, list[str]],
) -> list[str]:
    """Actualiza sólo ``chess_com.usernames`` y preserva el resto del YAML y sus comentarios."""
    path = Path(config_path)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if re.fullmatch(r"  usernames:\s*\n?", line)),
        None,
    )
    if start is None:
        raise ValueError("No se encontró chess_com.usernames en la configuración")

    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        indentation = len(lines[end]) - len(lines[end].lstrip(" "))
        if stripped and not stripped.startswith("#") and indentation <= 2:
            break
        end += 1

    existing_lines: dict[str, str] = {}
    for line in lines[start + 1 : end]:
        match = re.match(r"\s*-\s*([^\s#]+)", line)
        if match:
            existing_lines[_normalise_username(match.group(1))] = line

    combined: list[str] = []
    seen: set[str] = set()
    for username in seed_usernames:
        key = _normalise_username(username)
        if key not in seen:
            combined.append(username)
            seen.add(key)
    for usernames in selected.values():
        for username in usernames:
            key = _normalise_username(username)
            if key not in seen:
                combined.append(username)
                seen.add(key)

    replacement = [lines[start]]
    for index, username in enumerate(combined):
        key = _normalise_username(username)
        if index == len(seed_usernames):
            replacement.append("    # Selección reproducible generada por scripts/seleccionar_jugadores.py.\n")
        replacement.append(existing_lines.get(key, f"    - {username}\n"))
    replacement.append("\n")

    updated = "".join(lines[:start] + replacement + lines[end:])
    parsed = yaml.safe_load(updated)
    if parsed["chess_com"]["usernames"] != combined:
        raise ValueError("La actualización de usernames no superó la validación")
    _atomic_write_text(path, updated)
    return combined
