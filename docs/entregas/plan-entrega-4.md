# Plan · Entrega 4: la app cuenta el proyecto (copa de martini)

## Contexto

La consigna de la Entrega 4 (`docs/entregas/consigna-entrega-4.md`, recibida el 22/10) pide **una app web publicada en
una URL pública** que cuente el proyecto y deje usarlo. La entrega es el **11/11**, o el
13/11 para la 5K10, y la expo final es el **25/11**: las fechas viejas, 04/11 y 18/11, están
mal en la skill y en el kit. La estructura que pide es una "copa de martini":

- **Portada:** la idea central en una oración y tres números que la sostienen.
- **Tallo**, guiado por el autor: *Los datos*, *Lo que encontramos* y *El modelo*. Cada
  sección tiene un título que afirma algo, un gráfico que lo prueba y un desplegable
  «Cómo lo sabemos», cerrado por defecto, con la evidencia técnica.
- **Copa**, que maneja el usuario: *Explorá* (un panorama, al menos dos controles que
  cambian el gráfico y el detalle de cada caso con lo que dijo el modelo) y *Probá el
  modelo* (un caso nuevo, con aviso si cae fuera de lo que vio el modelo).
- **Gráficos hechos con Altair**, con colores y escalas que significan lo mismo en toda
  la app.
- **Un script de construcción** que toma los datos del pipeline y el modelo y genera la
  app. Lo que muestra la app tiene que coincidir con los notebooks.

La app actual (Next.js + FastAPI) ya cubre *Probá el modelo*: `/jugar` y `/analizar`
avisan con `AvisoRango` cuando el rating cae fuera de lo visto. No tiene portada
con la oración, ni tallo, ni Explorá, ni Altair, ni URL pública. El grupo decidió
**quedarse con FastAPI + Next.js** y publicarla gratis. La consigna nombra "HTML o
Streamlit", así que hay que **confirmar con el docente** que esta forma vale. La
plataforma de publicación queda para el final (se decide al final). El contenido no
depende de esa decisión.

Rama: `feat/entrega-4-app` desde `main` (skill `git-workflow`). Pedir confirmación
antes de cada push, PR y merge.

## Fase 0 · Consigna y fechas (chico)

- Transcribir la consigna a `docs/entregas/consigna-entrega-4.md`, como se hizo con la de la Entrega 3.
- Corregir las fechas (11/11 y 13/11; expo 25/11) y "qué pide la Entrega 4" en
  `skills/entregas-integrador/SKILL.md`. El kit de arranque queda como se transcribió.
- Crear `docs/entregas/devolucion-entrega-3.md` como esqueleto. Se completa después del
  28/10, porque la consigna pide traer resuelto "lo que te marcamos en la Entrega 3"
  (minutos 0–2).

## Fase 1 · Que los notebooks exporten sus números (sin recalcular)

Para que la app coincida con los notebooks, los números salen de ellos, no se reescriben a mano.

- **`notebooks/04_modelado.ipynb`:** una celda final que guarda en
  `models/reporte_modelado.json` (no versionado, como el resto de `models/`) lo que ya
  está en memoria:
  - la tabla de comparación con media ± desvío (§3) y la diferencia pareada;
  - la grilla (§5) y el resultado del balanceo (§6);
  - la tabla de columnas por grupo (§7) y la variante D;
  - test global y por corte, para "todas" y para "llegan al 60" (§8);
  - la confusión y dónde se equivoca;
  - la importancia por permutación (§8) y la duración (§10).
- **`notebooks/02_eda_hipotesis.ipynb`:** una celda final que guarda
  `data/processed/reporte_eda.json` con el resumen de hipótesis (§9.3 y §10.7) y el η² por
  corte de material y reloj (H1′ y H2′).
- **Embudo de limpieza para «Los datos»:** ver si `src/clean_data.py` ya cuenta cada
  paso (duplicados entre usuarios, partidas de menos de 5 plies). Si no, agregar
  `pasos_limpieza` a `data_summary.json` en `src/pipeline.py` (`build_summary`).
- Hace falta volver a correr el DAG, el 02 y el 04 (37 min). **Lo corre una persona del grupo**
  (el DAG no se dispara ni se actualizan números sin él).

## Fase 2 · Script de construcción y gráficos Altair

- **`src/app_charts.py`:** una función por gráfico, que devuelve un `alt.Chart`. La
  **paleta y los órdenes** se definen una sola vez: `RESULT_ORDER` con sus colores,
  bandas de ELO y ritmos. Son los mismos tokens que las bandas de `web/components/Curva.module.css`.
- **`src/build_app.py`**, que se corre con `python -m src.build_app`:
  1. Lee `data/processed/*.parquet`, `data_summary.json`, los dos reportes y
     `models/modelo_en_vivo.joblib` (con `cargar_modelo` de `src/predict.py`).
  2. Arma el test con `artifact["entrenado_hasta"]`, el mismo corte temporal del 04.
     Predice con el Pipeline guardado sobre una **muestra estratificada de partidas de
     test** (unas 2.000, por banda y ritmo, `random_state` de `config.yaml`), con los
     mismos historiales que usa el 04 (`attach_player_histories`).
  3. Verifica que el test global de la muestra completa coincida con el reporte del 04
     (0,795 frente a 0,936) dentro de una tolerancia, o falla.
  4. Escribe, **versionados**, `web/public/graficos/<seccion>.json` (specs de Vega-Lite,
     `chart.to_dict()`) y `web/public/datos/explora.json`. Son agregados y una muestra, no
     `data/`, y tienen que viajar al deploy. Se documenta como excepción y se controla el tamaño.
- **Gráficos y títulos que afirman** (las cifras se recalculan en el build; el texto
  final se cierra en grupo):
  - **Portada:** una oración del estilo "Antes de mover, el resultado apenas se adivina
    mejor que el piso; con el material y los relojes, cada jugada lo vuelve más
    predecible". Tres números: 100.396 partidas, 5,2 % de mejora antes de mover y 19,6 % al ply 60.
  - **Los datos:** cuántas partidas siguen vivas en cada corte, por ritmo (la unidad
    partida × corte). «Cómo lo sabemos»: DAG y fecha de corrida (22/10), qué es una fila,
    el embudo paso a paso y las columnas descartadas por fuga (el rating posterior).
  - **Lo que encontramos:** η² del material y del reloj por corte (H1′ y H2′).
    «Cómo lo sabemos»: una hipótesis que se sostuvo y una que no, cada una con su número,
    y cómo se calcula el η².
  - **El modelo:** log-loss por corte, modelo contra piso, en test. «Cómo lo sabemos»:
    - por qué log-loss, el piso y la validación temporal en 5 folds por partida;
    - la tabla con media ± desvío, la grilla y el test;
    - dónde se equivoca (empate al 3,8 %) y la importancia por permutación;
    - el rating de los rivales como corrección.
  - **Explorá:** dispersión de partidas de test en un corte: x = balance de material,
    y = P(gana el bando con ventaja), color = resultado real. Controles de Altair:
    `alt.binding_range` para el corte y `alt.binding_select` para el ritmo y la banda.
    Tooltip con jugadores, ritmo, ratings, resultado y las tres probabilidades del modelo.

## Fase 3 · Web (Next.js)

- **`web/components/GraficoAltair.tsx`:** carga una spec y la dibuja con `vega-embed`
  (sumar `vega`, `vega-lite` y `vega-embed` a `web/package.json` con versión exacta). Los
  colores salen de la spec, no del CSS.
- **`web/components/ComoLoSabemos.tsx`:** un `<details>` cerrado por defecto.
- **`web/app/page.tsx`:** portada (oración y tres números), y debajo el tallo en
  orden con las tres secciones. Se reusa el estilo de `page.module.css` y `DemoEnVivo`
  puede quedar como cierre.
- **`web/app/explora/page.tsx`:** el gráfico de Explorá. Al hacer clic en un punto
  (listener de señal de vega) se abre `/analizar?usuario=…&partida=…` con la curva
  completa de esa partida: es el detalle a pedido, con el modelo.
- **Probá el modelo** = `/jugar` y `/analizar`, que ya existen. Sólo se renombran en
  `web/components/Navegacion.tsx`: Explorá · Probá el modelo (jugar / analizar).

## Fase 4 · Pruebas

- **`tests/test_build_app.py`** (sin red; se saltea si faltan datos o artefacto, como
  `tests/test_model_realism.py`):
  - las specs se serializan y declaran sus params/bindings;
  - Explorá trae las probabilidades del modelo y suman 1;
  - los números de la portada coinciden con los reportes;
  - la paleta es la misma en todas las specs;
  - los JSON de `web/public` quedan bajo un tamaño máximo.
- `python -m unittest discover -s tests`; `cd web && npm run typecheck && npm run build`.
- Recorrer la app local entera: portada → tallo → Explorá (los controles cambian el
  gráfico y el clic abre la partida) → Probá (caso fuera de rango → aviso).

## Fase 5 · Publicación gratis (decisión pendiente; probarla temprano)

Opción recomendada, para validar con una prueba de deploy en la semana del 29/10:

- **API en Hugging Face Spaces (Docker, gratis, 16 GB de RAM).** El random forest pesa
  132 MB comprimido y ocupa ~1 GB de RAM al cargar. Render y Koyeb gratis dan 512 MB, no
  alcanza. Habría que agregar `Dockerfile` con
  `uvicorn api.main:app` y el modelo subido al Space o a un Release; CORS por variable de
  entorno en `api/main.py`. Se duerme tras 48 h sin uso: abrirla antes de entrar.
- **Web en Vercel (gratis)**, con `NEXT_PUBLIC_API_URL` apuntando al Space.
- Si el docente no acepta Next + FastAPI, el contenido (specs de Altair y JSON) sirve
  igual para Streamlit, que dibuja las mismas specs con `st.altair_chart`.

## Fase 6 · Documentación y defensa

- README: cómo se regenera la app (DAG → 02/04 → `python -m src.build_app` → deploy) y
  la URL. Actualizar la estructura en `AGENTS.md` y el estado en la skill.
- `docs/entregas/guia-defensa-entrega-4.md`:
  - cada gráfico componente por componente (datos, mapeo, marca, transformación, escala);
  - qué control toca qué componente;
  - una decisión de diseño que cambió;
  - cómo llega el modelo a la app y qué pasa con un caso raro.

## Verificación

1. Alguien del grupo corre el DAG, el 02 y el 04. Después: `python -m src.build_app`, que termina
   sin fallar la comparación con el reporte.
2. `python -m unittest discover -s tests` y `npm run typecheck && npm run build`.
3. Local: `uvicorn api.main:app` + `npm run dev`, recorrido completo (Fase 4).
4. Deploy: abrir la URL pública desde otra computadora o el celular, probar Explorá y
   un caso de Probá.
