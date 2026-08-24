# AGENTS.md

Instrucciones para agentes de código que trabajen en este repo.
Este archivo lo leen **Codex** y **OpenCode**; Claude Code entra por `CLAUDE.md`.

## El proyecto

Proyecto Integrador de Ciencia de Datos (UTN FRM 2026): qué combinación de ELO,
apertura, modalidad de ritmo y color de piezas predice el **resultado** y la
**duración** de una partida de ajedrez online real (PubAPI pública de Chess.com). Trabajo
grupal de 5-6 personas, con cuatro entregas parciales entre septiembre y noviembre de
2026. Leé el README — tiene contexto largo sobre por qué el tema cambió dos veces
antes de llegar a este, y qué falta validar con datos reales de volumen.

```
src/         módulos del pipeline (descarga, parseo de PGN, features) reusados por el notebook
notebooks/   pipeline narrado y verificación, numerados por entrega
config/      config.yaml — usuarios de Chess.com, bandas de ELO, parámetros de descarga
data/        vacío en git — se regenera corriendo el pipeline
skills/      instrucciones reutilizables para agentes (leer más abajo)
```

Stack: Python 3.11+, pandas, requests, pyarrow, matplotlib, rich, Jupyter. Ver
`requirements.txt`.

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
- **Nunca commitear archivos de `data/`.** Se regeneran corriendo el pipeline contra la PubAPI de Chess.com.
- **Pedir confirmación antes de `git push`, de abrir un PR y de mergear.** El repo es
  compartido con el resto del grupo.
- Narrativa de notebooks en markdown **en español**; comentarios de código **en inglés**.
- Todo notebook tiene que correr con **Restart & Run All** desde un kernel limpio.
- Cada `merge` de dataframes va seguido de su `assert` anti fan-out.
- Las anomalías en los datos se investigan y se explican por escrito, no se silencian.

## Correr el pipeline

```bash
pip install -r requirements.txt
jupyter lab notebooks/01_data_ingestion_verification.ipynb   # Restart & Run All
# o, por consola:
python -m src.pipeline
```

La primera corrida descarga hasta 1.000 partidas rated de 8 usuarios de Chess.com,
recorriendo archivos mensuales en serie. Las siguientes saltean los JSON ya descargados.
