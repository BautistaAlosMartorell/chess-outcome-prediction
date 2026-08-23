# Entrega 0 — Definición del proyecto

**Ciencia de Datos · UTN FRM 2026**
**Tema:** Degradación de neumáticos en Fórmula 1 — predicción de "the cliff"

---

## 1. Pregunta de investigación

> **¿Cómo evoluciona el tiempo de vuelta de un piloto a medida que aumenta la vida del neumático dentro de un stint, y en qué vuelta ese deterioro entra en fase crítica ("the cliff"), según el compuesto y la temperatura de pista?**

**Glosario rápido:**
- **"The cliff" (el acantilado):** los neumáticos rinden bien durante varias vueltas y en cierto punto caen de golpe, perdiendo 1-2 segundos por vuelta. Predecir ese punto es la clave de la estrategia.
- **Compuesto:** tipo de goma (Soft / Medium / Hard); cada uno balancea velocidad inicial vs. durabilidad.
- **Stint:** tanda de vueltas que da un piloto entre dos paradas en boxes.

---

## 2. Fuente de datos y automatización

- **Fuente:** paquete **[FastF1](https://docs.fastf1.dev/)** (Python), que consulta directamente los servidores oficiales de telemetría y cronometraje de la Fórmula 1. Repositorio: <https://github.com/theOehrly/Fast-F1>.
- **Descarga 100 % automatizada:** un script en Python (`build_dataset.py`) baja las temporadas completas y arma el dataset. **No se toca ningún CSV a mano.**
- **Unidad de análisis:** cada fila del dataset es **una vuelta de un piloto en una carrera** (datos tidy).
- **Volumen:** con **una sola temporada (2024, 24 carreras)** obtenemos **26.604 vueltas → 22.999 vueltas limpias**, muy por encima del ideal de >10.000 filas.

**Cómo lo armamos (pipeline):**
1. Descargamos las vueltas de cada carrera de la temporada con FastF1.
2. Mergeamos el clima (temperatura de pista, aire, humedad, lluvia) a cada vuelta.
3. Convertimos los tiempos a segundos y agregamos flags de limpieza.
4. **Filtramos** a vueltas "verdes y representativas": sacamos las afectadas por Safety Car / VSC, banderas amarillas, entradas/salidas de boxes y vueltas borradas por límites de pista (si no, la señal de degradación se ensucia).
5. Nos quedamos con las **columnas que realmente usamos** (dataset "lean").

El pipeline genera dos archivos: `f1_laps_raw.csv` (todas las columnas que baja FastF1, por transparencia) y `f1_laps_clean.csv` (el dataset depurado y listo para modelar).

---

## 3. Qué vamos a predecir (variable objetivo)

- **Problema principal — Regresión:** predecir el **tiempo de vuelta** (`LapTime`) en función de la vida del neumático, el compuesto, la temperatura y la vuelta de carrera.
- **Problema secundario — Clasificación:** predecir si una vuelta está **"en el cliff"**. Esa etiqueta **no existe en los datos: la construimos** a partir de los tiempos de vuelta reales (detectando el salto brusco dentro del stint). Definir un target a partir de datos medidos es una práctica estándar de machine learning, no inventar datos.

---

## 4. Las columnas del dataset y para qué las usamos

El dataset final tiene **14 columnas**. Cada fila = una vuelta de un piloto en una carrera.

| Columna | Tipo | Rol | Para qué la usamos |
|---|---|---|---|
| `LapTime` | numérica | **🎯 TARGET** | Tiempo de vuelta (en segundos). Es lo que predecimos, y de donde derivamos la etiqueta del "cliff". |
| `TyreLife` | numérica | **⭐ Feature central** | Vueltas acumuladas del neumático. Es el predictor principal de la degradación. |
| `Compound` | categórica | **⭐ Feature central** | Compuesto (SOFT/MEDIUM/HARD). Cada goma degrada distinto. |
| `TrackTemp` | numérica | **⭐ Feature central** | Temperatura de pista (°C). Afecta cuándo llega el cliff. |
| `LapNumber` | numérica | **Feature** | Vuelta de carrera. Representa el efecto del combustible (ver punto 5) sin estimarlo. |
| `Stint` | numérica | **Feature** | Número de tanda entre paradas. Ubica la vuelta dentro de la estrategia. |
| `FreshTyre` | booleana | **Feature** | Si el neumático salió nuevo. |
| `AirTemp` | numérica | **Feature** | Temperatura del aire (°C). |
| `Humidity` | numérica | **Feature** | Humedad (%). |
| `Rainfall` | booleana | **Feature** | Si hay lluvia. |
| `Year` | numérica | Identificación | Temporada. |
| `Round` | numérica | Identificación | Número de carrera. |
| `Event` | texto | Identificación | Nombre del Gran Premio. |
| `Driver` | categórica | Identificación | Piloto (código de 3 letras, ej. VER = Verstappen). |

**Resumen:** 1 target (`LapTime`), 9 features y 4 columnas de identificación (para saber de qué vuelta/piloto/carrera es cada fila; no entran al modelo como predictoras).

---

## 5. Decisiones metodológicas (por qué NO usamos ciertas cosas)

**a) No usamos el combustible.**
La pregunta original hablaba del "consumo de combustible", pero **la F1 no publica la carga de combustible** y no está disponible en la API. Estimarla sería inventar datos, así que la sacamos. Su efecto (el auto se aliviana y va más rápido a medida que quema nafta) **queda representado por `LapNumber`**, que es un dato real medido: como el combustible se quema de forma pareja vuelta a vuelta, la vuelta de carrera captura ese efecto sin fabricar ninguna cantidad.

**b) `LapTime` es el target, no una feature.**
El tiempo de vuelta es lo que queremos predecir/explicar. Una variable no puede ser entrada y salida del mismo modelo. Y el "cliff" no es una variable aparte: **es un comportamiento del propio tiempo de vuelta** (el momento en que se dispara). Por eso lo usamos como objetivo, no como predictor.

**c) No usamos sectores ni velocidades como features.**
Los tiempos de sector (S1+S2+S3) y las velocidades **son partes del tiempo de vuelta**. Usarlas para predecir el tiempo de vuelta sería *data leakage* (hacer trampa, predecir el resultado con pedazos del propio resultado). Están en el archivo `_raw` por transparencia, pero no en el dataset de modelado.

---

## 6. Validación contra los criterios de la cátedra

| Criterio | Cumple | Cómo |
|---|---|---|
| Datos tidy | ✅ | Cada fila = 1 vuelta de 1 piloto en 1 carrera. |
| Unidad alineada con la pregunta | ✅ | La pregunta es sobre degradación vuelta a vuelta → la unidad es la vuelta. |
| Algo modelable | ✅ | Regresión (tiempo de vuelta) + clasificación (el cliff). |
| Descarga automatizada | ✅ | FastF1 = pipeline en Python, sin intervención manual. |
| Volumen suficiente | ✅ | 22.999 vueltas con una temporada (>>10.000). |
| Varias columnas informativas | ✅ | Features numéricas + categóricas + booleanas + target. |
| Documentación entendible | ✅ | FastF1 documenta cada campo; este documento mapea las columnas. |
