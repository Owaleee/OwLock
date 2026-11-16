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
    def _summary(entry: Entry) -> dict[str, Any]:
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
    def list_entries(self, query: str = "", filter: str = "all") -> dict[str, Any]:
        """Lista contas (sem senhas), com busca e filtro."""
        with self._lock:
            err = self._require()
            if err:
                return err
            if filter not in _FILTERS:
                return _error("invalid_filter", "Filtro inválido.")
            vault = self._vault
            assert vault is not None
            everything = vault.entries
            stats = {
                "total": len(everything),
                "with_2fa": sum(1 for e in everything if e.has_2fa),
                "attention": sum(
                    1 for e in everything
                    if password_strength(e.password)["score"] <= _ATTENTION_MAX_SCORE
                ),
            }
            found = vault.search(query if isinstance(query, str) else "")
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
