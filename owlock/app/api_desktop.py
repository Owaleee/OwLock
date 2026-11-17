"""Métodos de desktop da Api (bandeja, busca rápida, preferências do aparelho).

Mixin: `class Api(DesktopApiMixin)`. Usa os atributos da Api (`_lock`, `_vault`, `_require`,
`_copy_with_timer`, `_clear_after`, `_path`). Atributos próprios começam com "_".
"""
from __future__ import annotations

import sys
from typing import Any

from owlock.app.config import (
    DesktopConfig,
    config_path_for,
    load_config,
    save_config,
    validate_config_data,
)
from owlock.core.generator import generate_password
from owlock.core.strength import password_strength

LOCKED_CLEAR_SECONDS = 30
GENERATED_LENGTH = 20


def _err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": code, "message": message}


class DesktopApiMixin:
    _desktop: Any = None

    def _attach_desktop(self, controller: Any) -> None:
        """Registra o DesktopController (chamado por main.py)."""
        self._desktop = controller

    # ---- preferências ----
    def _desktop_info(self) -> dict[str, Any]:
        if self._desktop is not None:
            return self._desktop.info()
        return {
            "platform": "windows" if sys.platform == "win32" else "other",
            "tray_available": False,
            "hotkey_available": False,
        }

    def _desktop_config(self) -> DesktopConfig:
        if self._desktop is not None:
            return self._desktop.config
        return load_config(config_path_for(self._path))  # type: ignore[attr-defined]

    def get_desktop_config(self) -> dict[str, Any]:
        """Preferências do aparelho. Não exige cofre aberto."""
        return {"ok": True, "config": self._desktop_config().to_dict(), **self._desktop_info()}

    def save_desktop_config(self, data: Any) -> dict[str, Any]:
        """Valida (só bool, só chaves conhecidas), aplica na hora e grava o config.json."""
        values = validate_config_data(data)
        if values is None:
            return _err("invalid_config", "Configuração inválida.")
        if self._desktop is not None:
            try:
                new = self._desktop.update_config(values)
            except OSError:
                return _err("save_failed", "Não foi possível aplicar ou salvar a configuração.")
            return {"ok": True, "config": new.to_dict()}
        current = self._desktop_config()
        new = DesktopConfig(**{**current.to_dict(), **values})
        try:
            save_config(config_path_for(self._path), new)  # type: ignore[attr-defined]
        except OSError:
            return _err("save_failed", "Não foi possível salvar a configuração.")
        return {"ok": True, "config": new.to_dict()}

    # ---- janelas ----
    def quick_hide(self) -> dict[str, Any]:
        if self._desktop is not None:
            self._desktop.hide_quick()
        return {"ok": True}

    def quick_open_main(self, id: Any = None) -> dict[str, Any]:  # noqa: A002 - nome do contrato
        if self._desktop is not None:
            self._desktop.show_main(id if isinstance(id, str) and id else None)
        return {"ok": True}

    # ---- gerar e copiar ----
    def generate_and_copy(self) -> dict[str, Any]:
        """Gera 20 caracteres e copia com limpeza automática. Nunca devolve a senha."""
        password = generate_password(GENERATED_LENGTH)
        with self._lock:  # type: ignore[attr-defined]
            self._require()  # type: ignore[attr-defined]  # expira o cofre se preciso e conta atividade
            locked = self._vault is None  # type: ignore[attr-defined]
            saved = self._clear_after  # type: ignore[attr-defined]
            if locked:
                self._clear_after = LOCKED_CLEAR_SECONDS  # type: ignore[attr-defined]
            try:
                result = self._copy_with_timer(password)  # type: ignore[attr-defined]
            finally:
                if locked:
                    self._clear_after = saved  # type: ignore[attr-defined]
        if not result.get("ok"):
            return result
        return {"ok": True, "clear_in": result["clear_in"], "strength": password_strength(password)}
