"""Uma única instância do OwLock por cofre (Windows).

Duas cópias abertas gravariam o mesmo arquivo e uma poderia desfazer o que a outra salvou.
A primeira instância cria um mutex nomeado e fica esperando um evento nomeado; quem abrir o app de
novo encontra o mutex, dispara o evento (a primeira mostra a janela) e encerra. Sem rede, sem arquivos.
Fora do Windows não faz nada (sempre "primeira instância").
"""
from __future__ import annotations

import hashlib
import sys
import threading
from pathlib import Path
from typing import Any, Callable

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0


def instance_key(vault_path: Path) -> str:
    """Nome estável por cofre (o caminho não aparece no nome)."""
    try:
        resolved = str(Path(vault_path).expanduser().resolve())
    except OSError:
        resolved = str(vault_path)
    return "OwLock-" + hashlib.sha256(resolved.casefold().encode("utf-8")).hexdigest()[:20]


def _kernel32() -> Any:
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateMutexW.restype = wintypes.HANDLE
    k.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateEventW.restype = wintypes.HANDLE
    k.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k.OpenEventW.restype = wintypes.HANDLE
    k.SetEvent.argtypes = [wintypes.HANDLE]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.get_last_error = ctypes.get_last_error
    return k


class SingleInstance:
    def __init__(self, key: str, kernel: Any = None, enabled: bool | None = None) -> None:
        self.key = key
        self._enabled = (sys.platform == "win32") if enabled is None else enabled
        self._kernel = kernel
        self._mutex = None
        self._event = None

    def _k(self) -> Any:
        if self._kernel is None:
            self._kernel = _kernel32()
        return self._kernel

    def acquire(self) -> bool:
        """True se esta é a primeira instância (e fica dona do mutex até o processo terminar)."""
        if not self._enabled:
            return True
        try:
            k = self._k()
            self._mutex = k.CreateMutexW(None, False, "Local\\" + self.key)
            if self._mutex and k.get_last_error() == ERROR_ALREADY_EXISTS:
                return False
            self._event = k.CreateEventW(None, False, False, "Local\\" + self.key + "-show")
        except Exception:  # noqa: BLE001 - sem a proteção, o app abre normalmente
            return True
        return True

    def notify_existing(self) -> bool:
        """Pede para a instância que já está aberta mostrar a janela."""
        if not self._enabled:
            return False
        try:
            k = self._k()
            handle = k.OpenEventW(EVENT_MODIFY_STATE, False, "Local\\" + self.key + "-show")
            if not handle:
                return False
            try:
                return bool(k.SetEvent(handle))
            finally:
                k.CloseHandle(handle)
        except Exception:  # noqa: BLE001
            return False

    def listen(self, on_show: Callable[[], Any]) -> threading.Thread | None:
        """Thread que chama `on_show` cada vez que outra instância tenta abrir."""
        if not self._enabled or not self._event:
            return None
        k, event = self._k(), self._event

        def loop() -> None:
            while k.WaitForSingleObject(event, INFINITE) == WAIT_OBJECT_0:
                try:
                    on_show()
                except Exception:  # noqa: BLE001 - nunca derruba o app
                    pass

        thread = threading.Thread(target=loop, name="owlock-single-instance", daemon=True)
        thread.start()
        return thread
