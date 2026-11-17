"""Importar contas de arquivos CSV de outros gerenciadores e exportar o cofre em CSV.

Formatos reconhecidos pelo cabeçalho (sem diferenciar maiúsculas):
- Chrome, Edge e Gerenciador de Senhas do Google: name, url, username, password[, note]
- Bitwarden: folder, favorite, type, name, notes, ..., login_uri, login_username, login_password, login_totp
- Firefox: url, username, password, httpRealm, formActionOrigin, guid, ...
- OwLock (exportação deste app): service, url, username, password, notes, has_2fa, twofa_app, category, favorite

Nada aqui toca em disco: quem chama lê/grava os arquivos. O núcleo só converte texto <-> Entry.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from owlock.core.models import Entry

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 20000

SOURCE_LABELS = {
    "chrome": "Chrome, Edge ou Google",
    "bitwarden": "Bitwarden",
    "firefox": "Firefox",
    "owlock": "OwLock",
}

OWLOCK_COLUMNS = ["service", "url", "username", "password", "notes", "has_2fa", "twofa_app", "category", "favorite"]

_TRUE = {"1", "true", "sim", "yes", "y", "s", "x"}
_TWO_LEVEL = {"com.br", "net.br", "org.br", "gov.br", "edu.br", "co.uk", "org.uk", "com.au", "co.jp", "com.ar", "com.mx"}


class ImportFormatError(ValueError):
    """O arquivo não é um CSV reconhecido."""


@dataclass
class ImportResult:
    source: str
    entries: list[Entry] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)  # nome da categoria de cada entrada ("" = nenhuma)
    skipped: int = 0  # linhas sem serviço, sem login e sem senha (ou que não são de login)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFormatError("Não foi possível ler o arquivo (codificação desconhecida).")


def _detect(columns: set[str]) -> str:
    if {"login_username", "login_password"} <= columns:
        return "bitwarden"
    if {"service", "username", "password"} <= columns:
        return "owlock"
    if {"url", "username", "password", "guid"} <= columns or {"url", "username", "password", "httprealm"} <= columns:
        return "firefox"
    if {"url", "username", "password"} <= columns:
        return "chrome"
    raise ImportFormatError(
        "Formato não reconhecido. Use o CSV exportado pelo Chrome, Edge, Google, Bitwarden, Firefox ou OwLock."
    )


def host_of(url: str) -> str:
    """Host do endereço, sem "www." (vazio se não for http/https)."""
    text = (url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    if parts.scheme not in ("http", "https"):
        return ""
    host = (parts.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def base_domain(host: str) -> str:
    """Domínio principal: accounts.google.com -> google.com; www.itau.com.br -> itau.com.br."""
    labels = [p for p in host.lower().split(".") if p]
    if len(labels) <= 2:
        return ".".join(labels)
    if ".".join(labels[-2:]) in _TWO_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _clean_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if host_of(url) == "":
        return ""  # android://, chrome://, endereços sem host: não servem para abrir o site
    return url if "://" in url else "https://" + url


def _service_name(name: str, url: str, lookup: Callable[[str], str | None] | None) -> str:
    """Nome amigável: nome do catálogo pelo domínio, senão o nome informado, senão o domínio."""
    host = host_of(url)
    if lookup is not None and host:
        found = lookup(host)
        if found:
            return found
    name = (name or "").strip()
    if name:
        return name
    return host or ""


def _rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        raise ImportFormatError("O arquivo está vazio.") from None
    except csv.Error:
        raise ImportFormatError("O arquivo não é um CSV válido.") from None
    names = [h.strip().lower() for h in header]
    rows: list[dict[str, str]] = []
    try:
        for raw in reader:
            if not any(cell.strip() for cell in raw):
                continue
            rows.append({names[i]: raw[i] if i < len(raw) else "" for i in range(len(names))})
            if len(rows) > MAX_IMPORT_ROWS:
                raise ImportFormatError(f"O arquivo tem mais de {MAX_IMPORT_ROWS} linhas.")
    except csv.Error:
        raise ImportFormatError("O arquivo não é um CSV válido.") from None
    return names, rows


def parse_csv(data: bytes, lookup: Callable[[str], str | None] | None = None) -> ImportResult:
    """Converte o CSV em entradas novas (sem salvar). `lookup(host)` devolve o nome do serviço no catálogo."""
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportFormatError("O arquivo é grande demais (máximo de 10 MB).")
    names, rows = _rows(_decode(data))
    source = _detect(set(names))
    result = ImportResult(source=source)
    for row in rows:
        g = lambda key: (row.get(key) or "").strip()  # noqa: E731
        category = ""
        has_2fa, twofa_app, favorite = False, "", False
        if source == "bitwarden":
            if g("type") and g("type").lower() != "login":
                result.skipped += 1
                continue
            url = g("login_uri").split(",")[0].strip()
            name, username, password, notes = g("name"), g("login_username"), row.get("login_password") or "", g("notes")
            category = g("folder")
            favorite = g("favorite").lower() in _TRUE
            if g("login_totp"):
                has_2fa, twofa_app = True, "Bitwarden"
        elif source == "owlock":
            url = g("url")
            name, username, password, notes = g("service"), g("username"), row.get("password") or "", g("notes")
            has_2fa = g("has_2fa").lower() in _TRUE
            twofa_app = g("twofa_app") if has_2fa else ""
            category = g("category")
            favorite = g("favorite").lower() in _TRUE
        else:  # chrome / firefox
            url = g("url")
            name = g("name") if source == "chrome" else ""
            username, password = g("username"), row.get("password") or ""
            notes = g("note") or g("notes")
        url = _clean_url(url)
        service = name if source in ("owlock", "bitwarden") and name else _service_name(name, url, lookup)
        if not service and not username and not password:
            result.skipped += 1
            continue
        result.entries.append(
            Entry(
                service=service or username or "Sem nome",
                username=username,
                password=password,
                url=url,
                notes=notes,
                has_2fa=has_2fa,
                twofa_app=twofa_app,
                favorite=favorite,
            )
        )
        result.categories.append(category)
    return result


def _key(entry: Entry) -> tuple[str, str, str]:
    where = base_domain(host_of(entry.url)) if entry.url else entry.service.strip().casefold()
    return (where, entry.username.strip().casefold(), entry.password)


def find_duplicates(candidates: Iterable[Entry], existing: Iterable[Entry]) -> list[bool]:
    """Para cada candidata: True se já existe no cofre (mesmo site/serviço, login e senha) ou repete no arquivo."""
    seen = {_key(e) for e in existing}
    # contas antigas sem site: compara também pelo nome do serviço
    seen |= {(e.service.strip().casefold(), e.username.strip().casefold(), e.password) for e in existing}
    out: list[bool] = []
    for entry in candidates:
        keys = {_key(entry), (entry.service.strip().casefold(), entry.username.strip().casefold(), entry.password)}
        dup = bool(keys & seen)
        out.append(dup)
        seen |= keys
    return out


def export_csv(entries: Iterable[Entry], category_names: dict[str, str] | None = None) -> str:
    """CSV no formato do OwLock (o próprio OwLock importa de volta). Contém as senhas em texto puro."""
    names = category_names or {}
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(OWLOCK_COLUMNS)
    for e in sorted(entries, key=lambda x: (x.service.casefold(), x.username.casefold())):
        writer.writerow([
            e.service, e.url, e.username, e.password, e.notes,
            "sim" if e.has_2fa else "", e.twofa_app if e.has_2fa else "",
            names.get(e.category_id, ""), "sim" if e.favorite else "",
        ])
    return buffer.getvalue()


def to_public_preview(result: ImportResult, duplicates: list[bool], limit: int = 200) -> list[dict[str, Any]]:
    """Linhas para a prévia na interface — nunca inclui a senha."""
    return [
        {"service": e.service, "username": e.username, "host": host_of(e.url), "duplicate": dup,
         "has_password": bool(e.password), "category": cat}
        for e, dup, cat in list(zip(result.entries, duplicates, result.categories))[:limit]
    ]
