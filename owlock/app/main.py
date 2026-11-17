"""Abre a janela do OwLock (pywebview) ligada à Api."""
from __future__ import annotations

import sys
from pathlib import Path

from owlock.app.api import Api

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
ICON_ICO = Path(__file__).resolve().parent / "owlock.ico"
ICON_PNG = WEB_DIR / "img" / "owlock-icon.png"


def run(vault_path: Path) -> None:
    """Cria a janela e bloqueia até ela ser fechada."""
    import webview  # import tardio: os testes não dependem do pywebview

    api = Api(vault_path)
    window = webview.create_window(
        "OwLock",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1240,
        height=800,
        min_size=(900, 620),
        background_color="#0B0C0F",
    )
    window.events.closed += api.shutdown
    # http_server: serve a interface por um servidor local interno (necessário para módulos JS);
    # private_mode: não guarda cookies nem armazenamento do navegador em disco.
    # ícone da janela/barra de tarefas (Windows exige .ico; Linux/macOS usam o PNG)
    icon = ICON_ICO if sys.platform == "win32" else ICON_PNG
    webview.start(http_server=True, private_mode=True, icon=str(icon))
