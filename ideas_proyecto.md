# Ideas de proyecto — Ciencia de Datos (UTN FRM 2026)

Ideas alternativas de proyecto, con dataset disponible, pregunta a responder, variable objetivo
y features candidatas. Verificadas como disponibles a agosto 2026 y evaluadas contra los
7 criterios de la cátedra.

> ✅ **Idea en desarrollo:** F1 — degradación de neumáticos ("the cliff") con **FastF1**.
> Ver carpeta [`f1-tyre-degradation/`](./f1-tyre-degradation/) (Parte 0 + pipeline + dataset probado).
> Las demás ideas quedan acá como respaldo hasta la limpieza final del repo.

---

## Cómo elegir (criterios de la cátedra)

**Eliminatorios (si falla uno, no sirve):**
1. **Datos tidy** — cada fila una observación, cada columna una variable.
2. **Unidad alineada con la pregunta** — la fila coincide con aquello sobre lo que querés concluir.
3. **Algo modelable** — hay variable a predecir o grupos naturales.
4. **Descargable automatizado** — URL, API o scrapeable, **sin intervención humana**.

**Facilitadores (no rompen, pero complican):**
5. **Volumen** — > 1.000 filas, ideal > 10.000.
6. **≥ 5 columnas útiles** — mezclando numéricas, categóricas y fechas.
7. **Documentación entendible.**

> ⚠️ **FIFA / EA FC / sofifa queda descartado**: es el dataset que la cátedra usa para los TPs
> prácticos. No conviene repetirlo en el integrador.
>
> ⚠️ **Trampa de Kaggle con el criterio #4**: los *datasets* de Kaggle se bajan por API
> (`kaggle datasets download -d ...` con token) → cuenta como automatizado ✅. Pero los de
> *competición* (ej. PUBG) exigen **aceptar las reglas a mano en la web** antes de poder bajarlos
> → riesgo con el criterio eliminatorio #4. Preferir datasets, APIs abiertas o dumps con URL directa.

---

## Ranking según la rúbrica

1. **🏎️ F1** — cumple los 7 con holgura; el pipeline de joins luce y hay volumen de sobra.
2. **♟️ Ajedrez (Lichess)** — todo verde; dumps con URL directa (o API) = descarga automatizada limpia.
3. **🏀 NBA** — sólido y con volumen enorme; descarga por API/Kaggle-dataset.
4. **🔫 PUBG** — datos ricos pero ⚠️ descarga de competición (criterio #4) y tema muy trillado.
5. **🖥️ StarCraft 2 (SkillCraft)** — muy limpio pero ⚠️ pocas filas (~3.400) y casi todo numérico.

---

## 🎮 Ideas de videojuegos (frescas)

### 1. ♟️ Ajedrez — Predecir el resultado de la partida
- **Dataset:** [Chess Game Dataset (Lichess) — Kaggle](https://www.kaggle.com/datasets/datasnaek/chess) (~20.000 partidas). Para más volumen y descarga por URL directa: [database.lichess.org](https://database.lichess.org/) (millones de partidas en PGN) o la [API de Lichess](https://lichess.org/api).
- **Pregunta:** ¿Quién gana? (Blancas / Negras / Tablas) — clasificación multiclase. Variantes: ¿ganan las Blancas? (binaria) o predecir nº de turnos (regresión).
- **Target:** `winner`.
- **Features:** `white_rating`, `black_rating` y su diferencia, `rated`, `opening_name`/`opening_eco`/`opening_ply`, control de tiempo (`increment_code`). *(Cuidado con `turns` y `victory_status`: son post-partida → posible data leakage.)*
- **Criterios:** 1 ✅ (fila = partida) · 2 ✅ · 3 ✅ · 4 ✅ (dump URL / API / Kaggle) · 5 ✅ (20k, o millones) · 6 ✅ (numéricas + categóricas + fecha en los dumps) · 7 ✅.

### 2. 🔫 PUBG — Predecir la posición final del jugador en la partida
- **Dataset:** [PUBG Finish Placement Prediction — Kaggle](https://www.kaggle.com/c/pubg-finish-placement-prediction/data) (millones de filas, ~28-30 features).
- **Pregunta:** ¿En qué percentil termina el jugador? — regresión (`winPlacePerc`, 0 a 1). Variante: ¿queda en el top? (binaria).
- **Target:** `winPlacePerc`.
- **Features:** `kills`, `damageDealt`, `walkDistance`, `rideDistance`, `boosts`, `heals`, `weaponsAcquired`, `killPlace`, `matchDuration`, `numGroups`, etc.
- **Criterios:** 1 ✅ (fila = jugador-partida) · 2 ✅ · 3 ✅ · 4 ⚠️ (data de **competición**: hay que aceptar reglas a mano → revisar si sirve, o buscar un mirror como *dataset*) · 5 ✅ · 6 ✅ (mayormente numéricas) · 7 ✅. Tema muy trillado (muchas soluciones publicadas).

### 3. 🖥️ StarCraft 2 (SkillCraft) — Predecir la liga/nivel del jugador
- **Dataset:** [SkillCraft1 Master Table — UCI ML Repository](https://archive.ics.uci.edu/dataset/272/skillcraft1+master+table+dataset) (descarga por URL directa o paquete `ucimlrepo`).
- **Pregunta:** ¿En qué liga juega el jugador (Bronze → Professional)? — clasificación ordinal (8 clases).
- **Target:** `LeagueIndex` (1-8).
- **Features:** `APM` (acciones por minuto), `SelectByHotkeys`, `AssignToHotkeys`, `ActionLatency`, `NumberOfPACs`, `WorkersMade`, `TotalMapExplored`, `MinimapAttacks`, edad, horas jugadas por semana, etc. *(APM es la feature más predictiva.)*
- **Criterios:** 1 ✅ (fila = jugador) · 2 ✅ · 3 ✅ · 4 ✅ (URL directa) · 5 ⚠️ (**~3.400 filas**, pasa el mínimo pero lejos del ideal) · 6 ⚠️ (casi todo numérico, sin categóricas ni fechas) · 7 ✅.

---

## 🏆 Ideas de deportes (por si te sirven)

### 4. 🏎️ Fórmula 1 — Predecir podio / abandono / posición final
- **Dataset:** API [Jolpica-F1](https://github.com/jolpica/jolpica-f1) (sucesor libre de Ergast, `api.jolpi.ca`, 1950→2026, sin auth) o [F1 World Championship 1950-2020 — Kaggle](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020).
- **Pregunta:** ¿Termina en podio? / ¿Abandona (DNF)? (binaria) o ¿en qué posición termina? (regresión).
- **Target:** posición final / podio / DNF.
- **Features:** posición de largada, tiempo de qualy, escudería, circuito, nº de pit stops, ritmo de vuelta, forma reciente del piloto (últimas N carreras), clima.
- **Criterios:** 1 ✅ (fila = piloto-carrera, tras joins) · 2 ✅ · 3 ✅ · 4 ✅ (**API abierta sin auth**) · 5 ✅ (decenas de miles) · 6 ✅ (numéricas + categóricas + fecha) · 7 ✅. El pipeline de joins luce en la Entrega 1.

### 5. 🏀 NBA — Predecir el ganador del partido
- **Dataset:** [NBA Games — Kaggle (Nathan Lauga)](https://www.kaggle.com/datasets/nathanlauga/nba-games) o [NBA Database — wyattowalsh](https://www.kaggle.com/datasets/wyattowalsh/basketball) (64k+ partidos). También el paquete `nba_api`.
- **Pregunta:** ¿Gana el local? (binaria) o predecir estadísticas de un jugador (regresión).
- **Target:** resultado del partido (`HOME_TEAM_WINS`).
- **Features:** FG%, rebotes, asistencias, pérdidas, local/visitante, forma reciente, back-to-backs, ELO/ranking, head-to-head.
- **Criterios:** 1 ✅ (fila = partido o jugador-partido) · 2 ✅ · 3 ✅ · 4 ✅ (Kaggle-dataset API / `nba_api`) · 5 ✅ (64k+) · 6 ✅ · 7 ✅.

---

## 🚫 Descartadas

### 6. ⚽🎮 EA SPORTS FC / FIFA — DESCARTADO
Es el dataset que la cátedra usa para los TPs prácticos → no repetirlo en el integrador.

### 7. 🎮 Steam — Predecir el éxito de un juego
- **Dataset:** [Steam Games 2021-2025 (65k+) — Kaggle](https://www.kaggle.com/datasets/jypenpen54534/steam-games-dataset-2021-2025-65k) o [Steam Games (SteamSpy API)](https://www.kaggle.com/datasets/muhammadaqeelkabir/steam-games-dataset-steamspy-api).
- **Pregunta:** ¿Será bien recibido? (ratio de reseñas positivas — clasificación) o predecir nº de dueños/ventas estimadas (regresión).
- **Features:** géneros, precio, fecha de lanzamiento, desarrollador/publisher, plataformas, tags, tiempo de juego.
- **Criterios:** técnicamente cumple los 7 (Kaggle-dataset API), pero **tema muy quemado**.

---

Cuando elijas una, se arma la **Parte 0 / Definición**: pregunta en una frase + fuente con URL +
tipo de problema + variable objetivo + features (separando pre/post-partida) + métrica + baseline,
todo chequeado contra los 7 criterios para validar con el docente.
