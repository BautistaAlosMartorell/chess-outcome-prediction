# Skills del proyecto

Instrucciones reutilizables para agentes de código (Claude Code, Codex, OpenCode).
Cada subcarpeta es una skill en formato [Agent Skills](https://code.claude.com/docs/en/skills):
un `SKILL.md` con frontmatter YAML (`name`, `description`) y el contenido en Markdown.

| Skill | Cuándo aplica |
|---|---|
| [`git-workflow`](git-workflow/SKILL.md) | Antes de commitear, crear una rama, pushear o abrir un PR |
| [`pipeline-datos`](pipeline-datos/SKILL.md) | Al escribir o modificar notebooks, mergear dataframes o tocar `data/` |
| [`entregas-integrador`](entregas-integrador/SKILL.md) | Al planificar trabajo, priorizar o validar una fuente de datos |

## Cómo las lee cada herramienta

Esta carpeta es la **única fuente de verdad**. Los demás caminos apuntan acá.

| Herramienta | Cómo llega |
|---|---|
| **Claude Code** | `.claude/skills/<nombre>` → symlink a `skills/<nombre>`; las carga solas cuando la `description` matchea |
| **Codex** | Lee `AGENTS.md` en la raíz, que indexa las skills y le dice cuándo abrir cada `SKILL.md` |
| **OpenCode** | Lee `AGENTS.md` igual que Codex; además `.opencode/skills/<nombre>` → symlink, para las versiones que soportan skills nativas |

Los symlinks están versionados en git, así que funcionan al clonar (en Windows hace falta
`git config --global core.symlinks true`).

## Agregar una skill

1. `mkdir skills/<nombre>` y escribir el `SKILL.md` con su frontmatter.
2. En la `description`, decir **cuándo** usarla, no solo qué hace: es lo único que el
   agente ve antes de decidir si abrirla. Incluir palabras que el usuario realmente
   tipearía.
3. Crear los symlinks:
   ```bash
   ln -s ../../skills/<nombre> .claude/skills/<nombre>
   ln -s ../../skills/<nombre> .opencode/skills/<nombre>
   ```
4. Agregarla a la tabla de acá arriba y a la de `AGENTS.md`.
