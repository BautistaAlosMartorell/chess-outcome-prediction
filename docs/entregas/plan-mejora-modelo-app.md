# Plan de mejora del modelo final de la app

Estado al 22/10/2026. Documento de traspaso para continuar en otra sesión o con otro modelo.
**Este documento propone trabajo; todavía no se reentrenó ni reemplazó el modelo.**

**Avance posterior:** ya se preservó el artefacto, se fijó el protocolo y se ejecutaron
un piloto de cobertura sin red y referencias iniciales de diagnóstico. Leer primero
el [punto de continuación y resultados](../auditorias/avance-mejora-modelo-app-2026-10-22.md).
El modelo de producción sigue intacto; las referencias no son artefactos de la app.

## Objetivo y alcance

Mejorar las probabilidades de resultado que muestra la app antes de empezar y durante
la partida, especialmente la respuesta a la diferencia de nivel entre jugadores.
Conservar la reconstrucción temporal del historial y verificar la misma entrada en
entrenamiento y API. La duración restante es secundaria: medirla y evitar regresiones,
sin convertir su ajuste en requisito previo para resolver las probabilidades.

No corregir porcentajes a mano, no introducir reglas para Hikaru y no confundir
puntuación esperada (`P(victoria) + 0,5 P(tablas)`) con probabilidad de ganar.

## Leer antes de continuar

1. `AGENTS.md`, `README.md` y las skills `skills/pipeline-datos/SKILL.md`,
   `skills/entregas-integrador/SKILL.md` y `skills/git-workflow/SKILL.md`.
2. [Auditoría y evidencia](../auditorias/modelo-app-2026-10-22.md).
3. [Estado de Entrega 3 y validación previa](plan-entrega-3.md).
4. `src/predict.py`, `src/history_transformer.py`, `src/rating_history.py`,
   `src/model_validation.py`, `api/chesscom.py`, `api/main.py` y notebook 04.

No es necesario repetir la auditoría para empezar a diseñar la corrección. Repetirla
si cambiaron el artefacto o los datos, o para evaluar el candidato final.

## Estado que recibe la próxima sesión

- Rama observada: `feat/actualizar-modelado-120-cuentas`. Revisar `git status` antes de
  editar: puede haber trabajo nuevo del usuario. No cambiar ni descartar cambios ajenos.
- Se agregaron, sin commit, `src/audit_predictions.py`, `api/audit_predictions.py`,
  `docs/auditorias/modelo-app-2026-10-22.md` y este plan. No hubo push ni PR.
- Artefacto local: `models/modelo_en_vivo.joblib`, random forest, 40 columnas,
  entrenado hasta `2026-07-04T01:29:25+00:00`, rango declarado 100–3403.
  SHA-256: `25051ff7bd92a11b8911c69ee0fbf0152a780b84ddf5b688e895a31d45cebe8d`.
- El pipeline oficial y la lista congelada de 120 cuentas permanecen intactos.
- El servidor de la app observado corre desde otro worktree temporal, no desde este
  directorio. Su código relevante coincidía y su modelo era un enlace al artefacto de
  este repo. No asumir que editar acá recarga ese proceso; verificar cwd/configuración
  al integrar. No depender de que ese worktree siga existiendo en otra sesión.

Hallazgos comprobados:

- Sólo **185/80.314 partidas de train (0,23 %)** tienen ambos ratings previos; en el
  período posterior son **85/20.080**. La app intenta consultar ambos historiales.
  Hay una diferencia de distribución de entradas y evidencia insuficiente para validar
  diferencias de ELO por banda. Ampliar cuentas élite no resuelve por sí solo esto.
- La app transmite las probabilidades del modelo correctamente. Casos confirmados en
  el servidor: 733 contra 1358 recibe 44,89 % de victoria de blancas; 108 contra 2686,
  34,41 %. La auditoría también muestra 2044 contra 2744 con 45,02 %.
- En controles iniciales de igual ritmo/posición, pasar de −200 a +200 de diferencia
  de rating reduce la probabilidad de blancas para medias de 2000, 2800 y 3200.
  Ocurre dentro del rango del modelo, no sólo con Hikaru fuera del máximo.
- Un minuto adicional de pausa de blancas cambia más de cinco puntos la predicción
  en 6,40 % de los casos disponibles. No prueba que quitar pausas mejore el modelo.
- Los promedios por nivel son razonables, pero no validan los enfrentamientos entre
  niveles. Buena calibración agregada puede ocultar errores que se compensan.
- Suite ejecutada: 86 pruebas; una falla en dos subcasos ya conocidos, por sensibilidad
  insuficiente a ganar una dama (+9,02/+10,34 puntos, contrato >15). No bajar el umbral.

## Secuencia de implementación

### 1. Congelar la comparación antes de buscar un modelo mejor

- Preservar una copia local del artefacto actual y su hash; no versionar modelos/datos.
- Registrar hashes de datos, semilla, versiones y particiones. Mantener la evaluación
  histórica para comparar versiones, declarándola exploratoria y ya observada.
- Definir una evaluación temporal nueva antes de seleccionar candidatos. Las partidas
  de esta auditoría y las ya inspeccionadas no son un holdout nuevo. Si se usan meses
  posteriores, inventariar y excluir de la evaluación ciega los casos ya examinados.
- Elegir por CV temporal por partida. Exigir separación de partidas y disponibilidad
  de train al inicio de validación; excluir partidas que cruzan los límites temporales.
- Congelar tablas de resultados por ritmo, nivel, brecha de rating, cobertura de uno/dos
  historiales y ply. Comparar los mismos juegos al medir avance entre cortes.

Entregable: protocolo breve, particiones reproducibles y métricas del artefacto vigente
en esas mismas particiones. No seleccionar cambios por su desempeño en el test final.

### 2. Corregir cobertura y comparabilidad del historial

Esta etapa precede a una búsqueda amplia de hiperparámetros.

- Medir primero, sin red, cuánto aumentaría la cobertura al usar apariciones previas de
  los rivales en los JSON existentes. Deduplicar por cuenta/partida. Son observaciones
  parciales: no tratarlas como las últimas diez partidas completas de esa cuenta.
- Diseñar un enriquecimiento **acotado a un salto de rivales** de las partidas objetivo.
  Consultar archivos mensuales anteriores a sus inicios, con presupuesto configurable
  de cuentas, meses y solicitudes. No descargar recursivamente rivales de rivales.
- Hacer un piloto estratificado por seis niveles, tres ritmos donde existan y brechas
  absolutas 0–100, 100–200, 200–400 y ≥400. Verificar costo y cobertura antes de ampliar.
  Procurar al menos 100 partidas con dos ratings en cada celda principal disponible;
  es un mínimo operativo de diagnóstico, no garantía estadística. Informar celdas vacías.
- Usar caché idempotente, requests en serie, User-Agent, reintentos y escritura atómica.
  Guardar el enriquecimiento separado de la muestra oficial. No borrar ni regenerar
  `config/jugadores_seleccionados.yaml`; no cambiar en silencio `download.until_month`.
- Para cada cuenta, usar sólo cierres estrictamente anteriores al inicio, del mismo
  ritmo para rating/forma. Nunca rellenar con WhiteElo/BlackElo del juego objetivo.
- Distinguir rating ausente, historial parcial, ventana de diez resultados suficiente
  y pausa desconocida. Una ausencia en un historial truncado no demuestra inactividad.
- Unificar la política de ventana/contexto entre entrenamiento y `api/chesscom.py`.
  La app consulta hasta tres archivos activos recientes: para partidas antiguas puede
  no obtener observaciones anteriores al inicio. Elegir consulta por fecha del objetivo
  o declarar el contexto faltante; evitar una pausa ficticia por ventana incompleta.
- Revisar `partidas_sesion`: truncar el historial también trunca el conteo de la sesión.

Archivos probables: módulo nuevo de enriquecimiento, configuración separada,
`src/rating_history.py`, `src/history_transformer.py`, `api/chesscom.py` y tests.
Mantener observaciones crudas separadas de features derivadas por el Pipeline.

Entregable: cobertura antes/después por banda/ritmo/brecha, procedencia y fallos
documentados. Si la cobertura sigue siendo insuficiente, reportarlo; no afirmar que
el modelo quedó validado para ese uso ni pasar directamente a una grilla grande.

### 3. Comparar candidatos pequeños y explicables

Hacer las transformaciones de features dentro del Pipeline y compartirlas con la app.

1. Referencia de tres resultados basada en diferencia y nivel medio de rating, color y
   ritmo. Una logística multinomial es un primer candidato; aprender tablas explícitamente.
2. Modelo actual reentrenado con datos enriquecidos, sin otros cambios: aislar el aporte
   de la cobertura de datos antes de atribuir mejoras a nuevas features.
3. Añadir diferencia de ELO, promedio y banderas de disponibilidad. Calcular diferencia
   sólo si se conocen ambos; no restar dos imputaciones y presentarlas como observadas.
4. Comparar forma mínima (resultados recientes) contra forma completa; luego pausas y
   sesión como grupo separado. Reentrenar cada variante en los mismos folds. La prueba
   previa de hacer columnas faltantes no sustituye esta ablación.
5. Probar acotar/transformar pausas y marcar cobertura incompleta sólo si el diagnóstico
   lo justifica. Suprimirlas si no aportan mejora robusta fuera de muestra.

Priorizar una sola ruta de predicción que sirva antes y durante. Si un modelo inicial
separado mejora claramente, evaluar una arquitectura que incorpore contexto inicial y
features en vivo sin un salto artificial en el primer ply. No introducir una mezcla de
probabilidades o pesos arbitrarios sólo para corregir los ejemplos de esta auditoría.

Archivos probables: transformador compartido, `src/predict.py`, notebook 04 y tests.
Preservar nombres/orden de clases y contrato de `predecir`. La calibración, si se prueba,
se ajusta en particiones temporales de entrenamiento, nunca sobre el test final.

### 4. Validar comportamiento y calidad probabilística

- Métrica principal: log-loss pareada contra la versión anterior en los mismos juegos
  y cortes. Complementar con Brier y calibración por clase y brecha; mostrar n por celda.
- Reportar variación entre folds y, donde se estimen intervalos, considerar repetición
  de cuentas y dependencia temporal. No declarar significancia por 21 ejemplos elegidos.
- Control inicial con rating medio fijo, diferencias −800/−400/−200/0/+200/+400/+800,
  ambos colores y ritmos. Mantener ratings individuales dentro de rangos soportados.
  Exigir orden coherente en una referencia sin forma; registrar inversiones del candidato.
- Controlar que no se apruebe una respuesta casi plana por ser apenas monótona: contrastar
  magnitud con tasas observadas y con la referencia, sin imponer porcentajes inventados.
- Separar controles con forma faltante de contextos completos reales. Variar pausas sin
  cruzar el límite de sesión, o recalcular sesión de forma coherente si se cruza.
- Mantener casos de prueba de datos futuros, simultáneos, solapados, rating posterior,
  duplicados, historial parcial y paridad entrenamiento/API. Cada merge lleva assert.
- Preservar el contrato de dama ganada. Verificar relojes, posiciones iniciales y que
  el ganador real recibe mayor probabilidad cerca del final **en promedio**.
- Medir duración con MAE/sesgo por corte/nivel/ritmo y población comparable. No presentar
  una disminución del error sobre otra población como mejora dentro de una partida.

Criterio para promover: mejora de log-loss reproducible en CV, sin deterioro sistemático
de la predicción inicial ni en vivo; respuesta de ELO coherente y respaldada por grupos
con cobertura suficiente; calibración sin deterioros materiales por subgrupo. Fijar las
tolerancias numéricas antes de inspeccionar el nuevo test. Si hay un intercambio entre
métricas, documentar el costo y no promover automáticamente.

### 5. Integrar y cerrar

- Ejecutar notebook 04 con Restart & Run All; guardar outputs en español y metadata del
  artefacto: versión de features, rango, cobertura, fecha, datos y métricas.
- Hacer que la API valide compatibilidad del artefacto y exponga metadata pertinente.
  Revisar el aviso de rango de la interfaz: el rango individual no detecta brechas o
  combinaciones no representadas. Comunicar falta de contexto cuando ayude al usuario.
- Repetir auditoría poblacional, muestra de app y controles de comportamiento, usando
  snapshots para reproducir. Conservar los casos auditados como regresiones, no como test
  ciego. Verificar el servidor que usa realmente el navegador y su modelo cargado.
- Correr la suite completa; documentar cualquier fallo restante. Actualizar README,
  mapa de Entrega 3 e informe de auditoría. No declarar corregido lo que no se verificó.
- Mantener una copia local anterior para volver atrás. No versionar datos/modelos.
  Pedir confirmación antes de push, PR y merge, según las reglas del repo.

## Orden recomendado si queda poco tiempo

Primero cobertura y piloto; después referencia simple y diferencia de rating; luego
ablación de pausas; finalmente reentrenamiento completo e integración. Evitar una grilla
grande, motores de ajedrez o nuevas features de posición antes de resolver las entradas.
Si sólo alcanza para el diagnóstico/piloto, dejar números y limitaciones, sin publicar
una supuesta corrección ni reemplazar el artefacto por una regla improvisada.

## Artefactos locales y comandos ya disponibles

Los archivos de `/tmp` pueden desaparecer entre sesiones; el informe versionable
conserva los hallazgos. Los scripts permiten regenerar lo necesario:

```bash
.venv/bin/python -m src.audit_predictions --output /tmp/auditoria-probabilidades.json
.venv/bin/python -m api.audit_predictions --snapshot /tmp/auditoria-app-fuentes.json --output /tmp/auditoria-app.json
.venv/bin/python -m api.audit_predictions --active-accounts --snapshot /tmp/auditoria-app-activos-fuentes.json --output /tmp/auditoria-app-activos.json
.venv/bin/python -m unittest discover -s tests
```

Si existen snapshots, la auditoría de la app los reproduce sin red; si no, consulta
Chess.com y puede obtener una muestra diferente. Los JSON incluyen curvas de control,
contextos previos y métricas; los snapshots contienen respuestas públicas originales.
También quedó `/tmp/auditoria-api-servidor.json` con tres verificaciones del servidor.

## Instrucción breve para retomar

> Leé AGENTS.md, las skills aplicables, docs/entregas/plan-mejora-modelo-app.md y
> docs/auditorias/modelo-app-2026-10-22.md y
> docs/auditorias/avance-mejora-modelo-app-2026-10-22.md. Continuá desde las próximas
> acciones del avance, sin repetir el piloto sin red, respetando el estado real de git.
> La auditoría ya confirmó falta de cobertura
> de ambos ratings, probabilidades poco sensibles o invertidas ante diferencias de ELO
> y sensibilidad a pausas. No reentrenes a ciegas ni fuerces porcentajes. Preservá el
> artefacto actual, diseñá una evaluación temporal no contaminada y documentá cada
> etapa. Antes de reemplazar el modelo final, verificá mejoras fuera de muestra y la
> misma ruta de predicción en la app. No hagas push, PR ni merge sin confirmación.
