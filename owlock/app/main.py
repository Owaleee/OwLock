"""Abre a janela do OwLock (pywebview) ligada à Api."""
from __future__ import annotations

import sys
from pathlib import Path

from owlock.app.api import Api

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
ICON_ICO = Path(__file__).resolve().parent / "owlock.ico"
ICON_PNG = WEB_DIR / "img" / "owlock-icon.png"


def _save_dialog_type(webview):
    """Constante do diálogo "Salvar como" da versão instalada do pywebview."""
    file_dialog = getattr(webview, "FileDialog", None)
    if file_dialog is not None and hasattr(file_dialog, "SAVE"):
        return file_dialog.SAVE
    return webview.SAVE_DIALOG  # versões antigas


def run(vault_path: Path) -> None:
    """Cria a janela e bloqueia até ela ser fechada."""
    import webview  # import tardio: os testes não dependem do pywebview

    from owlock.core import default_store

    holder: dict = {}

    def save_dialog(default_name: str) -> str | None:
        window = holder.get("window")
        if window is None:
            return None
        result = window.create_file_dialog(
            _save_dialog_type(webview),
            save_filename=default_name,
            file_types=("Página da web (*.html)",),
        )
        if not result:
            return None
        return result if isinstance(result, str) else str(result[0])

    api = Api(vault_path, store=default_store(), save_dialog=save_dialog)
    window = webview.create_window(
        "OwLock",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1240,
        height=800,
        min_size=(900, 620),
        background_color="#0B0C0F",
    )
    holder["window"] = window
    window.events.closed += api.shutdown
    # http_server: serve a interface por um servidor local interno (necessário para módulos JS);
    # private_mode: não guarda cookies nem armazenamento do navegador em disco.
    # ícone da janela/barra de tarefas (Windows exige .ico; Linux/macOS usam o PNG)
    icon = ICON_ICO if sys.platform == "win32" else ICON_PNG
    webview.start(http_server=True, private_mode=True, icon=str(icon))
