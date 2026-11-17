"""Copia os ícones de marcas usados em owlock/core/data/services.json a partir do pacote Simple Icons.

Uso (na raiz do projeto):
    npm pack simple-icons && tar xzf simple-icons-*.tgz        # cria ./package
    python packaging/build_brand_icons.py package

Gera owlock/web/icons/brands/<slug>.svg (desenho branco) e owlock/core/data/brand_icons.json
({slug: {"title", "hex"}}). Os arquivos gerados ficam no repositório: o app não acessa a internet.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "owlock" / "core" / "data" / "services.json"
OUT_SVG = ROOT / "owlock" / "web" / "icons" / "brands"
OUT_JSON = ROOT / "owlock" / "core" / "data" / "brand_icons.json"


def main(package_dir: str) -> None:
    pkg = Path(package_dir)
    data = json.loads((pkg / "data" / "simple-icons.json").read_text(encoding="utf-8"))
    icons = data if isinstance(data, list) else data["icons"]
    by_slug = {i["slug"]: i for i in icons}
    slugs = sorted({s["icon"] for s in json.loads(SERVICES.read_text(encoding="utf-8"))["services"] if s["icon"]})
    OUT_SVG.mkdir(parents=True, exist_ok=True)
    meta = {}
    for slug in slugs:
        svg = (pkg / "icons" / f"{slug}.svg").read_text(encoding="utf-8")
        svg = re.sub(r"<title>.*?</title>", "", svg)
        svg = svg.replace("<svg ", '<svg fill="#FFFFFF" ', 1)
        (OUT_SVG / f"{slug}.svg").write_text(svg, encoding="utf-8")
        meta[slug] = {"title": by_slug[slug]["title"], "hex": "#" + by_slug[slug]["hex"].upper()}
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_SVG / "LICENSE.txt").write_text(
        "Ícones de marcas do projeto Simple Icons (https://simpleicons.org), licença CC0 1.0.\n"
        "As marcas pertencem aos seus respectivos donos; são usadas apenas para identificar cada serviço.\n",
        encoding="utf-8",
    )
    print(f"{len(slugs)} ícones gerados")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "package")
