# Cierre de integración de la app · 23/10/2026

Rama: `feat/completar-app-entrega-4`. Se prepara una PR contra `main` con los
notebooks ejecutados, la interfaz existente, sus artefactos y las verificaciones.
La publicación se difiere por pedido explícito del usuario.

## Recuperación de la interfaz

La PR #35 se tituló «app de la Entrega 4 con portada, tallo, Explorá y trivia», pero
su head mergeado fue `4085249`: sólo contenía la consigna, los contadores de limpieza
y el script de gráficos. Los cinco commits siguientes seguían en la rama local
`feat/trivia-resumen-visual`:

- `9f30be2`: proyecto y Explorá.
- `c2e2369`: trivia y resumen animado de partidas.
- `a38bc9a`: tema claro y bienvenida «¿Vos cómo la ves?».
- `ed7c143`: gráficos y banco de trivia generados.
- `bff8486`: instrucciones de construcción y guía de defensa.

Se integraron mediante cherry-pick conservando su autoría. La rama original queda
intacta. Se descartó la reconstrucción alternativa iniciada desde el `main` que no
contenía esa interfaz: no forma parte de esta PR. Se conservan el diseño, los colores,
la distribución y las rutas `/proyecto`, `/explora`, `/trivia`, `/analizar` y `/jugar`.

## Datos y modelo

El [registro de regeneración](regeneracion-entrega-4-2026-10-23.md) documenta el DAG y
los notebooks 02/04 desde kernel limpio. El 04 tardó 54,5 minutos y reprodujo las
métricas y decisiones anteriores dentro de `1e-9`, sin contar los tiempos de ajuste.

Se volvió a construir la app con el código recuperado: resumen, cuatro gráficos,
2.000 partidas de Explorá y 60 casos de trivia, con posiciones y curvas completas.
La construcción reconstruye el test y exige paridad con el notebook 04. Los JSON
se versionan bajo `web/public/app/`; los Parquet, crudos y modelos siguen fuera de Git.

## Correcciones y preparación de despliegue

- Explorá desbordaba en móvil porque el texto de ayuda se dibujaba en una coordenada
  fija para 640 px. Ahora se centra con el ancho real y usa dos líneas. El título
  de la partida seleccionada también limita su ancho; el tooltip conserva su detalle.
- La trivia presenta los controles de tiempo menores de un minuto en segundos, sin
  fracciones extensas como `0.16666666666666666 min`.
- El error de conexión al modelo explica la indisponibilidad y el posible arranque
  del servicio, sin mostrar comandos internos al visitante.
- `CORS_ORIGINS` configura los orígenes de producción; se probaron preflights de
  orígenes autorizados y no autorizados.
- `deploy/api.Dockerfile` y las dependencias de inferencia permiten servir el mismo
  artefacto en un contenedor. El paquete de `deploy/prepare_space.py` incluye sólo
  los archivos necesarios y el modelo; no incluye `.env`, datos ni modelos de experimentos.
- Las instrucciones de Vercel y Hugging Face están en `deploy/README.md`. No se creó
  ningún servicio público, Space ni despliegue remoto.

## Verificaciones

- Python: 122 tests, 121 aprobados y uno con los dos fallos conocidos de dama ganada
  (+11,58/+6,29 puntos frente a +15). No se modificó el contrato ni el modelo para
  hacer pasar esos ejemplos.
- Web: cuatro tests de experiencias, comprobación de tipos y compilación de producción
  con todas las rutas.
- Docker: imagen construida, healthcheck sano, `/salud` con 40 columnas y predicción
  de cuatro posiciones con probabilidades normalizadas.
- Paquete del Space: exportación real comprobada, sin datos ni archivos `.env`.
- Navegador: bienvenida recuperada, ronda completa de tres posiciones de trivia,
  elección → pronóstico → resultado → marcador. La trivia no desborda a 390 px.
- Explorá: control de ritmo, nivel y plies; comprobación de ancho móvil tras corregir
  el texto de ayuda (390 px de viewport y 390 px de documento).
- Después de la corrección, los diez tests específicos del build vuelven a pasar.
  La compilación de producción se repitió sobre los JSON y el código finales.

## Límites que se conservan

La URL pública se difiere por decisión del usuario. Aún debe confirmarse con el
docente la forma Next.js + FastAPI y completarse la devolución de Entrega 3 después
del 28/10. El contrato de dama ganada sigue incumplido. El período de test ya se
había observado; no se lo presenta como una evaluación ciega nueva.
