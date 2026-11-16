"""Modelos de dados do cofre."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    """Data/hora atual em ISO 8601 UTC (segundos)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Entry:
    """Uma conta guardada no cofre."""

    service: str
    username: str = ""
    password: str = ""
    has_2fa: bool = False
    twofa_app: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável em JSON."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Entry":
        """Cria a partir de dicionário, ignorando chaves desconhecidas."""
        if not isinstance(d, dict):
            raise ValueError("Entrada inválida: esperado um objeto.")
        for required in ("service", "id"):
            if required not in d:
                raise ValueError(f"Entrada inválida: campo '{required}' ausente.")
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})
