---
name: git-workflow
description: Convención de ramas, mensajes de commit y Pull Requests de este repo. Usar SIEMPRE antes de hacer git commit, git checkout -b, git push o abrir un PR; también cuando haya que resolver conflictos en notebooks .ipynb o decidir qué archivos entran al commit. Triggers - commit, rama, branch, PR, pull request, mergear, subir cambios.
---

# Flujo de trabajo con Git

Proyecto grupal (5-6 personas) sobre un repo compartido. Las reglas de acá existen
para que el historial siga siendo legible con varias personas trabajando en paralelo
y para que en cada entrega se pueda mostrar qué hizo cada uno.

## Regla 1 — Nunca commitear directo a `main`

`main` solo recibe cambios por merge de un PR. Todo trabajo arranca con una rama nueva
sacada de `main` actualizado:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/nombre-corto
```

Si ya empezaste a trabajar sobre `main` sin querer, no pierdas los cambios:

```bash
git checkout -b feat/nombre-corto   # se lleva los cambios sin commitear a la rama nueva
```

## Regla 2 — Nombre de rama: `<tipo>/<slug>`

El slug va en kebab-case, en español, y describe **el cambio**, no el archivo tocado.

| Tipo | Cuándo | Ejemplo |
|---|---|---|
| `feat/` | funcionalidad o análisis nuevo | `feat/eda-distribucion-lesiones` |
| `fix/` | corregir algo que está mal | `fix/fan-out-merge-mapping` |
| `docs/` | README, informes, documentación | `docs/readme-instrucciones-corrida` |
| `chore/` | dependencias, estructura, config | `chore/pin-pandas-3` |
| `exp/` | prueba exploratoria que puede no quedar | `exp/xgboost-vs-randomforest` |

Nombres a evitar: `feat/cambios`, `feat/tute`, `feat/notebook`, `feat/entrega`.
No dicen qué se hizo.

## Regla 3 — Mensajes de commit

Formato:

```
<tipo>(<alcance>): <resumen en imperativo, minúscula, sin punto final>

<cuerpo opcional: qué cambió y POR QUÉ; el cómo ya está en el diff>
```

Alcances de este proyecto: `pipeline`, `eda`, `modelado`, `viz`, `app`, `datos`,
`docs`, `skills`, o `entrega-N` cuando el commit cierra una entrega completa.

Ejemplos buenos:

```
feat(pipeline): filtrar el panel en streaming por chunks

El panel de Zenodo pesa ~515 MB y no entra en memoria. Se procesa con
read_csv(chunksize=200_000) y se escribe incremental, quedándonos solo con
los jugadores que tienen al menos una lesión registrada.
```

```
fix(pipeline): conservar el fbref_player_id del panel en el merge

El mapping tiene una fila por (jugador, temporada). Mergear su fbref_player_id
pisaba el valor correcto por temporada del panel con el de la última.
```

Ejemplos malos: `cambios`, `update notebook`, `arreglos varios`, `wip`, `asd`.

Reglas:
- Resumen ≤ 72 caracteres, en imperativo ("agregar", no "agregué" ni "agregado").
- Un commit = un cambio con sentido propio. Si el resumen necesita un "y", probablemente son dos commits.
- El cuerpo se escribe cuando la decisión no es obvia leyendo el diff (por qué ese
  umbral, por qué se descartó la otra opción, qué limitación de los datos motivó el cambio).
- Los commits hechos por un agente terminan con el trailer de atribución que use esa
  herramienta, en una línea aparte al final del mensaje.

## Regla 4 — Qué NO entra en un commit

- **Nada de `data/`.** Los datos se regeneran corriendo el pipeline; están ignorados
  en `.gitignore` a propósito. Un CSV de 515 MB en el historial no se saca nunca más.
- Credenciales, tokens, rutas absolutas de tu máquina.
- Archivos de estado local del agente (`.claude/settings.local.json`, `.opencode/state/`).
- Cambios de formato masivos mezclados con cambios de fondo: van en su propio commit.

Antes de commitear, mirar qué se está por incluir:

```bash
git status --short
git diff --stat --cached
```

## Regla 5 — Notebooks en git

Los `.ipynb` de este repo **se commitean con sus outputs guardados**: los outputs son
la evidencia de que el pipeline corrió, y el docente los mira en la entrega.

Consecuencias prácticas:

- Antes de commitear un notebook, correrlo con **Restart & Run All** para que los
  outputs correspondan al código actual. Un notebook con outputs viejos miente.
- **Un conflicto en un `.ipynb` no se resuelve editando el JSON a mano.** Se elige una
  versión entera y se vuelve a correr:

  ```bash
  git checkout --theirs notebooks/01_pipeline_ingesta.ipynb   # o --ours
  # abrir, Restart & Run All, guardar
  git add notebooks/01_pipeline_ingesta.ipynb
  ```

- Para evitar conflictos: que dos personas no editen el mismo notebook en paralelo.
  Si hace falta, dividir en notebooks numerados distintos.

## Regla 6 — Pull Requests

Un PR por rama, contra `main`. Título = el resumen del commit principal, mismo formato.

Plantilla del cuerpo:

```markdown
## Qué hace
Dos o tres líneas sobre el cambio, en criollo.

## Por qué
Qué problema resuelve o qué parte de la entrega cubre.

## Cómo probarlo
Pasos concretos para verificarlo (qué notebook correr, qué celda mirar,
qué número tiene que dar).

## Entrega relacionada
Entrega N — <nombre> (fecha)

## Checklist
- [ ] El notebook corre de punta a punta con Restart & Run All
- [ ] No se agregó nada de `data/` al commit
- [ ] Los asserts de integridad (anti fan-out, huérfanos) pasan
- [ ] `requirements.txt` actualizado si se agregó una dependencia
```

Antes de pedir review:

```bash
git fetch origin
git rebase origin/main    # resolver conflictos acá, no en el PR
```

**La evaluación del integrador es individual**: en la entrega el docente le pregunta a
integrantes puntuales sobre cualquier parte. El PR es la herramienta para que el resto
del grupo entienda lo que hiciste — describilo como si lo fuera a leer alguien que no
estuvo cuando lo escribiste.

## Regla 7 — Push y operaciones que salen del repo local

`git push`, abrir un PR y mergear afectan el trabajo de otras personas. Un agente **pide
confirmación explícita antes de cada una de esas tres**, aunque ya haya commiteado.

Prohibido siempre: `push --force` sobre `main`, `git reset --hard` sobre trabajo de otro,
reescribir historia ya pusheada y compartida.
