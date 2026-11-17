"""Biblioteca de serviços: links de login e ícones das plataformas (dados embutidos)."""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

_DATA_DIR = Path(__file__).parent / "data"
ICON_URL_PREFIX = "icons/brands/"

_builtin_cache: list[dict[str, Any]] | None = None
_icons_cache: dict[str, dict[str, str]] | None = None


def normalize(text: str) -> str:
    """casefold, sem acentos, só [a-z0-9]: "Epic Games" -> "epicgames"; "gov.br" -> "govbr"."""
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        c for c in decomposed if c.isascii() and c.isalnum() and not unicodedata.combining(c)
    )


def icon_url(slug: str) -> str | None:
    """Caminho relativo do SVG de um ícone ("" -> None)."""
    return f"{ICON_URL_PREFIX}{slug}.svg" if slug else None


def brand_icons() -> dict[str, dict[str, str]]:
    """{slug: {title, hex}} dos ícones embutidos (cache em memória)."""
    global _icons_cache
    if _icons_cache is None:
        raw = json.loads((_DATA_DIR / "brand_icons.json").read_text(encoding="utf-8"))
        _icons_cache = {
            str(slug): {"title": str(v.get("title", slug)), "hex": str(v.get("hex", ""))}
            for slug, v in raw.items()
        }
    return _icons_cache


def _builtin_services() -> list[dict[str, Any]]:
    global _builtin_cache
    if _builtin_cache is None:
        raw = json.loads((_DATA_DIR / "services.json").read_text(encoding="utf-8"))
        _builtin_cache = list(raw["services"])
    return _builtin_cache


@dataclass
class Service:
    """Um serviço da biblioteca (embutido, possivelmente alterado, ou personalizado)."""

    key: str
    name: str
    aliases: list[str]
    login_url: str
    default_url: str
    icon: str
    color: str
    builtin: bool
    customized: bool = False


def _sort_key(service: Service) -> tuple[str, str, str]:
    return (normalize(service.name), service.name.casefold(), service.key)


class Catalog:
    """Biblioteca = serviços embutidos (com links alterados) + personalizados do cofre."""

    def __init__(
        self,
        custom_services: Iterable[Mapping[str, Any]] = (),
        url_overrides: Mapping[str, str] | None = None,
    ) -> None:
        icons = brand_icons()

        def color_of(slug: str) -> str:
            return icons.get(slug, {}).get("hex", "") if slug else ""

        overrides = dict(url_overrides or {})
        services: list[Service] = []
        self._builtin_keys: set[str] = set()
        for raw in _builtin_services():
            default = raw["login_url"]
            override = overrides.get(raw["key"])
            current = override if isinstance(override, str) and override else default
            services.append(
                Service(
                    key=raw["key"],
                    name=raw["name"],
                    aliases=list(raw.get("aliases", [])),
                    login_url=current,
                    default_url=default,
                    icon=raw.get("icon", ""),
                    color=color_of(raw.get("icon", "")),
                    builtin=True,
                    customized=current != default,
                )
            )
            self._builtin_keys.add(raw["key"])
        custom: list[Service] = []
        for raw in custom_services:
            slug = raw.get("icon", "") or ""
            custom.append(
                Service(
                    key=raw["key"],
                    name=raw["name"],
                    aliases=list(raw.get("aliases", [])),
                    login_url=raw["login_url"],
                    default_url=raw["login_url"],
                    icon=slug,
                    color=color_of(slug),
                    builtin=False,
                    customized=False,
                )
            )
        self._all = sorted(services + custom, key=_sort_key)
        self._by_key = {s.key: s for s in self._all}
        # personalizados primeiro: têm prioridade no match
        self._match_order = [s for s in self._all if not s.builtin] + [
            s for s in self._all if s.builtin
        ]

    def all(self) -> list[Service]:
        """Todos os serviços, em ordem alfabética."""
        return list(self._all)

    def get(self, key: str) -> Service | None:
        return self._by_key.get(key) if isinstance(key, str) else None

    def is_builtin(self, key: str) -> bool:
        return key in self._builtin_keys

    @staticmethod
    def _names(service: Service) -> list[str]:
        return [n for n in (normalize(service.name), *map(normalize, service.aliases)) if n]

    def match(self, name: str) -> Service | None:
        """Serviço cujo nome ou apelido, normalizado, é igual ao texto (personalizados primeiro)."""
        needle = normalize(name)
        if not needle:
            return None
        for service in self._match_order:
            if needle in self._names(service):
                return service
        return None

    def suggest(self, text: str, limit: int = 6) -> list[Service]:
        """Sugestões: prefixo do nome/apelido primeiro, depois "contém"; sem repetidos."""
        needle = normalize(text)
        if not needle or limit <= 0:
            return []
        prefix: list[Service] = []
        contains: list[Service] = []
        for service in self._all:
            names = self._names(service)
            if any(n.startswith(needle) for n in names):
                prefix.append(service)
            elif any(needle in n for n in names):
                contains.append(service)
        return (prefix + contains)[:limit]

    @staticmethod
    def icons() -> list[dict[str, str]]:
        """Ícones disponíveis: [{slug, title}] ordenados pelo título."""
        items = [{"slug": slug, "title": v["title"]} for slug, v in brand_icons().items()]
        return sorted(items, key=lambda i: (i["title"].casefold(), i["slug"]))
