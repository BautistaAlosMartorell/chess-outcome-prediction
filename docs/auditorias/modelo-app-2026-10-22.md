# Auditoría del modelo final de la app · 22/10/2026

## Dictamen

La app transmite correctamente las probabilidades del artefacto, pero el modelo final **no queda validado para comparar niveles de ambos jugadores**. Los promedios de resultado por banda son razonables; los controles de diferencia de rating y varios enfrentamientos reales muestran una respuesta insuficiente o invertida. No se reemplazó ni reentrenó el artefacto durante esta revisión.

## Alcance y reproducción

- Modelo: `models/modelo_en_vivo.joblib`, random forest, 40 columnas, entrenado hasta `2026-07-04T01:29:25+00:00`.
- SHA-256: `25051ff7bd92a11b8911c69ee0fbf0152a780b84ddf5b688e895a31d45cebe8d`.
- Se evaluaron 20.080 partidas posteriores al corte de entrenamiento y 53.423 posiciones en plies 0, 20 y 60. Cada partida pesa una vez dentro de cada corte.
- Ese período ya se observó en los notebooks previos: esta es una auditoría descriptiva, no un holdout nuevo ni evidencia para elegir y volver a evaluar una corrección en el mismo período.
- Se ejercitó el endpoint real `GET /jugadores/{usuario}/analisis` con TestClient sobre 21 partidas públicas únicas de seis bandas de cuentas; 15 tenían los dos ratings previos disponibles. Se comprobaron todas las probabilidades de sus curvas, no sólo las iniciales.
- Primera muestra: primera cuenta de cada banda del manifiesto. Segunda: cuenta con cierre local más reciente de cada banda. Por cuenta se eligen la última partida y la de mayor diferencia de rating mostrado entre sus últimas 40, deduplicando si coinciden. Es una muestra de diagnóstico deliberada; no estima la calibración de toda Chess.com.
- Las bandas del manifiesto identifican las cuentas de origen, no el nivel actual en todos los ritmos. Una cuenta élite en blitz puede tener otro rating en rapid.
- Las consultas públicas quedan capturadas en snapshots locales para repetir la auditoría sin red. No se guardan partidas ni snapshots en git.

```bash
.venv/bin/python -m src.audit_predictions --output /tmp/auditoria-probabilidades.json
.venv/bin/python -m api.audit_predictions --snapshot /tmp/auditoria-app-fuentes.json --output /tmp/auditoria-app.json
.venv/bin/python -m api.audit_predictions --active-accounts --snapshot /tmp/auditoria-app-activos-fuentes.json --output /tmp/auditoria-app-activos.json
```

Una segunda ejecución de los comandos de la app reutiliza los snapshots existentes. Sin esos archivos, captura una muestra nueva y puede obtener otras partidas. Requiere las dependencias de `api/requirements.txt`. La auditoría poblacional requiere los Parquets y los JSON de las 120 cuentas.

## 1. Integridad del camino de la app

- En todas las curvas de la muestra, probabilidades finitas, entre 0 y 1 y suma 1 con tolerancia 1e-9.
- Paridad entre la respuesta del endpoint y `src.predict.predecir`, reconstruyendo con el contexto previo publicado por el propio endpoint: tolerancia 1e-12 en todos los plies.
- En la auditoría poblacional, derivar primero el historial y luego ejecutar el resto del Pipeline reproduce el Pipeline completo a 1e-12 en 128 filas de control.
- La API ordena las clases por nombre; la interfaz muestra esos valores multiplicados por 100 y redondeados. No se encontró inversión de colores. La duración en plies se divide por dos para mostrar jugadas por bando.
- También se consultó el servidor ya levantado en `localhost:8000`, cuyo `/salud` declara la misma familia, 40 columnas, fecha y rango. Reprodujo las probabilidades de Hikaru–Sina, arnav3188–Raunak y brunokbrera–Alann10. Una primera consulta de Hikaru devolvió HTTP 500; al repetirla respondió 200 con los valores esperados. La causa de ese fallo transitorio no se estableció; es un incidente separado de las probabilidades.

## 2. Partidas reales que muestran la limitación

Ratings **previos reconstruidos por la app**, del mismo ritmo y con cierre anterior al inicio. No son los ratings posteriores del listado. Valores de la posición inicial; B/T/N = blancas/tablas/negras.

| Partida | Ritmo | ELO B / N | B % | T % | N % |
|---|---|---:|---:|---:|---:|
| [AleMLira78 – Adriano_ar](https://www.chess.com/game/live/185666253050) | rapid | 900 / 916 | 49.56 | 5.39 | 45.05 |
| [Kotamjaru – Alann10](https://www.chess.com/game/live/185744940498) | blitz | 1364 / 1366 | 35.79 | 8.48 | 55.73 |
| [brunokbrera – Alann10](https://www.chess.com/game/live/185265709452) | blitz | 733 / 1358 | 44.89 | 7.18 | 47.93 |
| [ABBESALI – M1ndOverMatter10](https://www.chess.com/game/live/185662477986) | blitz | 2185 / 2318 | 41.30 | 8.35 | 50.35 |
| [ogpin – sleepdeprivation1](https://www.chess.com/game/live/184767228718) | bullet | 2533 / 2560 | 51.79 | 7.24 | 40.98 |
| [Slawomir_Kurpiewski – ogpin](https://www.chess.com/game/live/185361990435) | bullet | 2009 / 2587 | 43.00 | 5.62 | 51.38 |
| [God-of-brilliancy – Vojtastr](https://www.chess.com/game/live/185763829244) | blitz | 2698 / 2715 | 49.52 | 8.98 | 41.51 |
| [Visheshopchess100 – Vojtastr](https://www.chess.com/game/live/185693626892) | blitz | 2044 / 2744 | 45.02 | 8.94 | 46.05 |
| [RaunakSadhwani2005 – pheonixking2000](https://www.chess.com/game/live/185501485026) | blitz | 3151 / 3064 | 54.18 | 10.98 | 34.83 |
| [arnav3188 – RaunakSadhwani2005](https://www.chess.com/game/live/184516658034) | rapid | 108 / 2686 | 34.41 | 11.86 | 53.74 |
| [Hikaru – Sina-Movahed](https://www.chess.com/game/live/186999389881) | blitz | 3474 / 3349 | 37.34 | 19.92 | 42.74 |

No se declara incorrecta una probabilidad porque perdió el favorito ni se asigna un porcentaje verdadero a una partida aislada. El problema es la respuesta del modelo frente a diferencias amplias de rating y a cambios controlados en los mismos datos. Los casos con 578, 625, 700 y 2578 puntos de diferencia reciben probabilidades de victoria de las blancas cercanas a 43–45 % o 34 %, pese a ser el lado de menor rating. Esto exige evaluar específicamente ese régimen, casi ausente del entrenamiento con los dos ratings conocidos.

## 3. Cobertura: la validación global no representa bien el uso con dos historiales

- Entrenamiento: sólo **185 de 80,314 partidas** con ambos ratings previos (0.23 %).
- Evaluación posterior: **85 de 20.080** con ambos ratings; 19.980 con un solo lado y 15 sin ninguno. De esas 85, 83 pertenecen al grupo élite según el promedio de rating previo conocido y dos al grupo top mundial.
- Sólo 33 partidas evaluables tienen dos ratings conocidos y una diferencia absoluta de al menos 100. No hay soporte para una tabla empírica sólida de probabilidades por diferencia de ELO en todas las bandas.
- La app consulta ambos historiales; la mayor parte del entrenamiento recibe un lado faltante y pasa por imputación. Es una diferencia de distribución de entradas importante. Las 40 columnas incluyen ratings separados, pero ninguna diferencia explícita de rating.
- Esta cobertura hace plausible que se aprendan asociaciones de nivel absoluto, forma y muestreo sin aprender bien la ventaja relativa. Es un diagnóstico compatible con la evidencia, no una demostración causal de cuál corrección funcionará.

## 4. Promedios por nivel: razonables, pero insuficientes

Nivel calculado con el promedio de los ratings previos disponibles; casi siempre corresponde a un único jugador. No se usa rating posterior para completar al rival. Cada celda predicha se compara con la frecuencia observada en ese mismo grupo. Las partidas repiten cuentas y no son observaciones independientes.

| Nivel conocido | n | B pred. % | B real % | T pred. % | T real % | N pred. % | N real % |
|---|---:|---:|---:|---:|---:|---:|---:|
| principiante | 3288 | 49.76 | 47.51 | 4.84 | 3.89 | 45.40 | 48.60 |
| intermedio | 5766 | 48.96 | 48.70 | 5.02 | 4.87 | 46.02 | 46.43 |
| avanzado | 1094 | 49.15 | 52.65 | 5.36 | 4.11 | 45.49 | 43.24 |
| experto | 580 | 48.68 | 50.52 | 6.98 | 6.72 | 44.34 | 42.76 |
| top_mundial | 2756 | 48.19 | 49.60 | 9.16 | 8.71 | 42.66 | 41.69 |
| elite | 6581 | 47.40 | 48.91 | 9.64 | 10.32 | 42.97 | 40.77 |

El mayor desajuste agregado por clase entre estas bandas es de 3,50 puntos porcentuales. Eso permite afirmar que no hay un desvío masivo en los promedios de banda, pero puede ocultar errores compensados entre favoritos y jugadores de menor rating.

## 5. Controles de rating sobre una misma posición inicial

Blitz 180+0, sin torneo y sin forma reciente para ambos lados. Se mantiene el rating medio y sólo se intercambian 200 puntos de ventaja entre colores. Todos estos ratings individuales están dentro del rango declarado del artefacto. Es una prueba sintética de comportamiento, no calibración empírica.

| Rating medio | P(B gana) con B −200 ELO | Con igual ELO | Con B +200 ELO |
|---|---:|---:|---:|
| 1000 | 47.79 % | 47.42 % | 49.10 % |
| 1500 | 46.59 % | 47.71 % | 49.98 % |
| 2000 | 49.43 % | 50.30 % | 48.08 % |
| 2400 | 45.76 % | 48.97 % | 52.21 % |
| 2800 | 52.02 % | 50.91 % | 49.73 % |
| 3200 | 55.61 % | 55.77 % | 53.14 % |

La respuesta se invierte en medias de 2000, 2800 y 3200. Por tanto, el problema no se limita a extrapolar por encima del máximo de entrenamiento de 3403 ni a la pausa de Hikaru.
Como otro control, al aumentar en 200 el rating de blancas en 9187 contextos reales sin superar el máximo del artefacto, su probabilidad baja en 48.16 % de ellos. Mantener la forma fija mientras cambia el rating puede producir combinaciones poco frecuentes; esta prueba señala comportamiento irregular, no mide directamente el error en partidas reales.

## 6. Pausas: sensibilidad, sin atribuir fatiga

`minutos_desde_anterior` mide tiempo desde el último cierre observado, sin exigir el mismo ritmo. No mide sueño, cansancio ni descanso real; un historial truncado puede sobreestimar esa pausa. La app y el entrenamiento también pueden observar ventanas diferentes de historial.
- Se sumó exactamente un minuto a la pausa de blancas, manteniendo el resto de las variables fijas, en 10.090 posiciones iniciales con ese dato conocido.
- Cambio absoluto del percentil 95: **5,44 puntos**; máximo: **14,80 puntos**. Un **6,40 %** cambia más de cinco puntos. El cambio medio firmado es −0,30 puntos; no existe una penalización uniforme por descansar más.
- Al hacer faltantes las pausas de ambos lados, cambia el favorito entre blancas/negras en **14,69 %** de las partidas. Con toda la forma faltante cambia en **29,52 %**.
- Hacer faltante una variable activa el imputador del modelo existente. No equivale a entrenar un modelo sin esa variable ni prueba que retirarla mejore la predicción. Mantener partidas de sesión fijas al cambiar la pausa también puede generar un contexto inconsistente si se cruza el umbral de sesión de 30 minutos.

## 7. Durante la partida y duración

| Ply | Partidas en curso | Log-loss | MAE de duración (plies) | Sesgo duración (plies) |
|---|---:|---:|---:|---:|
| 0 | 20080 | 0.8662 | 27.31 | -7.12 |
| 20 | 19622 | 0.8577 | 26.33 | -6.51 |
| 60 | 13721 | 0.7632 | 20.47 | -5.61 |

Cada corte tiene otra población porque sólo sobreviven partidas que lo alcanzan; la caída de log-loss de esta tabla no mide por sí sola la mejora sobre las mismas partidas. La duración inicial tiene un error absoluto medio de **13,65 jugadas por bando** y subestima en promedio **3,56**. Es una estimación gruesa, no una cuenta regresiva exacta. El JSON reproducible también incluye métricas por banda, ritmo y corte.

## 8. Comprobaciones y siguiente corrección a evaluar

- `python -m unittest discover -s tests`: 86 pruebas ejecutadas; permanece el fallo conocido de una prueba en dos subcasos de dama ganada (+9,02/+10,34 puntos, frente a +15 exigidos). No se cambió el umbral ni se declara la suite en verde.
- Los dos scripts se ejecutaron hasta terminar con asserts de integridad, paridad y anti fan-out. No se modificaron API de producción, interfaz, datos de entrenamiento ni modelo.
- Antes de cambiar hiperparámetros por los casos anteriores, ampliar la cobertura causal de los rivales para que el entrenamiento represente la entrada que la app usa. Evaluar diferencia de rating explícita y una referencia sencilla basada en ambos ratings, por ritmo y nivel.
- Comparar con/sin pausas mediante reentrenamiento y CV temporal por partida; no decidir por su importancia ni por hacerlas faltantes en el modelo actual. Revisar la consistencia de la ventana observada del historial y la definición de sesión.
- Validar por separado posición inicial y posiciones en curso, y construir una evaluación temporal nueva con suficientes enfrentamientos de ambos ratings conocidos y diferentes brechas. No forzar resultados para Hikaru ni convertir una fórmula de puntuación esperada en probabilidades de victoria sin modelar tablas.
