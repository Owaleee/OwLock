"""Métodos de importar (CSV de outros gerenciadores) e exportar (CSV do OwLock) da Api.

Mixin: `class Api(TransferApiMixin, ...)`. Usa `_lock`, `_vault`, `_require`, `_catalog`,
`_find_category`, `_save_dialog` e `_open_dialog` da Api.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from owlock.core.errors import WrongPasswordError
from owlock.core.models import Category
from owlock.core.transfer import (
    SOURCE_LABELS,
    ImportFormatError,
    base_domain,
    export_csv,
    find_duplicates,
    host_of,
    parse_csv,
    to_public_preview,
)

MAX_CATEGORY_NAME = 24
MAX_CATEGORIES = 30


def _err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": code, "message": message}


def _chosen_path(chosen: Any) -> Path | None:
    if isinstance(chosen, (tuple, list)):
        chosen = chosen[0] if chosen else None
    if not chosen or not isinstance(chosen, (str, Path)):
        return None
    return Path(chosen)


class TransferApiMixin:
    _open_dialog: Any = None
    _pending_import: dict[str, Any] | None = None

    def _domain_lookup(self):
        """Função host -> nome do serviço no catálogo (pelo domínio do link de login)."""
        # por domínio, vence o serviço cujo link é o próprio domínio e, depois, o de nome mais curto
        # (google.com -> "Google", não "Gmail" nem "Google Drive")
        by_domain: dict[str, str] = {}
        services = [(host_of(s.login_url), s.name) for s in self._catalog().all()]  # type: ignore[attr-defined]
        for host, name in sorted(services, key=lambda hn: (hn[0] != base_domain(hn[0]), len(hn[1]))):
            if host:
                by_domain.setdefault(base_domain(host), name)

        def lookup(host: str) -> str | None:
            return by_domain.get(base_domain(host))

        return lookup

    # ---- importar ----
    def import_pick(self) -> dict[str, Any]:
        """Abre a janela para escolher o CSV, lê e devolve a prévia (sem senhas). Nada é salvo ainda."""
        with self._lock:  # type: ignore[attr-defined]
            err = self._require()  # type: ignore[attr-defined]
            if err:
                return err
            if self._open_dialog is None:
                return _err("open_failed", "Não foi possível abrir a janela para escolher o arquivo.")
        try:
            path = _chosen_path(self._open_dialog())
        except Exception:  # noqa: BLE001 - janela indisponível
            return _err("open_failed", "Não foi possível abrir a janela para escolher o arquivo.")
        if path is None:
            return _err("cancelled", "Importação cancelada.")
        return self._import_preview_file(str(path))

    def _import_preview_file(self, path: str) -> dict[str, Any]:
        """Lê o CSV indicado e prepara a importação (usado por import_pick e pelos testes)."""
        with self._lock:  # type: ignore[attr-defined]
            err = self._require()  # type: ignore[attr-defined]
            if err:
                return err
            vault = self._vault  # type: ignore[attr-defined]
            source_path = Path(path)
            try:
                if source_path.stat().st_size > 10 * 1024 * 1024:
                    return _err("too_large", "O arquivo é grande demais (máximo de 10 MB).")
                data = source_path.read_bytes()
            except OSError:
                return _err("read_failed", "Não foi possível ler o arquivo.")
            try:
                result = parse_csv(data, self._domain_lookup())
            except ImportFormatError as exc:
                return _err("invalid_format", str(exc))
            finally:
                data = b""
            duplicates = find_duplicates(result.entries, vault.entries)
            existing = {c.name.casefold() for c in vault.categories}
            new_categories = sorted(
                {c[:MAX_CATEGORY_NAME].strip() for c in result.categories if c.strip()},
                key=str.casefold,
            )
            new_categories = [c for c in new_categories if c.casefold() not in existing]
            token = secrets.token_hex(16)
            self._pending_import = {
                "token": token, "path": source_path, "result": result, "duplicates": duplicates,
            }
            dup_count = sum(duplicates)
            return {
                "ok": True,
                "token": token,
                "source": result.source,
                "source_label": SOURCE_LABELS.get(result.source, result.source),
                "file_name": source_path.name,
                "total": len(result.entries),
                "new": len(result.entries) - dup_count,
                "duplicates": dup_count,
                "skipped": result.skipped,
                "new_categories": new_categories,
                "items": to_public_preview(result, duplicates),
            }

    def import_confirm(self, token: str, include_duplicates: bool = False, delete_file: bool = False) -> dict[str, Any]:
        """Grava as contas da prévia num único salvamento. Pode apagar o CSV depois."""
        with self._lock:  # type: ignore[attr-defined]
            err = self._require()  # type: ignore[attr-defined]
            if err:
                self._pending_import = None
                return err
            pending = self._pending_import
            if not pending or not isinstance(token, str) or not secrets.compare_digest(token, pending["token"]):
                return _err("no_import", "A prévia expirou. Escolha o arquivo de novo.")
            vault = self._vault  # type: ignore[attr-defined]
            result = pending["result"]
            by_name = {c.name.casefold(): c for c in vault.categories}
            created: list[Category] = []
            chosen = []
            for entry, dup, cat_name in zip(result.entries, pending["duplicates"], result.categories):
                if dup and not include_duplicates:
                    continue
                name = cat_name[:MAX_CATEGORY_NAME].strip()
                if name:
                    category = by_name.get(name.casefold())
                    if category is None and len(vault.categories) + len(created) < MAX_CATEGORIES:
                        category = Category(name=name, color="gray", icon="star")
                        created.append(category)
                        by_name[name.casefold()] = category
                    if category is not None:
                        entry.category_id = category.id
                chosen.append(entry)
            if not chosen:
                self._pending_import = None
                return {"ok": True, "imported": 0, "deleted_file": False}
            try:
                vault.add_many(chosen, created)
            except OSError:
                return _err("save_failed", "Não foi possível salvar o cofre.")
            self._pending_import = None
            deleted = False
            if delete_file:
                try:
                    pending["path"].unlink()
                    deleted = True
                except OSError:
                    deleted = False
            return {"ok": True, "imported": len(chosen), "categories": len(created), "deleted_file": deleted}

    def import_cancel(self) -> dict[str, Any]:
        """Descarta a prévia guardada em memória."""
        with self._lock:  # type: ignore[attr-defined]
            self._pending_import = None
            return {"ok": True}

    # ---- exportar ----
    def export_vault(self, password: str) -> dict[str, Any]:
        """Confere a senha mestra e grava um CSV (texto puro) no lugar escolhido pelo usuário."""
        with self._lock:  # type: ignore[attr-defined]
            err = self._require()  # type: ignore[attr-defined]
            if err:
                return err
            vault = self._vault  # type: ignore[attr-defined]
            try:
                vault.verify_password(password if isinstance(password, str) else "")
            except WrongPasswordError:
                return _err("wrong_password", "Senha mestra incorreta.")
            if self._save_dialog is None:  # type: ignore[attr-defined]
                return _err("save_failed", "Não foi possível abrir a janela para salvar.")
            default_name = f"OwLock-exportacao-{datetime.now():%Y-%m-%d}.csv"
            try:
                target = _chosen_path(self._save_dialog(default_name))  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 - janela indisponível
                return _err("save_failed", "Não foi possível abrir a janela para salvar.")
            if target is None:
                return _err("cancelled", "Exportação cancelada.")
            if not target.suffix:
                target = target.with_name(target.name + ".csv")
            names = {c.id: c.name for c in vault.categories}
            content = export_csv(vault.entries, names)
            try:
                target.write_bytes(content.encode("utf-8"))
            except OSError:
                return _err("save_failed", "Não foi possível gravar o arquivo.")
            return {"ok": True, "path": str(target), "count": len(vault.entries)}
