"""Modelos de dados do cofre."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    """Data/hora atual em ISO 8601 UTC (segundos)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


CATEGORY_COLORS: dict[str, str] = {
    "mint": "#9FE3D3",
    "blue": "#7AB8FF",
    "violet": "#B69CFF",
    "pink": "#FF8FB8",
    "amber": "#FFB347",
    "coral": "#FF7A6B",
    "lime": "#B8E986",
    "gray": "#A1A6B4",
}

CATEGORY_ICONS: tuple[str, ...] = (
    "user", "briefcase", "gamepad", "chat", "card", "play",
    "home", "cart", "school", "code", "heart", "star",
)


@dataclass
class Category:
    """Categoria para organizar contas (cor e ícone são chaves das listas acima)."""

    name: str
    color: str = "gray"
    icon: str = "star"
    id: str = field(default_factory=lambda: uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável em JSON."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Category":
        """Cria a partir de dicionário, ignorando chaves desconhecidas."""
        if not isinstance(d, dict):
            raise ValueError("Categoria inválida: esperado um objeto.")
        for required in ("name", "id"):
            if required not in d:
                raise ValueError(f"Categoria inválida: campo '{required}' ausente.")
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class Entry:
    """Uma conta guardada no cofre."""

    service: str
    username: str = ""
    password: str = ""
    has_2fa: bool = False
    twofa_app: str = ""
    notes: str = ""
    category_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    url: str = ""
    password_history: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável em JSON."""
        out = {f.name: getattr(self, f.name) for f in fields(self)}
        out["password_history"] = copy.deepcopy(self.password_history)
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Entry":
        """Cria a partir de dicionário, ignorando chaves desconhecidas."""
        if not isinstance(d, dict):
            raise ValueError("Entrada inválida: esperado um objeto.")
        for required in ("service", "id"):
            if required not in d:
                raise ValueError(f"Entrada inválida: campo '{required}' ausente.")
        names = {f.name for f in fields(cls)}
        data = {k: v for k, v in d.items() if k in names}
        history = data.get("password_history", [])
        if not isinstance(history, list):
            raise ValueError("Entrada inválida: histórico de senhas deve ser uma lista.")
        for item in history:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("password"), str)
                or not isinstance(item.get("changed_at"), str)
            ):
                raise ValueError("Entrada inválida: item de histórico malformado.")
        data["password_history"] = [
            {"password": i["password"], "changed_at": i["changed_at"]} for i in history
        ]
        if not isinstance(data.get("url", ""), str):
            data["url"] = ""
        return cls(**data)


AUTO_LOCK_OPTIONS: tuple[int, ...] = (1, 2, 5, 10, 15, 30)
CLIPBOARD_OPTIONS: tuple[int, ...] = (10, 20, 30, 45, 60, 90)
DEFAULT_AUTO_LOCK_MINUTES = 5
DEFAULT_CLIPBOARD_SECONDS = 30


def _pick(value: Any, options: tuple[int, ...], default: int) -> int:
    """Devolve `value` se for um inteiro (não booleano) dentre as opções; senão o padrão."""
    if isinstance(value, bool) or not isinstance(value, int) or value not in options:
        return default
    return value


@dataclass
class Settings:
    """Ajustes do cofre (guardados dentro do conteúdo cifrado)."""

    auto_lock_minutes: int = DEFAULT_AUTO_LOCK_MINUTES
    clipboard_clear_seconds: int = DEFAULT_CLIPBOARD_SECONDS

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável em JSON."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: Any) -> "Settings":
        """Cria a partir de dicionário; valores inválidos ou ausentes viram o padrão."""
        if not isinstance(d, dict):
            return cls()
        return cls(
            auto_lock_minutes=_pick(
                d.get("auto_lock_minutes"), AUTO_LOCK_OPTIONS, DEFAULT_AUTO_LOCK_MINUTES
            ),
            clipboard_clear_seconds=_pick(
                d.get("clipboard_clear_seconds"), CLIPBOARD_OPTIONS, DEFAULT_CLIPBOARD_SECONDS
            ),
        )

    def is_valid(self) -> bool:
        """True se ambos os valores estão entre as opções permitidas."""
        return (
            _pick(self.auto_lock_minutes, AUTO_LOCK_OPTIONS, -1) != -1
            and _pick(self.clipboard_clear_seconds, CLIPBOARD_OPTIONS, -1) != -1
        )
