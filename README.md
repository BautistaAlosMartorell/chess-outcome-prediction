# Proyecto Integrador — Ciencia de Datos (UTN FRM 2026)

Repositorio **contenedor de proyectos candidatos**. Cada idea de proyecto vive en su propia
carpeta; más adelante nos quedamos con una sola para la entrega final.

## Estructura

```
.
├── ideas_proyecto.md          # relevamiento de ideas de dataset candidatas
├── f1-tyre-degradation/       # PROYECTO: degradación de neumáticos en F1 ("the cliff")
└── <otra-idea>/               # (futuras ideas van cada una en su carpeta)
```

## Proyectos

| Carpeta | Tema | Estado |
|---|---|---|
| [`f1-tyre-degradation/`](./f1-tyre-degradation/) | Degradación de neumáticos en F1 ("the cliff") con FastF1 | En desarrollo (Entrega 0 lista) |

Ver [`ideas_proyecto.md`](./ideas_proyecto.md) para el resto de ideas relevadas.

## Cómo agregar una idea nueva

1. Crear una carpeta con el nombre del proyecto.
2. Adentro: su propio `README.md`, `requirements.txt`, notebooks y `data/` (los datos se
   regeneran con el pipeline, no se versionan).

## Convención

- Cada proyecto es autocontenido (sus dependencias, sus datos, su pipeline).
- Los datasets generados **no se suben** al repo: se regeneran corriendo el pipeline de cada proyecto.
