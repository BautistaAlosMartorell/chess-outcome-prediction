"""Prepara una carpeta para Hugging Face Spaces sin datos crudos ni credenciales.

Uso: python deploy/prepare_space.py --output /tmp/ajedrez-space
No crea un Space ni publica nada. El artefacto debe existir: lo genera el notebook 04.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    model = ROOT / "models/modelo_en_vivo.joblib"
    if not model.is_file():
        parser.error("Falta models/modelo_en_vivo.joblib: ejecutar el notebook 04")
    if target.exists() and any(target.iterdir()):
        parser.error("La carpeta de salida debe estar vacía")
    target.mkdir(parents=True, exist_ok=True)
    for name in ("api", "src"):
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env", ".env.*"))
    for name in ("config", "models"):
        (target / name).mkdir()
    shutil.copy2(ROOT / "config/config.yaml", target / "config/config.yaml")
    shutil.copy2(model, target / "models/modelo_en_vivo.joblib")
    shutil.copy2(ROOT / "deploy/api.Dockerfile", target / "Dockerfile")
    (target / "README.md").write_text(
        "---\ntitle: Ajedrez en vivo API\nemoji: ♞\ncolorFrom: green\ncolorTo: gray\nsdk: docker\napp_port: 7860\n---\n"
        "\nAPI de predicción del proyecto integrador. Configurar CORS_ORIGINS con la URL de la web.\n",
        encoding="utf-8",
    )
    print(f"Space preparado en {target}; no se publicó nada.")


if __name__ == "__main__":
    main()
