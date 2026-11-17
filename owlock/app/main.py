"""Abre a janela do OwLock (pywebview) ligada à Api."""
from __future__ import annotations

import sys
from pathlib import Path

from owlock.app.api import Api
from owlock.app.config import config_path_for, load_config
from owlock.core.vault import DEFAULT_VAULT_PATH

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
ICON_ICO = Path(__file__).resolve().parent / "owlock.ico"
ICON_PNG = WEB_DIR / "img" / "owlock-icon.png"


def _save_dialog_type(webview):
    """Constante do diálogo "Salvar como" da versão instalada do pywebview."""
    file_dialog = getattr(webview, "FileDialog", None)
    if file_dialog is not None and hasattr(file_dialog, "SAVE"):
        return file_dialog.SAVE
    return webview.SAVE_DIALOG  # versões antigas


def run(vault_path: Path, tray: bool = False) -> None:
    """Cria a janela e bloqueia até ela ser fechada.

    `tray=True` (opção --tray, usada pela inicialização com o Windows) abre escondido na bandeja.
    """
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
    desktop = sys.platform == "win32"  # bandeja, atalho global e sessão só existem no Windows
    from owlock.app.desktop import tray as tray_module

    start_hidden = bool(tray and desktop and tray_module.pystray_importable())
    window = webview.create_window(
        "OwLock",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1240,
        height=800,
        min_size=(900, 620),
        background_color="#0B0C0F",
        hidden=start_hidden,
    )
    holder["window"] = window
    window.events.closed += api.shutdown
    controller = None
    if desktop:
        # Busca rápida: segunda janela, escondida, com a MESMA Api (rota #quick).
        quick = webview.create_window(
            "OwLock — busca rápida",
            url=str(WEB_DIR / "index.html") + "#quick",
            js_api=api,
            width=560,
            height=420,
            resizable=False,
            on_top=True,
            hidden=True,
            background_color="#0B0C0F",
        )
        controller = _build_controller(api, window, quick, vault_path)
        api._attach_desktop(controller)
        window.events.closed += controller.quit
    # http_server: serve a interface por um servidor local interno (necessário para módulos JS);
    # private_mode: não guarda cookies nem armazenamento do navegador em disco.
    # ícone da janela/barra de tarefas (Windows exige .ico; Linux/macOS usam o PNG)
    icon = ICON_ICO if sys.platform == "win32" else ICON_PNG
    webview.start(
        controller.start if controller is not None else None,
        http_server=True,
        private_mode=True,
        icon=str(icon),
    )


def _build_controller(api, window, quick, vault_path: Path):
    """Monta o DesktopController com as peças reais do Windows."""
    from owlock.app.desktop import (
        DesktopController,
        create_autostart,
        create_hotkey,
        create_session_watcher,
        create_tray,
    )

    config_path = config_path_for(vault_path)
    return DesktopController(
        api=api,
        main_window=window,
        quick_window=quick,
        config=load_config(config_path),
        config_path=config_path,
        tray_factory=create_tray,
        hotkey_factory=create_hotkey,
        session_factory=create_session_watcher,
        autostart=create_autostart(None if Path(vault_path) == DEFAULT_VAULT_PATH else Path(vault_path)),
        poll_interval=2.0,
    )
