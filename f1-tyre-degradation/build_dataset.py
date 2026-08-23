"""
Pipeline de ingesta — F1 Tyre Degradation ("the cliff")
Proyecto Integrador · Ciencia de Datos · UTN FRM 2026

Descarga vuelta-a-vuelta de la Fórmula 1 usando FastF1 (telemetría/cronometraje
oficial) y construye un dataset TIDY donde cada fila es UNA vuelta de UN piloto en
UNA carrera. Descarga 100% automatizada: no se toca ningún CSV a mano.

Uso:
    python build_dataset.py --seasons 2023 2024 2025
    python build_dataset.py --seasons 2024 --max-races 3      # prueba rápida
    python build_dataset.py --seasons 2024 --only-clean       # solo vueltas verdes

Salida:
    data/f1_laps_raw.csv       -> todas las vueltas (con flags de limpieza)
    data/f1_laps_clean.csv     -> solo vueltas representativas para modelar
"""

import argparse
import warnings
from pathlib import Path

import fastf1
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
DATA_DIR = BASE_DIR / "data"
CACHE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

fastf1.Cache.enable_cache(str(CACHE_DIR))

# NOTA: no estimamos ni fabricamos la carga de combustible (la F1 no la publica).
# El efecto del combustible queda representado por `LapNumber` (dato real medido).
# Ver README.md para la justificación.

# Columnas de la vuelta que nos quedamos de session.laps
LAP_COLS = [
    "Driver", "DriverNumber", "Team", "LapNumber", "Stint",
    "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",
    "SpeedI1", "SpeedI2", "SpeedFL", "SpeedST",
    "Compound", "TyreLife", "FreshTyre",
    "PitInTime", "PitOutTime", "TrackStatus", "Position",
    "Deleted", "IsAccurate", "LapStartTime",
]

WEATHER_COLS = ["AirTemp", "TrackTemp", "Humidity", "Pressure",
                "WindSpeed", "WindDirection", "Rainfall"]

# Columnas del dataset "lean" (listo para modelar): identificación mínima + features + target.
# Se dejan afuera sectores/velocidades (son partes del LapTime -> leakage), DriverNumber
# (redundante con Driver) y las columnas que solo sirven para filtrar.
LEAN_COLS = [
    "Year", "Round", "Event", "Driver",        # identificación / contexto
    "LapNumber", "Stint", "TyreLife", "Compound", "FreshTyre",  # features
    "TrackTemp", "AirTemp", "Humidity", "Rainfall",             # features (clima)
    "LapTime",                                  # TARGET
]


def _td_to_seconds(series: pd.Series) -> pd.Series:
    """Convierte timedelta a segundos (float)."""
    return series.dt.total_seconds()


def process_session(year: int, rnd: int, event_name: str) -> pd.DataFrame | None:
    """Carga una carrera y devuelve sus vueltas como DataFrame tidy, o None si falla."""
    try:
        session = fastf1.get_session(year, rnd, "R")
        # telemetry=False: no necesitamos la telemetría de canal completo (pesa mucho);
        # weather=True: sí queremos el clima para mergear por vuelta.
        session.load(telemetry=False, weather=True, messages=False)
    except Exception as exc:  # carrera inexistente, datos no disponibles, etc.
        print(f"  [skip] {year} R{rnd} {event_name}: {exc}")
        return None

    laps = session.laps
    if laps is None or len(laps) == 0:
        print(f"  [skip] {year} R{rnd} {event_name}: sin vueltas")
        return None

    df = laps[[c for c in LAP_COLS if c in laps.columns]].copy()

    # Clima alineado a cada vuelta (FastF1 mergea por LapStartTime)
    try:
        weather = laps.get_weather_data().reset_index(drop=True)
        for c in WEATHER_COLS:
            if c in weather.columns:
                df[c] = weather[c].values
    except Exception as exc:
        print(f"  [warn] {year} R{rnd}: sin clima ({exc})")

    # Convertir tiempos (timedelta) a segundos
    for col in ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]:
        if col in df.columns:
            df[col] = _td_to_seconds(df[col])

    # Flags de limpieza derivados
    df["IsPitLap"] = df["PitInTime"].notna() | df["PitOutTime"].notna()
    df["IsGreen"] = df["TrackStatus"].astype(str) == "1"  # 1 = pista verde

    # Metadata de la carrera
    df.insert(0, "Year", year)
    df.insert(1, "Round", rnd)
    df.insert(2, "Event", event_name)

    print(f"  [ok] {year} R{rnd} {event_name}: {len(df)} vueltas")
    return df


def build(seasons: list[int], max_races: int | None) -> pd.DataFrame:
    all_laps = []
    for year in seasons:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        rounds = schedule["RoundNumber"].tolist()
        if max_races:
            rounds = rounds[:max_races]
        print(f"\n=== Temporada {year}: {len(rounds)} carreras ===")
        for rnd in rounds:
            event_name = schedule.loc[schedule["RoundNumber"] == rnd, "EventName"].iloc[0]
            df = process_session(year, rnd, event_name)
            if df is not None:
                all_laps.append(df)

    if not all_laps:
        raise SystemExit("No se descargó ninguna vuelta. Revisá conexión / temporadas.")
    return pd.concat(all_laps, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra a vueltas 'verdes y representativas' y se queda con las columnas lean."""
    mask = (
        df["IsAccurate"].fillna(False)      # FastF1 marca la vuelta como fiable
        & df["IsGreen"]                     # pista verde (sin SC/VSC/amarilla)
        & ~df["IsPitLap"]                   # sin entrada/salida de boxes
        & ~df["Deleted"].fillna(False)      # no borrada por límites de pista
        & df["LapTime"].notna()
        & df["Compound"].notna()
    )
    filtered = df[mask]
    return filtered[[c for c in LEAN_COLS if c in filtered.columns]].copy()


def main():
    parser = argparse.ArgumentParser(description="Ingesta F1 tyre degradation (FastF1)")
    # Una temporada (~21.000 vueltas limpias) ya supera el ideal de >10.000 filas.
    # Agregá más años (ej. --seasons 2023 2024 2025) solo si querés más variedad de
    # circuitos/temperaturas para robustecer el modelo.
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024])
    parser.add_argument("--max-races", type=int, default=None,
                        help="Limitar nº de carreras por temporada (para pruebas)")
    parser.add_argument("--only-clean", action="store_true",
                        help="Guardar solo el dataset limpio")
    args = parser.parse_args()

    raw = build(args.seasons, args.max_races)

    if not args.only_clean:
        raw_path = DATA_DIR / "f1_laps_raw.csv"
        raw.to_csv(raw_path, index=False)
        print(f"\n[guardado] {raw_path}  ({len(raw):,} vueltas, {raw.shape[1]} columnas)")

    cleaned = clean(raw)
    clean_path = DATA_DIR / "f1_laps_clean.csv"
    cleaned.to_csv(clean_path, index=False)
    print(f"[guardado] {clean_path}  ({len(cleaned):,} vueltas, {cleaned.shape[1]} columnas — dataset para modelar)")

    print("\nResumen:")
    print(f"  Vueltas totales : {len(raw):,}")
    print(f"  Vueltas limpias : {len(cleaned):,} ({len(cleaned)/len(raw)*100:.1f}%)")
    print(f"  Carreras        : {raw.groupby(['Year','Round']).ngroups}")
    print(f"  Compuestos      : {sorted(cleaned['Compound'].dropna().unique())}")


if __name__ == "__main__":
    main()
