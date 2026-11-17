"""Preferências do aparelho (não sensíveis), guardadas fora do cofre.

Algumas opções precisam valer com o cofre bloqueado; por isso ficam num JSON simples
ao lado do cofre. Nunca guarda nada do cofre (nem nomes de contas).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from owlock.core.vault import DEFAULT_VAULT_PATH

CONFIG_NAME = "config.json"
CUSTOM_CONFIG_NAME = "owlock-config.json"


@dataclass
class DesktopConfig:
    close_to_tray: bool = True
    lock_on_minimize: bool = False
    lock_on_session_lock: bool = True
    quick_search_hotkey: bool = True
    start_with_windows: bool = False  # espelho do registro; o registro é a fonte da verdade

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


_FIELDS = {f.name for f in fields(DesktopConfig)}


def config_path_for(vault_path: Path) -> Path:
    """`~/.owlock/config.json` para o cofre padrão; senão `<pasta do cofre>/owlock-config.json`."""
    vault_path = Path(vault_path)
    if vault_path == DEFAULT_VAULT_PATH:
        return DEFAULT_VAULT_PATH.parent / CONFIG_NAME
    return vault_path.parent / CUSTOM_CONFIG_NAME


def validate_config_data(data: Any) -> dict[str, bool] | None:
    """Devolve só as chaves conhecidas se todas forem bool; None se algo for inválido."""
    if not isinstance(data, dict):
        return None
    out: dict[str, bool] = {}
    for key, value in data.items():
        if key not in _FIELDS or not isinstance(value, bool):
            return None
        out[key] = value
    return out


def load_config(path: Path) -> DesktopConfig:
    """Lê o arquivo; ausente, ilegível ou inválido → padrões (valores ruins são ignorados um a um)."""
    config = DesktopConfig()
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config
    if not isinstance(raw, dict):
        return config
    for key in _FIELDS:
        value = raw.get(key)
        if isinstance(value, bool):
            setattr(config, key, value)
    return config


def save_config(path: Path, config: DesktopConfig) -> None:
    """Grava de forma atômica (arquivo temporário na mesma pasta + replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
