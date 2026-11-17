"""Atalho global (Ctrl+Shift+Espaço) via RegisterHotKey numa thread com laço de mensagens."""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

log = logging.getLogger("owlock.hotkey")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
VK_SPACE = 0x20
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
_HOTKEY_ID = 0x0A11


class Hotkey:
    """Interface; a base é a implementação nula."""

    available = False  # atalho registrado e ativo
    supported = False  # a plataforma permite tentar registrar

    def start(self) -> bool:
        return False

    def stop(self) -> None:
        return None


NullHotkey = Hotkey


class WindowsHotkey(Hotkey):
    supported = True

    def __init__(self, callback: Callable[[], None], modifiers: int = MOD_CONTROL | MOD_SHIFT, vk: int = VK_SPACE) -> None:
        self._callback = callback
        self._modifiers = modifiers | MOD_NOREPEAT
        self._vk = vk
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._ok = False
        self.available = False

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return self.available
        self._ready.clear()
        self._ok = False
        self._thread = threading.Thread(target=self._loop, name="owlock-hotkey", daemon=True)
        self._thread.start()
        self._ready.wait(5)
        self.available = self._ok
        return self._ok

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        self._thread_id = int(kernel32.GetCurrentThreadId())
        registered = bool(user32.RegisterHotKey(None, _HOTKEY_ID, self._modifiers, self._vk))
        if not registered:
            log.warning("Atalho global indisponível (em uso por outro programa): erro %s", ctypes.get_last_error())
            self._ok = False
            self._ready.set()
            return
        self._ok = True
        self._ready.set()
        try:
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:  # 0 = WM_QUIT, -1 = erro
                    break
                if msg.message == WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                    try:
                        self._callback()
                    except Exception:  # noqa: BLE001
                        log.exception("Falha ao tratar o atalho global")
        finally:
            user32.UnregisterHotKey(None, _HOTKEY_ID)

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        if thread.is_alive() and self._thread_id:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW.restype = wintypes.BOOL
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if thread is not threading.current_thread():
            thread.join(3)
        self._thread = None
        self._thread_id = 0
        self.available = False


def create_hotkey(callback: Callable[[], None]) -> Hotkey:
    if sys.platform == "win32":
        return WindowsHotkey(callback)
    return NullHotkey()
