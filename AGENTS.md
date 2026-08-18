# AGENTS.md

Instrucciones para agentes de código que trabajen en este repo.
Este archivo lo leen **Codex** y **OpenCode**; Claude Code entra por `CLAUDE.md`.

## El proyecto

Proyecto Integrador de Ciencia de Datos (UTN FRM 2026): predecir el **tipo de lesión** de
jugadores de la Premier League a partir de la **congestión de partidos**. Trabajo grupal
de 5-6 personas, con cuatro entregas parciales entre septiembre y noviembre de 2026.

```
notebooks/   pipelines y análisis, numerados por entrega
data/        vacío en git — se regenera corriendo los notebooks
skills/      instrucciones reutilizables para agentes (leer más abajo)
```

Stack: Python 3.11+, pandas, requests, tqdm, matplotlib, Jupyter. Ver `requirements.txt`.

## Skills

`skills/` contiene las convenciones del repo, una por carpeta. **Abrí y seguí el
`SKILL.md` correspondiente antes de trabajar en algo que caiga en su alcance** — no
trabajes de memoria ni por defecto propio cuando hay una skill que cubre el caso.

| Skill | Leer antes de |
|---|---|
| [`skills/git-workflow/SKILL.md`](skills/git-workflow/SKILL.md) | `git commit`, `git checkout -b`, `git push`, abrir un PR, resolver conflictos en `.ipynb` |
| [`skills/pipeline-datos/SKILL.md`](skills/pipeline-datos/SKILL.md) | crear o modificar notebooks, agregar una fuente, hacer merges de dataframes, tocar `data/` |
| [`skills/entregas-integrador/SKILL.md`](skills/entregas-integrador/SKILL.md) | planificar trabajo, priorizar tareas, evaluar si algo alcanza para una entrega, validar una fuente nueva |

## Reglas que aplican siempre

- **Nunca commitear a `main`.** Rama `<tipo>/<slug>` para todo cambio (`git-workflow`).
- **Nunca commitear archivos de `data/`.** Se regeneran; el panel pesa ~515 MB.
- **Pedir confirmación antes de `git push`, de abrir un PR y de mergear.** El repo es
  compartido con el resto del grupo.
- Narrativa de notebooks en markdown **en español**; comentarios de código **en inglés**.
- Todo notebook tiene que correr con **Restart & Run All** desde un kernel limpio.
- Cada `merge` de dataframes va seguido de su `assert` anti fan-out.
- Las anomalías en los datos se investigan y se explican por escrito, no se silencian.

## Correr el pipeline

```bash
pip install -r requirements.txt
jupyter lab notebooks/01_pipeline_ingesta.ipynb   # Restart & Run All
```

La primera corrida baja ~540 MB desde Zenodo y tarda varios minutos. Las siguientes
saltean los archivos ya descargados.
