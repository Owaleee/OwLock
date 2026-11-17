"""Integração com o Windows (bandeja, atalho global, sessão, inicialização).

Cada módulo tem uma implementação nula fora do Windows; todos importam sem erro em qualquer sistema.
"""
from __future__ import annotations

from owlock.app.desktop.autostart import Autostart, NullAutostart, WindowsAutostart, create_autostart
from owlock.app.desktop.controller import DesktopController
from owlock.app.desktop.hotkey import Hotkey, NullHotkey, create_hotkey
from owlock.app.desktop.session import NullSessionWatcher, SessionWatcher, create_session_watcher
from owlock.app.desktop.tray import NullTray, Tray, create_tray

__all__ = [
    "Autostart", "NullAutostart", "WindowsAutostart", "create_autostart",
    "DesktopController",
    "Hotkey", "NullHotkey", "create_hotkey",
    "NullSessionWatcher", "SessionWatcher", "create_session_watcher",
    "NullTray", "Tray", "create_tray",
]
