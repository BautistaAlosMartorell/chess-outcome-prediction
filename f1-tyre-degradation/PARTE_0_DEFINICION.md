# Parte 0 — Definición del Proyecto

**Proyecto Integrador · Ciencia de Datos · UTN FRM 2026**
**Tema:** Degradación de neumáticos en Fórmula 1 — predicción de "the cliff"

---

## 1. Pregunta de investigación

> **¿Cómo evoluciona el tiempo de vuelta de un piloto a medida que aumenta la vida del neumático dentro de un stint, y en qué vuelta ese deterioro entra en fase crítica ("the cliff"), según el compuesto y la temperatura de pista?**

> **Nota:** la pregunta **no incluye el combustible** como variable. La F1 no publica la carga de
> combustible y no está en la API, por lo que estimarla sería inventar datos. En su lugar usamos
> `LapNumber` (la vuelta de carrera, dato real medido), que representa el efecto del combustible sin
> fabricar ninguna cantidad. Ver la justificación completa en el `README.md`.

Unidad de análisis: **una vuelta de un piloto en una carrera** (fila del dataset).

### Glosario
- **Degradación no lineal / "the cliff":** los neumáticos mantienen buen agarre varias vueltas y luego caen de golpe, perdiendo 1-2 s por vuelta. Predecir ese punto es la clave de la estrategia.
- **Compuesto:** tipo de goma (Soft / Medium / Hard); cada uno balancea velocidad inicial vs. durabilidad.
- **Stint:** tanda de vueltas entre dos paradas en boxes.
- **Undercut / Overcut:** parar una vuelta antes / después que el rival para adelantarlo con gomas frescas.

---

## 2. Hipótesis de trabajo

1. El tiempo de vuelta **crece de forma no lineal** con la vida del neumático: casi plano al principio y con un quiebre ("cliff") a partir de cierta vuelta del stint.
2. Ese punto de quiebre **llega antes** en compuestos blandos y con **mayor temperatura de pista**.
3. La **vida del neumático** (`TyreLife`) y el **compuesto** son predictores más fuertes que las variables meteorológicas.

---

## 3. Fuente de datos y automatización (Entrega 1)

- **Herramienta:** paquete **[FastF1](https://docs.fastf1.dev/)** (Python), que consulta los servidores oficiales de telemetría y cronometraje de la F1. Repo: <https://github.com/theOehrly/Fast-F1>.
- **Descarga 100 % automatizada:** el script [`build_dataset.py`](./build_dataset.py) baja temporadas completas y arma el dataset. **No se toca ningún CSV a mano.**
  ```bash
  pip install -r requirements.txt
  python build_dataset.py --seasons 2023 2024 2025
  ```
- **Salida:**
  - `data/f1_laps_raw.csv` — todas las vueltas con flags de limpieza.
  - `data/f1_laps_clean.csv` — vueltas "verdes y representativas" para modelar.

> **Nota de reproducibilidad:** FastF1 cachea la telemetría descargada en `cache/`. La primera corrida tarda; las siguientes son instantáneas.

---

## 4. Validación contra los 7 criterios de la cátedra

| # | Criterio | Estado | Justificación |
|---|----------|--------|---------------|
| 1 | Datos tidy | ✅ | Cada fila = 1 vuelta de 1 piloto en 1 carrera. |
| 2 | Unidad alineada | ✅ | La pregunta es sobre degradación vuelta-a-vuelta → unidad = vuelta. |
| 3 | Modelable | ✅ | Regresión (tiempo de vuelta) y clasificación ("cliff"). |
| 4 | Descarga automatizada | ✅ | FastF1 = pipeline en Python, sin intervención manual. |
| 5 | Volumen | ✅ | **22.999 vueltas limpias con UNA temporada** (2024, 24 carreras) — >>10.000 ideal. Sumar temporadas es opcional (más variedad). |
| 6 | ≥5 columnas útiles | ✅ | Dataset para modelar: **14 columnas** (features numéricas + categóricas + target). El `_raw` conserva las 35 originales (ver §6). |
| 7 | Documentación | ✅ | FastF1 documenta cada campo; este doc mapea las columnas. |

---

## 5. Problema de Machine Learning (Entrega 3)

**Problema principal — Regresión (target medido y objetivo):**
- Predecir el **tiempo de vuelta** (`LapTime`) — o su *delta* respecto a la mejor vuelta del stint — en función de la vida del neumático, el compuesto, la temperatura de pista y la vuelta de carrera (`LapNumber`).
- Métricas: **MAE / RMSE** (en segundos). Interpretable directamente.

**Problema secundario — Clasificación ("the cliff"):**
- Predecir si en la próxima vuelta el neumático **entra en degradación crítica**.
- ⚠️ **No existe una etiqueta de "cliff" en los datos: hay que construirla** a partir de los tiempos reales. Definición propuesta (a validar en la Entrega 2):
  una vuelta está "en el cliff" si su `LapTime` supera en más de **X segundos** (p. ej. 0.8 s) la tendencia base del stint, o vía **detección de change-point** por stint.
- Métricas: **F1-score / precision-recall** (clase desbalanceada).
- Baseline a superar: "el cliff llega siempre en la vuelta N del compuesto" (regla fija por compuesto).

**Baseline de regresión a superar:** modelo lineal `LapTime ~ TyreLife` por compuesto.

---

## 6. Variables del dataset (reales, generadas por el pipeline)

El pipeline produce **dos archivos**: `f1_laps_raw.csv` con las **35 columnas** que baja FastF1 (para transparencia/EDA), y `f1_laps_clean.csv` con las **14 columnas** que efectivamente usamos para modelar (filtradas y depuradas). El diccionario visual está en `diccionario_columnas.png`.

**Dataset para modelar (14 columnas):** `Year`, `Round`, `Event`, `Driver` (identificación) · `LapNumber`, `Stint`, `TyreLife`, `Compound`, `FreshTyre`, `TrackTemp`, `AirTemp`, `Humidity`, `Rainfall` (features) · `LapTime` (target).

<details><summary>Columnas del dataset _raw completo (35)</summary>

**Identificación / contexto:** `Year`, `Round`, `Event`, `Driver`, `Team`, `Position`.

**Estructura de la vuelta:** `LapNumber` (vuelta de carrera — representa el efecto del combustible sin estimarlo), `Stint`, `LapStartTime`.

**Objetivo / rendimiento (numéricas):** `LapTime`, `Sector1Time`, `Sector2Time`, `Sector3Time`, `SpeedI1`, `SpeedI2`, `SpeedFL`, `SpeedST`.

**Neumático (feature central):** `Compound` (categórica: SOFT/MEDIUM/HARD), `TyreLife` (vueltas acumuladas de la goma), `FreshTyre`.

**Clima (mergeado por vuelta):** `AirTemp`, `TrackTemp`, `Humidity`, `Pressure`, `WindSpeed`, `WindDirection`, `Rainfall`.

**Flags de limpieza:** `IsAccurate`, `IsGreen`, `IsPitLap`, `Deleted`, `TrackStatus`, `PitInTime`, `PitOutTime`.

</details>

### ⚠️ Puntos metodológicos declarados (honestidad de los datos)
1. **No estimamos el combustible.** La F1 no publica la carga de combustible, así que **no fabricamos ninguna columna**. Usamos `LapNumber` (dato real medido) como variable que representa el efecto del combustible: se quema de forma pareja vuelta a vuelta, así que la vuelta de carrera lo captura sin inventar cantidades. Ver justificación completa en el `README.md`.
2. **El "cliff" es un target construido** a partir de tiempos reales, no una columna de origen (ver §5). Definir la etiqueta desde el dato medido es *derivar un target* (práctica estándar en ML), no inventar datos. Es el mayor desafío — y la parte más original — del proyecto.
3. **Limpieza pesada obligatoria.** El tiempo de vuelta se contamina con Safety Car / VSC, banderas amarillas, tráfico, vueltas de boxes y borradas por límites de pista. Se filtra con `IsAccurate`, `IsGreen`, `IsPitLap` y `Deleted` (en la prueba de 3 carreras se retuvo el 87.8 % de las vueltas).

---

## 7. Aplicación final (Entrega 4)

Simulador de estrategia interactivo (**Streamlit / Dash**): elegís circuito, piloto, compuesto y condiciones meteorológicas, y la app proyecta la curva de degradación y la **ventana óptima de parada** (undercut / overcut).

---

## 8. Plan por entregas

| Entrega | Fecha | Qué se presenta |
|---------|-------|-----------------|
| Definición | 12/08 | Este documento (pregunta + fuente validada). |
| 1 · Ingeniería de datos | 02/09 | `build_dataset.py` funcionando + dataset tidy + limpieza. |
| 2 · EDA | 16/09 | Curvas de degradación por compuesto/temperatura; **definición del "cliff"** validada con datos. |
| 3 · Modelado | 14/10 | Regresión de tiempo de vuelta + clasificación del cliff; modelos comparados y métricas. |
| 4 · Visualización + app | 04/11 | Simulador de estrategia en Streamlit/Dash. |
| Exposición final | 18/11 | Presentación + demo en vivo. |
