"""Iniciar com o Windows (HKCU\\...\\Run)."""
from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "OwLock"


class Autostart:
    """Interface; a base é a implementação nula (sem suporte)."""

    available = False

    def is_enabled(self) -> bool:
        return False

    def enable(self) -> None:
        return None

    def disable(self) -> None:
        return None


NullAutostart = Autostart


def build_command(vault_path: Path | None = None) -> str:
    """Linha de comando entre aspas: executável empacotado, ou pythonw -m owlock."""
    if getattr(sys, "frozen", False):
        parts = [f'"{sys.executable}"']
    else:
        exe = Path(sys.executable)
        pythonw = exe.with_name("pythonw.exe")
        runner = pythonw if pythonw.exists() else exe
        parts = [f'"{runner}"', "-m", "owlock"]
    parts.append("--tray")
    if vault_path is not None:
        parts += ["--vault", f'"{vault_path}"']
    return " ".join(parts)


class WindowsAutostart(Autostart):
    available = True

    def __init__(self, command: str | None = None, key: str = RUN_KEY, value_name: str = VALUE_NAME) -> None:
        self._command = command
        self._key = key
        self._name = value_name

    def command(self) -> str:
        return self._command if self._command is not None else build_command()

    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key, 0, winreg.KEY_READ) as k:
                value, _ = winreg.QueryValueEx(k, self._name)
        except OSError:
            return False
        return isinstance(value, str) and bool(value.strip())

    def enable(self) -> None:
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self._key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, self._name, 0, winreg.REG_SZ, self.command())

    def disable(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, self._name)
        except FileNotFoundError:
            pass  # chave ou valor inexistente: já está desligado


def create_autostart(vault_path: Path | None = None) -> Autostart:
    if sys.platform == "win32":
        return WindowsAutostart(build_command(vault_path))
    return NullAutostart()
