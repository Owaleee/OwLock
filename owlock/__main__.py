"""Ponto de entrada: `python -m owlock [--vault CAMINHO]`."""

from __future__ import annotations

import argparse
from pathlib import Path

from owlock.core.vault import DEFAULT_VAULT_PATH


def main() -> None:
    """Abre o aplicativo."""
    parser = argparse.ArgumentParser(prog="owlock", description="Gerenciador de senhas local.")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="caminho do arquivo do cofre")
    parser.add_argument("--tray", action="store_true", help="inicia escondido na bandeja (Windows)")
    args = parser.parse_args()

    from owlock.app.main import run

    run(args.vault, tray=args.tray)


if __name__ == "__main__":
    main()
