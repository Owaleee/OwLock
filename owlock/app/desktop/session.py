"""Detecta "Windows travado" sondando o desktop de entrada a cada 2 s."""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

log = logging.getLogger("owlock.session")

POLL_SECONDS = 2.0
_UOI_NAME = 2
_DESKTOP_READOBJECTS = 0x0001


class SessionWatcher:
    """Interface; a base é a implementação nula."""

    available = False

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


NullSessionWatcher = SessionWatcher


def is_session_locked() -> bool:
    """True se o desktop de entrada não é o "Default" (ou não pôde ser aberto)."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL
    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL

    handle = user32.OpenInputDesktop(0, False, _DESKTOP_READOBJECTS)
    if not handle:
        return True  # sem acesso ao desktop de entrada = tela de bloqueio/UAC
    try:
        needed = wintypes.DWORD(0)
        buf = ctypes.create_unicode_buffer(256)
        ok = user32.GetUserObjectInformationW(handle, _UOI_NAME, buf, ctypes.sizeof(buf), ctypes.byref(needed))
        if not ok:
            return True
        return buf.value.lower() != "default"
    finally:
        user32.CloseDesktop(handle)


class PollingSessionWatcher(SessionWatcher):
    available = True

    def __init__(
        self,
        on_lock: Callable[[], None],
        probe: Callable[[], bool] = is_session_locked,
        interval: float = POLL_SECONDS,
    ) -> None:
        self._on_lock = on_lock
        self._probe = probe
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="owlock-session", daemon=True)
        self._thread.start()

    def _safe_probe(self) -> bool:
        try:
            return bool(self._probe())
        except Exception:  # noqa: BLE001
            return True

    def _run(self) -> None:
        was_locked = self._safe_probe()
        while not self._stop.wait(self._interval):
            locked = self._safe_probe()
            if locked and not was_locked:  # só na transição destravado → travado
                try:
                    self._on_lock()
                except Exception:  # noqa: BLE001
                    log.exception("Falha ao tratar o bloqueio da sessão")
            was_locked = locked

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(3)
        self._thread = None


def create_session_watcher(on_lock: Callable[[], None]) -> SessionWatcher:
    if sys.platform == "win32":
        return PollingSessionWatcher(on_lock)
    return NullSessionWatcher()
