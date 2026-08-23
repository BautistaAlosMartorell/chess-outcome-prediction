"""Genera un diccionario de columnas del dataset como imagen PNG + markdown,
para mostrar qué columnas hay y cuáles se usarían como features / target."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parent
df = pd.read_csv(BASE / "data" / "f1_laps_clean.csv")

# Rol de cada columna: (rol, descripción corta)
ROLES = {
    "LapTime":       ("TARGET", "Tiempo de vuelta (s) — lo que se predice (regresión)"),
    "TyreLife":      ("FEATURE (central)", "Vida del neumático (vueltas) — predictor central"),
    "Compound":      ("FEATURE (central)", "Compuesto: SOFT/MEDIUM/HARD — predictor central"),
    "TrackTemp":     ("FEATURE (central)", "Temperatura de pista (°C) — predictor central"),
    "LapNumber":     ("FEATURE", "Vuelta de carrera — representa el efecto del combustible"),
    "Stint":         ("FEATURE", "Nº de tanda entre paradas"),
    "FreshTyre":     ("FEATURE", "Si el neumático salió nuevo"),
    "AirTemp":       ("FEATURE", "Temperatura del aire (°C)"),
    "Humidity":      ("FEATURE", "Humedad (%)"),
    "Rainfall":      ("FEATURE", "Lluvia (bool)"),
    "Pressure":      ("feature (opcional)", "Presión atmosférica"),
    "WindSpeed":     ("feature (opcional)", "Velocidad del viento"),
    "WindDirection": ("feature (opcional)", "Dirección del viento"),
    "Sector1Time":   ("derivado", "Tiempo sector 1 (s)"),
    "Sector2Time":   ("derivado", "Tiempo sector 2 (s)"),
    "Sector3Time":   ("derivado", "Tiempo sector 3 (s)"),
    "SpeedI1":       ("derivado", "Velocidad en punto I1"),
    "SpeedI2":       ("derivado", "Velocidad en punto I2"),
    "SpeedFL":       ("derivado", "Velocidad en meta"),
    "SpeedST":       ("derivado", "Velocidad en recta (speed trap)"),
    "Year":          ("ID/contexto", "Temporada"),
    "Round":         ("ID/contexto", "Nº de carrera"),
    "Event":         ("ID/contexto", "Nombre del GP"),
    "Driver":        ("ID/contexto", "Piloto"),
    "DriverNumber":  ("ID/contexto", "Nº del piloto"),
    "Team":          ("ID/contexto", "Escudería"),
    "Position":      ("ID/contexto", "Posición en pista"),
    "LapStartTime":  ("ID/contexto", "Momento de inicio de la vuelta"),
    "PitInTime":     ("limpieza", "Entrada a boxes"),
    "PitOutTime":    ("limpieza", "Salida de boxes"),
    "TrackStatus":   ("limpieza", "Estado de pista (SC/VSC/amarilla)"),
    "Deleted":       ("limpieza", "Vuelta borrada por límites de pista"),
    "IsAccurate":    ("limpieza", "Vuelta marcada como fiable por FastF1"),
    "IsPitLap":      ("limpieza", "Vuelta de entrada/salida de boxes (derivada)"),
    "IsGreen":       ("limpieza", "Pista verde (derivada)"),
}

rows = []
for col in df.columns:
    rol, desc = ROLES.get(col, ("—", ""))
    ejemplo = df[col].dropna().iloc[0] if df[col].notna().any() else ""
    if isinstance(ejemplo, float):
        ejemplo = round(ejemplo, 2)
    rows.append([col, str(df[col].dtype), str(ejemplo)[:22], rol, desc])

table_df = pd.DataFrame(rows, columns=["Columna", "Tipo", "Ejemplo", "Uso", "Descripción"])

# ---- Markdown ----
md = ["# Diccionario de columnas — dataset F1 tyre degradation\n",
      f"Dataset: `data/f1_laps_clean.csv` — {len(df):,} vueltas × {df.shape[1]} columnas.",
      "Cada fila = una vuelta de un piloto en una carrera.\n",
      table_df.to_markdown(index=False),
      "\n**Leyenda:** TARGET · FEATURE (central) · FEATURE · feature (opcional) · derivado · ID/contexto · limpieza."]
(BASE / "diccionario_columnas.md").write_text("\n".join(md), encoding="utf-8")

# ---- PNG ----
color_map = {
    "TARGET": "#ffd6a5", "FEATURE (central)": "#caffbf", "FEATURE": "#e7ffd9",
    "feature (opcional)": "#f2f2f2", "derivado": "#f2f2f2",
    "ID/contexto": "#e5eeff", "limpieza": "#ffe5ec",
}
fig, ax = plt.subplots(figsize=(13, 0.42 * len(table_df) + 1.5))
ax.axis("off")
ax.set_title(f"Dataset F1 — degradación de neumáticos  |  {len(df):,} vueltas × {df.shape[1]} columnas\n"
             "Cada fila = una vuelta de un piloto en una carrera",
             fontsize=13, fontweight="bold", loc="left", pad=16)

tbl = ax.table(cellText=table_df.values, colLabels=table_df.columns,
               cellLoc="left", loc="center",
               colWidths=[0.13, 0.07, 0.13, 0.13, 0.54])
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1, 1.35)

for (r, c), cell in tbl.get_celld().items():
    cell.set_edgecolor("#dddddd")
    if r == 0:
        cell.set_facecolor("#222222"); cell.set_text_props(color="white", fontweight="bold")
    else:
        uso = table_df.iloc[r - 1]["Uso"]
        cell.set_facecolor(color_map.get(uso, "#ffffff"))

plt.tight_layout()
out_png = BASE / "diccionario_columnas.png"
plt.savefig(out_png, dpi=160, bbox_inches="tight")
print(f"Generado: {out_png}")
print(f"Generado: {BASE / 'diccionario_columnas.md'}")
