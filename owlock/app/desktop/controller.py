"""Orquestra a integração com o desktop: bandeja, atalho, sessão, janelas e inicialização.

Tudo é injetado (api, janelas, fábricas), então a lógica é testável sem Windows com objetos falsos.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from owlock.app.config import DesktopConfig, save_config
from owlock.app.desktop.tray import TrayHandlers

log = logging.getLogger("owlock.desktop")

LOCKED_JS = "window.owlockEvent && owlockEvent('locked')"


def _select_js(entry_id: str) -> str:
    return f"window.owlockEvent && owlockEvent('select', {json.dumps(entry_id)})"


def center_window(window: Any) -> None:
    """Centraliza na tela principal, se o pywebview instalado informar o tamanho das telas."""
    try:
        import webview

        screen = webview.screens[0]
        width = int(getattr(window, "width", 560))
        height = int(getattr(window, "height", 420))
        window.move(int(screen.x + (screen.width - width) / 2), int(screen.y + (screen.height - height) / 2))
    except Exception:  # noqa: BLE001 - sem informação de tela: fica onde estiver
        pass


class DesktopController:
    def __init__(
        self,
        api: Any,
        main_window: Any,
        quick_window: Any,
        config: DesktopConfig,
        config_path: Path | None,
        tray_factory: Callable[[TrayHandlers], Any],
        hotkey_factory: Callable[[Callable[[], None]], Any],
        session_factory: Callable[[Callable[[], None]], Any],
        autostart: Any,
        center: Callable[[Any], None] = center_window,
        poll_interval: float | None = None,
    ) -> None:
        self.api = api
        self.main_window = main_window
        self.quick_window = quick_window
        self.config = config
        self._config_path = config_path
        self._autostart = autostart
        self._center = center
        self._poll_interval = poll_interval
        self._lock = threading.RLock()
        self._quitting = False
        self._started = False
        self._last_locked: bool | None = None
        self._poll_stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._hotkey_running = False
        self.tray = tray_factory(
            TrayHandlers(
                on_open=self.show_main,
                on_quick=self.on_quick,
                on_generate=self.generate_and_copy,
                on_lock=self.lock_now,
                on_toggle_autostart=self.toggle_autostart,
                on_quit=self.quit,
                is_locked=self.is_locked,
                is_autostart=self.autostart_enabled,
            )
        )
        self.hotkey = hotkey_factory(self.on_hotkey)
        self.session = session_factory(self.on_session_locked)

    # ---- ciclo de vida ----
    def start(self, hidden: bool = False) -> None:
        """Liga bandeja, atalho, detector de sessão e ganchos das janelas."""
        with self._lock:
            if self._started:
                return
            self._started = True
        self.config.start_with_windows = self.autostart_enabled()
        self._hook_windows()
        try:
            self.tray.start()
        except Exception:  # noqa: BLE001
            log.exception("Bandeja indisponível")
            self.tray = _FailedTray()
        if self.config.quick_search_hotkey:
            self._start_hotkey()
        self.session.start()
        if hidden and self.tray.available:
            self.main_window.hide()
        if self._poll_interval:
            self._poll_thread = threading.Thread(target=self._poll, name="owlock-tray-sync", daemon=True)
            self._poll_thread.start()

    def _hook_windows(self) -> None:
        self.main_window.events.closing += self.on_main_closing
        self.main_window.events.minimized += self.on_minimized
        self.quick_window.events.closing += self.on_quick_closing

    def _poll(self) -> None:
        while not self._poll_stop.wait(self._poll_interval):
            try:
                self.sync_tray()
            except Exception:  # noqa: BLE001
                log.exception("Falha ao sincronizar a bandeja")

    def sync_tray(self) -> None:
        locked = self.is_locked()
        if locked != self._last_locked:
            self._last_locked = locked
            self.tray.set_locked(locked)

    # ---- estado ----
    def is_locked(self) -> bool:
        try:
            return not bool(self.api.status().get("unlocked"))
        except Exception:  # noqa: BLE001
            return True

    def autostart_enabled(self) -> bool:
        try:
            return bool(self._autostart.is_enabled())
        except Exception:  # noqa: BLE001
            return False

    @property
    def tray_available(self) -> bool:
        return bool(getattr(self.tray, "available", False))

    @property
    def hotkey_available(self) -> bool:
        if self._hotkey_running:
            return bool(self.hotkey.available)
        return bool(getattr(self.hotkey, "supported", False))

    def info(self) -> dict[str, Any]:
        return {
            "platform": "windows" if sys.platform == "win32" else "other",
            "tray_available": self.tray_available,
            "hotkey_available": self.hotkey_available,
        }

    # ---- janelas ----
    def _show(self, window: Any) -> None:
        window.show()
        try:
            window.restore()
        except Exception:  # noqa: BLE001
            pass

    def show_main(self, entry_id: str | None = None) -> None:
        self._show(self.main_window)
        if entry_id and not self.is_locked():
            self._eval(self.main_window, _select_js(entry_id))

    def show_quick(self) -> None:
        self._show(self.quick_window)
        self._center(self.quick_window)

    def hide_quick(self) -> None:
        self.quick_window.hide()

    def on_quick(self) -> None:
        """Atalho/menu: bloqueado → janela principal (desbloqueio); aberto → busca rápida."""
        if self.is_locked():
            self.show_main()
        else:
            self.show_quick()

    on_hotkey = on_quick

    def _eval(self, window: Any, js: str) -> None:
        try:
            window.evaluate_js(js)
        except Exception:  # noqa: BLE001 - janela ainda sem página carregada
            pass

    # ---- bloqueio ----
    def lock_now(self) -> None:
        """Bloqueia o cofre e avisa as duas janelas e a bandeja."""
        self.api.lock()
        self._eval(self.main_window, LOCKED_JS)
        self._eval(self.quick_window, LOCKED_JS)
        self.tray.set_locked(True)
        self._last_locked = True

    def on_session_locked(self) -> None:
        if self.config.lock_on_session_lock:
            self.lock_now()

    def on_minimized(self) -> None:
        if self.config.lock_on_minimize:
            self.lock_now()

    # ---- fechamento ----
    def on_main_closing(self) -> bool | None:
        """False cancela o fechamento (pywebview); só com bandeja disponível."""
        if self._quitting:
            return None
        if self.config.close_to_tray and self.tray_available:
            self.main_window.hide()
            return False
        return None

    def on_quick_closing(self) -> bool | None:
        if self._quitting:
            return None
        self.quick_window.hide()
        return False

    def quit(self) -> None:
        """Encerra tudo (idempotente): atalho, sessão, Api, bandeja, janelas."""
        with self._lock:
            if self._quitting:
                return
            self._quitting = True
        self._poll_stop.set()
        steps: list[Callable[[], Any]] = [
            self._stop_hotkey,
            self.session.stop,
            self.api.shutdown,
            self.tray.stop,
            self.quick_window.destroy,
            self.main_window.destroy,
        ]
        for step in steps:
            try:
                step()
            except Exception:  # noqa: BLE001 - segue encerrando
                log.exception("Falha ao encerrar")

    # ---- atalho ----
    def _start_hotkey(self) -> None:
        self._hotkey_running = True
        try:
            ok = self.hotkey.start()
        except Exception:  # noqa: BLE001
            log.exception("Falha ao registrar o atalho global")
            ok = False
        if not ok:
            log.warning("Atalho global indisponível; seguindo sem atalho")

    def _stop_hotkey(self) -> None:
        if self._hotkey_running:
            self._hotkey_running = False
            self.hotkey.stop()

    # ---- inicialização com o Windows e configuração ----
    def toggle_autostart(self) -> None:
        self.update_config({"start_with_windows": not self.autostart_enabled()})
        self.tray.refresh()

    def generate_and_copy(self) -> dict[str, Any]:
        return self.api.generate_and_copy()

    def update_config(self, values: dict[str, bool]) -> DesktopConfig:
        """Aplica na hora (registro, atalho) e grava o config.json. `values` já validado."""
        with self._lock:
            new = DesktopConfig(**{**self.config.to_dict(), **values})
            # só mexe no registro quando o valor muda: a interface envia todas as chaves a cada ajuste,
            # e regravar o "Iniciar com o Windows" sem necessidade trocaria o comando salvo (outro cofre).
            if "start_with_windows" in values and values["start_with_windows"] != self.autostart_enabled():
                if values["start_with_windows"]:
                    self._autostart.enable()
                else:
                    self._autostart.disable()
                new.start_with_windows = self.autostart_enabled()
            if new.quick_search_hotkey and not self._hotkey_running:
                self._start_hotkey()
            elif not new.quick_search_hotkey:
                self._stop_hotkey()
            self.config = new
            if self._config_path is not None:
                save_config(self._config_path, new)
            return new


class _FailedTray:
    available = False

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def set_locked(self, locked: bool) -> None: ...
    def refresh(self) -> None: ...


__all__ = ["DesktopController", "LOCKED_JS", "center_window"]
