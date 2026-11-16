"""Api: única ponte entre a interface (web) e o núcleo do cofre.

Toda resposta é um dict: sucesso ``{"ok": True, ...}``; erro
``{"ok": False, "error": "<código>", "message": "<texto>"}``.
Métodos públicos são expostos à interface; auxiliares começam com "_".
"""
from __future__ import annotations

import dataclasses
import threading
import time
from pathlib import Path
from typing import Any, Callable

from owlock.core import (
    CATEGORY_COLORS,
    CATEGORY_ICONS,
    Category,
    Entry,
    MIN_MASTER_PASSWORD_LENGTH,
    Vault,
    VaultCorruptedError,
    VaultExistsError,
    WrongPasswordError,
    generate_password,
)
from owlock.core.strength import password_strength

_FILTERS = ("all", "2fa", "attention")
_FIELDS = ("username", "password")
_ATTENTION_MAX_SCORE = 2
_MAX_CATEGORY_NAME = 24
_MAX_CATEGORIES = 30


class _PyperclipClipboard:
    """Adaptador sobre pyperclip (importado só quando usado)."""

    def copy(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)

    def paste(self) -> str:
        import pyperclip

        return pyperclip.paste()


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": code, "message": message}


def _locked() -> dict[str, Any]:
    return _error("locked", "O cofre está bloqueado.")


def _not_found() -> dict[str, Any]:
    return _error("not_found", "Conta não encontrada.")


class Api:
    """Ponte entre a interface e o núcleo. Thread-safe (RLock)."""

    def __init__(
        self,
        vault_path: Path,
        auto_lock_seconds: int = 300,
        clipboard: Any = None,
        clock: Callable[[], float] = time.monotonic,
        clear_after: int = 30,
        timer_factory: Callable[..., Any] = threading.Timer,
    ) -> None:
        self._path = Path(vault_path)
        self._auto_lock = auto_lock_seconds
        self._clipboard = clipboard if clipboard is not None else _PyperclipClipboard()
        self._clock = clock
        self._clear_after = clear_after
        self._timer_factory = timer_factory
        self._lock = threading.RLock()
        self._vault: Vault | None = None
        self._last_activity = 0.0
        self._timer: Any = None
        self._copied: str | None = None

    # ---- auxiliares (todos chamados com o lock já adquirido) ----
    def _seconds_left(self) -> int:
        if self._vault is None:
            return 0
        left = self._auto_lock - (self._clock() - self._last_activity)
        return max(0, int(left))

    def _expired(self) -> bool:
        return self._clock() - self._last_activity > self._auto_lock

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _clear_clipboard_if_ours(self) -> None:
        copied, self._copied = self._copied, None
        if copied is None:
            return
        try:
            if self._clipboard.paste() == copied:
                self._clipboard.copy("")
        except Exception:  # noqa: BLE001 - área de transferência indisponível
            pass

    def _do_lock(self) -> None:
        self._vault = None
        self._cancel_timer()
        self._clear_clipboard_if_ours()

    def _require(self) -> dict[str, Any] | None:
        """Exige cofre aberto e dentro do prazo; registra atividade."""
        if self._vault is None:
            return _locked()
        if self._expired():
            self._do_lock()
            return _locked()
        self._last_activity = self._clock()
        return None

    @staticmethod
    def _category_dict(category: Category) -> dict[str, Any]:
        return {
            "id": category.id,
            "name": category.name,
            "color": category.color,
            "color_hex": CATEGORY_COLORS.get(category.color, CATEGORY_COLORS["gray"]),
            "icon": category.icon,
        }

    def _category_summary(self, category: Category) -> dict[str, Any]:
        assert self._vault is not None
        out = self._category_dict(category)
        out["count"] = sum(1 for e in self._vault.entries if e.category_id == category.id)
        return out

    def _find_category(self, category_id: Any) -> Category | None:
        assert self._vault is not None
        for category in self._vault.categories:
            if category.id == category_id:
                return category
        return None

    def _summary(self, entry: Entry) -> dict[str, Any]:
        category = self._find_category(entry.category_id) if entry.category_id else None
        return {
            "id": entry.id,
            "service": entry.service,
            "username": entry.username,
            "has_2fa": bool(entry.has_2fa),
            "twofa_app": entry.twofa_app,
            "notes": entry.notes,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "password_length": len(entry.password),
            "strength": password_strength(entry.password),
            "category_id": entry.category_id if category is not None else "",
            "category": self._category_dict(category) if category is not None else None,
        }

    def _find(self, entry_id: Any) -> Entry | None:
        assert self._vault is not None
        for entry in self._vault.entries:
            if entry.id == entry_id:
                return entry
        return None

    def _on_clear_timer(self, token: Any) -> None:
        with self._lock:
            if self._timer is not token:
                return
            self._timer = None
            self._clear_clipboard_if_ours()

    # ---- estado ----
    def status(self) -> dict[str, Any]:
        """Estado atual. Não conta como atividade."""
        with self._lock:
            if self._vault is not None and self._expired():
                self._do_lock()
            return {
                "ok": True,
                "exists": self._path.exists(),
                "unlocked": self._vault is not None,
                "vault_path": str(self._path),
                "auto_lock_seconds": self._auto_lock,
                "seconds_left": self._seconds_left(),
            }

    def create_vault(self, password: str, confirm: str) -> dict[str, Any]:
        """Cria um cofre novo e o deixa aberto."""
        with self._lock:
            password = password if isinstance(password, str) else ""
            if len(password) < MIN_MASTER_PASSWORD_LENGTH:
                return _error(
                    "password_too_short",
                    f"A senha mestra deve ter ao menos {MIN_MASTER_PASSWORD_LENGTH} caracteres.",
                )
            if password != confirm:
                return _error("mismatch", "A confirmação não confere com a senha.")
            if self._path.exists():
                return _error("exists", "Já existe um cofre neste caminho.")
            try:
                vault = Vault.create(self._path, password)
            except VaultExistsError:
                return _error("exists", "Já existe um cofre neste caminho.")
            except ValueError as exc:
                return _error("password_too_short", str(exc))
            except OSError:
                return _error("save_failed", "Não foi possível gravar o cofre.")
            self._vault = vault
            self._last_activity = self._clock()
            return {"ok": True}

    def unlock(self, password: str) -> dict[str, Any]:
        """Abre o cofre com a senha mestra."""
        with self._lock:
            try:
                vault = Vault.open(self._path, password if isinstance(password, str) else "")
            except FileNotFoundError:
                return _error("not_found", "Nenhum cofre encontrado neste caminho.")
            except WrongPasswordError:
                return _error("wrong_password", "Senha mestra incorreta.")
            except VaultCorruptedError:
                bak = self._path.with_name(self._path.name + ".bak")
                return _error(
                    "corrupted",
                    f"O arquivo do cofre está corrompido. Uma cópia anterior pode estar em: {bak}",
                )
            except OSError:
                return _error("open_failed", "Não foi possível ler o arquivo do cofre.")
            self._vault = vault
            self._last_activity = self._clock()
            return {"ok": True}

    def lock(self) -> dict[str, Any]:
        """Bloqueia o cofre."""
        with self._lock:
            self._do_lock()
            return {"ok": True}

    def touch(self) -> dict[str, Any]:
        """Registra atividade do usuário."""
        with self._lock:
            err = self._require()
            if err:
                return err
            return {"ok": True, "seconds_left": self._seconds_left()}

    # ---- contas ----
    def list_entries(
        self, query: str = "", filter: str = "all", category: str = ""
    ) -> dict[str, Any]:
        """Lista contas (sem senhas), com busca, filtro e categoria."""
        with self._lock:
            err = self._require()
            if err:
                return err
            if filter not in _FILTERS:
                return _error("invalid_filter", "Filtro inválido.")
            vault = self._vault
            assert vault is not None
            category = category if isinstance(category, str) else ""
            if category not in ("", "none") and self._find_category(category) is None:
                return _error("invalid_category", "Categoria inválida.")
            everything = vault.entries
            known = {c.id for c in vault.categories}
            stats = {
                "total": len(everything),
                "with_2fa": sum(1 for e in everything if e.has_2fa),
                "attention": sum(
                    1 for e in everything
                    if password_strength(e.password)["score"] <= _ATTENTION_MAX_SCORE
                ),
                "uncategorized": sum(1 for e in everything if e.category_id not in known),
            }
            found = vault.search(query if isinstance(query, str) else "")
            if category == "none":
                found = [e for e in found if e.category_id not in known]
            elif category:
                found = [e for e in found if e.category_id == category]
            if filter == "2fa":
                found = [e for e in found if e.has_2fa]
            elif filter == "attention":
                found = [
                    e for e in found
                    if password_strength(e.password)["score"] <= _ATTENTION_MAX_SCORE
                ]
            found.sort(key=lambda e: e.service.casefold())
            return {"ok": True, "entries": [self._summary(e) for e in found], "stats": stats}

    def get_entry(self, id: str) -> dict[str, Any]:
        """Devolve uma conta (sem a senha)."""
        with self._lock:
            err = self._require()
            if err:
                return err
            entry = self._find(id)
            if entry is None:
                return _not_found()
            return {"ok": True, "entry": self._summary(entry)}

    def reveal_password(self, id: str) -> dict[str, Any]:
        """Devolve a senha de uma conta."""
        with self._lock:
            err = self._require()
            if err:
                return err
            entry = self._find(id)
            if entry is None:
                return _not_found()
            return {"ok": True, "password": entry.password}

    def copy_field(self, id: str, field: str) -> dict[str, Any]:
        """Copia usuário ou senha e agenda a limpeza da área de transferência."""
        with self._lock:
            err = self._require()
            if err:
                return err
            entry = self._find(id)
            if entry is None:
                return _not_found()
            if field not in _FIELDS:
                return _error("invalid_field", "Campo inválido.")
            text = entry.username if field == "username" else entry.password
            return self._copy_with_timer(text)

    def copy_text(self, text: str) -> dict[str, Any]:
        """Copia um texto avulso (ex.: senha do gerador) com a mesma limpeza automática."""
        with self._lock:
            err = self._require()
            if err:
                return err
            if not isinstance(text, str) or not text or len(text) > 1024:
                return _error("invalid_text", "Texto inválido para copiar.")
            return self._copy_with_timer(text)

    def _copy_with_timer(self, text: str) -> dict[str, Any]:
        """Copia e agenda a limpeza (chamado com o lock adquirido)."""
        try:
            self._clipboard.copy(text)
        except Exception:  # noqa: BLE001
            return _error("clipboard_failed", "Não foi possível acessar a área de transferência.")
        self._cancel_timer()
        self._copied = text
        timer = self._timer_factory(self._clear_after, lambda: self._on_clear_timer(timer))
        timer.daemon = True
        self._timer = timer
        timer.start()
        return {"ok": True, "clear_in": self._clear_after}

    def save_entry(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria (sem id) ou edita (com id) uma conta."""
        with self._lock:
            err = self._require()
            if err:
                return err
            vault = self._vault
            assert vault is not None
            if not isinstance(data, dict):
                return _error("service_required", "Informe o nome do serviço.")
            service = str(data.get("service") or "").strip()
            if not service:
                return _error("service_required", "Informe o nome do serviço.")
            has_2fa = bool(data.get("has_2fa"))
            fields: dict[str, Any] = {
                "service": service,
                "username": str(data.get("username") or ""),
                "has_2fa": has_2fa,
                "twofa_app": str(data.get("twofa_app") or "") if has_2fa else "",
                "notes": str(data.get("notes") or ""),
            }
            category_id = data.get("category_id")
            category_id = category_id if isinstance(category_id, str) else ""
            if category_id and self._find_category(category_id) is None:
                return _error("invalid_category", "Categoria inválida.")
            fields["category_id"] = category_id
            entry_id = data.get("id")
            try:
                if not entry_id:
                    saved = vault.add(Entry(password=str(data.get("password") or ""), **fields))
                else:
                    current = self._find(entry_id)
                    if current is None:
                        return _not_found()
                    password = data.get("password")
                    fields["password"] = current.password if password is None else str(password)
                    saved = vault.update(dataclasses.replace(current, **fields))
            except KeyError:
                return _not_found()
            except OSError:
                return _error("save_failed", "Não foi possível salvar o cofre.")
            return {"ok": True, "entry": self._summary(saved)}

    def delete_entry(self, id: str) -> dict[str, Any]:
        """Remove uma conta."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            try:
                self._vault.delete(id)
            except KeyError:
                return _not_found()
            except OSError:
                return _error("save_failed", "Não foi possível salvar o cofre.")
            return {"ok": True}

    # ---- categorias ----
    def list_categories(self) -> dict[str, Any]:
        """Lista as categorias na ordem salva, com a contagem de contas."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            return {
                "ok": True,
                "categories": [self._category_summary(c) for c in self._vault.categories],
            }

    def save_category(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria (sem id) ou edita (com id) uma categoria."""
        with self._lock:
            err = self._require()
            if err:
                return err
            vault = self._vault
            assert vault is not None
            if not isinstance(data, dict):
                return _error("name_required", "Informe o nome da categoria.")
            name = str(data.get("name") or "").strip()
            if not name:
                return _error("name_required", "Informe o nome da categoria.")
            if len(name) > _MAX_CATEGORY_NAME:
                return _error(
                    "name_too_long",
                    f"O nome deve ter no máximo {_MAX_CATEGORY_NAME} caracteres.",
                )
            color, icon = data.get("color"), data.get("icon")
            if not isinstance(color, str) or color not in CATEGORY_COLORS:
                return _error("invalid_color", "Cor inválida.")
            if not isinstance(icon, str) or icon not in CATEGORY_ICONS:
                return _error("invalid_icon", "Ícone inválido.")
            category_id = data.get("id")
            current = None
            if category_id:
                current = self._find_category(category_id)
                if current is None:
                    return _error("not_found", "Categoria não encontrada.")
            folded = name.casefold()
            if any(
                c.name.casefold() == folded and c is not current
                for c in vault.categories
            ):
                return _error("name_exists", "Já existe uma categoria com esse nome.")
            if current is None and len(vault.categories) >= _MAX_CATEGORIES:
                return _error(
                    "too_many", f"O limite é de {_MAX_CATEGORIES} categorias."
                )
            try:
                if current is None:
                    saved = vault.add_category(Category(name=name, color=color, icon=icon))
                else:
                    saved = vault.update_category(
                        dataclasses.replace(current, name=name, color=color, icon=icon)
                    )
            except KeyError:
                return _error("not_found", "Categoria não encontrada.")
            except OSError:
                return _error("save_failed", "Não foi possível salvar o cofre.")
            return {"ok": True, "category": self._category_summary(saved)}

    def delete_category(self, id: str) -> dict[str, Any]:
        """Remove uma categoria; as contas dela ficam sem categoria."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            try:
                moved = self._vault.delete_category(id)
            except KeyError:
                return _error("not_found", "Categoria não encontrada.")
            except OSError:
                return _error("save_failed", "Não foi possível salvar o cofre.")
            return {"ok": True, "moved": moved}

    def category_options(self) -> dict[str, Any]:
        """Cores e ícones disponíveis. Não exige cofre aberto."""
        return {
            "ok": True,
            "colors": [{"key": k, "hex": h} for k, h in CATEGORY_COLORS.items()],
            "icons": list(CATEGORY_ICONS),
        }

    # ---- senhas ----
    def generate_password(
        self,
        length: int = 20,
        upper: bool = True,
        lower: bool = True,
        digits: bool = True,
        symbols: bool = True,
    ) -> dict[str, Any]:
        """Gera uma senha forte. Não exige cofre aberto."""
        try:
            password = generate_password(length, upper, lower, digits, symbols)
        except (ValueError, TypeError) as exc:
            return _error("invalid_options", str(exc))
        return {"ok": True, "password": password, "strength": password_strength(password)}

    def check_strength(self, password: str) -> dict[str, Any]:
        """Avalia a força de uma senha. Não exige cofre aberto."""
        result = password_strength(password)
        return {"ok": True, "score": result["score"], "label": result["label"]}

    def change_master_password(self, current: str, new: str, confirm: str) -> dict[str, Any]:
        """Troca a senha mestra."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            current = current if isinstance(current, str) else ""
            new = new if isinstance(new, str) else ""
            if new != confirm:
                return _error("mismatch", "A confirmação não confere com a nova senha.")
            if len(new) < MIN_MASTER_PASSWORD_LENGTH:
                return _error(
                    "password_too_short",
                    f"A senha mestra deve ter ao menos {MIN_MASTER_PASSWORD_LENGTH} caracteres.",
                )
            if new == current:
                return _error("same_password", "A nova senha deve ser diferente da atual.")
            try:
                self._vault.change_master_password(current, new)
            except WrongPasswordError:
                return _error("wrong_password", "Senha mestra atual incorreta.")
            except ValueError as exc:
                return _error("password_too_short", str(exc))
            except OSError:
                return _error("save_failed", "Não foi possível salvar o cofre.")
            return {"ok": True}

    def shutdown(self) -> dict[str, Any]:
        """Encerra: limpa a área de transferência (se for nossa) e bloqueia."""
        with self._lock:
            self._do_lock()
            return {"ok": True}
