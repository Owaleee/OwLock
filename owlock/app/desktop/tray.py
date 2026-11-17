"""Ícone na bandeja do sistema (pystray, só no Windows)."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("owlock.tray")

ICON_PNG = Path(__file__).resolve().parent.parent.parent / "web" / "img" / "owlock-icon.png"
TITLE_OPEN = "OwLock — aberto"
TITLE_LOCKED = "OwLock — bloqueado"


@dataclass
class TrayHandlers:
    """Ações e estados do menu (todos injetados pelo DesktopController)."""

    on_open: Callable[[], None]
    on_quick: Callable[[], None]
    on_generate: Callable[[], None]
    on_lock: Callable[[], None]
    on_toggle_autostart: Callable[[], None]
    on_quit: Callable[[], None]
    is_locked: Callable[[], bool]
    is_autostart: Callable[[], bool]


class Tray:
    """Interface; a base é a implementação nula (sem bandeja)."""

    available = False

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def set_locked(self, locked: bool) -> None:
        return None

    def refresh(self) -> None:
        return None


NullTray = Tray


def locked_variant(image: Any) -> Any:
    """Cópia do ícone com o LED da fechadura (verde) apagado, em cinza."""
    img = image.convert("RGBA")
    px = img.load()
    width, height = img.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = px[x, y]
            if a and g > r + 40 and g > b + 10:
                gray = int(0.3 * r + 0.59 * g + 0.11 * b)
                gray = max(70, min(gray, 120))
                px[x, y] = (gray, gray, gray, a)
    return img


class PystrayTray(Tray):
    available = True

    def __init__(self, handlers: TrayHandlers, icon_path: Path = ICON_PNG) -> None:
        self._h = handlers
        self._icon_path = icon_path
        self._icon: Any = None
        self._open_img: Any = None
        self._locked_img: Any = None

    def _build_menu(self) -> Any:
        import pystray

        h = self._h
        item = pystray.MenuItem
        return pystray.Menu(
            item("Abrir OwLock", lambda icon, it: h.on_open(), default=True),
            item("Busca rápida (Ctrl+Shift+Espaço)", lambda icon, it: h.on_quick()),
            item("Gerar senha e copiar", lambda icon, it: h.on_generate()),
            item("Bloquear agora", lambda icon, it: h.on_lock(), enabled=lambda it: not h.is_locked()),
            pystray.Menu.SEPARATOR,
            item("Iniciar com o Windows", lambda icon, it: h.on_toggle_autostart(), checked=lambda it: h.is_autostart()),
            pystray.Menu.SEPARATOR,
            item("Sair", lambda icon, it: h.on_quit()),
        )

    def start(self) -> None:
        import pystray
        from PIL import Image

        base = Image.open(self._icon_path)
        base.load()
        self._open_img = base.convert("RGBA").resize((64, 64))
        self._locked_img = locked_variant(self._open_img)
        locked = self._h.is_locked()
        self._icon = pystray.Icon(
            "OwLock",
            self._locked_img if locked else self._open_img,
            TITLE_LOCKED if locked else TITLE_OPEN,
            self._build_menu(),
        )
        self._icon.run_detached()

    def set_locked(self, locked: bool) -> None:
        icon = self._icon
        if icon is None:
            return
        try:
            icon.icon = self._locked_img if locked else self._open_img
            icon.title = TITLE_LOCKED if locked else TITLE_OPEN
            icon.update_menu()
        except Exception:  # noqa: BLE001
            log.exception("Falha ao atualizar o ícone da bandeja")

    def refresh(self) -> None:
        icon = self._icon
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:  # noqa: BLE001
                log.exception("Falha ao atualizar o menu da bandeja")

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.visible = False
                icon.stop()
            except Exception:  # noqa: BLE001
                log.exception("Falha ao remover o ícone da bandeja")


def pystray_importable() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def create_tray(handlers: TrayHandlers) -> Tray:
    if pystray_importable():
        return PystrayTray(handlers)
    return NullTray()
