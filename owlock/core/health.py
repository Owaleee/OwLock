"""Saúde das senhas: repetidas e antigas (cálculo puro, só em memória)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .models import Entry

STALE_DAYS = 365


def _parse_utc(value: Any) -> datetime | None:
    """ISO 8601 -> datetime com fuso UTC (sem fuso = UTC); None se não der para ler."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def password_changed_at(entry: Entry) -> datetime | None:
    """Quando a senha atual foi definida: changed_at mais recente do histórico, senão created_at."""
    moments = [m for m in (_parse_utc(h.get("changed_at")) for h in entry.password_history) if m]
    if moments:
        return max(moments)
    return _parse_utc(entry.created_at)


def password_health(entries: Iterable[Entry], now: datetime) -> dict[str, dict[str, Any]]:
    """Saúde por conta, indexada pelo id da conta.

    Cada valor: {"reused": bool, "reused_count": int, "reused_with": [ids das OUTRAS contas],
    "stale": bool}. As senhas só são comparadas aqui, em memória, e nunca saem.
    Senha vazia não conta como repetida. "Antiga" = mais de 365 dias (em datas UTC) sem troca.
    `now` é o relógio (datetime; sem fuso = UTC), injetável nos testes.
    """
    items = list(entries)
    today = (now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).date()
    groups: dict[str, list[str]] = {}
    for entry in items:
        if entry.password:
            groups.setdefault(entry.password, []).append(entry.id)
    out: dict[str, dict[str, Any]] = {}
    for entry in items:
        others = [i for i in groups.get(entry.password, []) if i != entry.id] if entry.password else []
        changed = password_changed_at(entry)
        stale = changed is not None and (today - changed.date()).days > STALE_DAYS
        out[entry.id] = {
            "reused": bool(others),
            "reused_count": len(others),
            "reused_with": others,
            "stale": stale,
        }
    return out
