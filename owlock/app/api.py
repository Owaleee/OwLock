"""Api: única ponte entre a interface (web) e o núcleo do cofre.

Toda resposta é um dict: sucesso ``{"ok": True, ...}``; erro
``{"ok": False, "error": "<código>", "message": "<texto>"}``.
Métodos públicos são expostos à interface; auxiliares começam com "_".
"""
from __future__ import annotations

import dataclasses
import html
import re
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from owlock import __version__
from owlock.core import (
    AUTO_LOCK_OPTIONS,
    CLIPBOARD_OPTIONS,
    Settings,
    CATEGORY_COLORS,
    CATEGORY_ICONS,
    Category,
    Entry,
    InvalidSecretKeyError,
    MIN_MASTER_PASSWORD_LENGTH,
    MigrationError,
    SecretKeyRequiredError,
    SecretKeyStore,
    Vault,
    VaultCorruptedError,
    VaultExistsError,
    WrongPasswordError,
    WrongSecretKeyError,
    default_store,
    generate_password,
)
from owlock.core.catalog import Catalog, Service, brand_icons, icon_url, normalize
from owlock.core.strength import password_strength

_FILTERS = ("all", "2fa", "attention")
_FIELDS = ("username", "password")
_ATTENTION_MAX_SCORE = 2
_MAX_CATEGORY_NAME = 24
_MAX_CATEGORIES = 30
_MAX_URL = 2048
_MAX_SERVICE_NAME = 40
_MAX_ALIASES = 10
_MAX_CUSTOM_SERVICES = 200
_RECOMMENDED_AUTO_LOCK = 5
_RECOMMENDED_CLIPBOARD = 30
# "esquema:" que não seja "host:porta" (ex.: javascript:, mailto:, file:, ftp://)
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:(?!\d+(?:[/?#]|$))")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _seconds_label(total: int) -> str:
    minutes, seconds = divmod(total, 60)
    parts = []
    if minutes:
        parts.append(_plural(minutes, "minuto", "minutos"))
    if seconds or not parts:
        parts.append(_plural(seconds, "segundo", "segundos"))
    return " e ".join(parts)


def _valid_http_url(url: str) -> bool:
    """True para URL http/https com host, sem espaços/controles, até 2048 caracteres."""
    if not url or len(url) > _MAX_URL:
        return False
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        return False
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - valida a porta
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def _normalize_url(raw: str) -> str | None:
    """Normaliza a URL da conta: "" se vazia; None se inválida."""
    url = raw.strip()
    if not url:
        return ""
    if len(url) > _MAX_URL:
        return None
    if _SCHEME_RE.match(url) is None:
        if url.startswith("//"):
            return None
        url = "https://" + url
    return url if _valid_http_url(url) else None


_KIT_DEFAULT_NAME = "OwLock-Kit-de-emergencia.html"

_KIT_CSS = """
@page { size: A4; margin: 18mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #111; background: #fff;
       margin: 0; padding: 24px; line-height: 1.5; font-size: 14px; }
.page { max-width: 170mm; margin: 0 auto; }
.logo { font-size: 26px; font-weight: 700; letter-spacing: 0.5px; }
.logo span { color: #0a7d5a; }
h1 { font-size: 22px; margin: 6px 0 2px; }
.date { color: #555; margin: 0 0 18px; }
.box { border: 2px solid #111; border-radius: 10px; padding: 16px 18px; margin: 16px 0; }
.label { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #444; margin: 0 0 6px; }
.key { font-family: "Consolas", "Courier New", monospace; font-size: 24px; font-weight: 700;
       letter-spacing: 1px; word-break: break-all; margin: 0; }
.line { font-family: "Consolas", "Courier New", monospace; font-size: 16px; margin: 0; }
.path { font-family: "Consolas", "Courier New", monospace; font-size: 13px; word-break: break-all; margin: 0; }
h2 { font-size: 16px; margin: 22px 0 6px; }
ol { padding-left: 20px; margin: 0; }
li { margin-bottom: 6px; }
.warn { border: 2px solid #b00020; background: #fff3f3; border-radius: 10px; padding: 12px 16px; margin-top: 20px;
        color: #7a0016; font-weight: 600; }
@media print { body { padding: 0; } }
"""


def _kit_html(secret_key: str, vault_id: str, vault_path: str, date_text: str) -> str:
    """HTML autossuficiente do Kit de emergência (todos os valores passam por html.escape)."""
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kit de emergência do OwLock</title>
<style>{_KIT_CSS}</style>
</head>
<body>
<div class="page">
<div class="logo">Ow<span>Lock</span></div>
<h1>Kit de emergência do OwLock</h1>
<p class="date">Gerado em {e(date_text)}</p>

<div class="box">
<p class="label">Chave Secreta</p>
<p class="key">{e(secret_key)}</p>
</div>

<div class="box">
<p class="label">Senha mestra (escreva à mão)</p>
<p class="line">Senha mestra: ______________________________</p>
</div>

<div class="box">
<p class="label">Cofre</p>
<p class="path">{e(vault_path)}</p>
<p class="path">Identificador: {e(vault_id)}</p>
</div>

<h2>Como recuperar seu cofre</h2>
<ol>
<li>Instale o OwLock no computador novo e copie o arquivo do cofre para ele.</li>
<li>Abra o OwLock e digite a senha mestra.</li>
<li>Quando o OwLock pedir, digite a Chave Secreta acima. Maiúsculas, minúsculas, espaços e hífens não importam.</li>
<li>Pronto: a Chave Secreta fica guardada no novo computador e não será pedida de novo.</li>
</ol>

<div class="warn">Guarde esta folha em um local seguro (por exemplo, em um cofre ou gaveta trancada).
Nunca envie a Chave Secreta por mensagem, e-mail ou foto. Sem a Chave Secreta e a senha mestra, ninguém consegue abrir o cofre, nem nós.</div>
</div>
</body>
</html>
"""


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
        url_opener: Callable[[str], Any] | None = None,
        store: SecretKeyStore | None = None,
        save_dialog: Callable[[str], str | None] | None = None,
        kdf_params: dict[str, int] | None = None,
    ) -> None:
        self._path = Path(vault_path)
        self._store_obj = store
        self._save_dialog = save_dialog
        self._kdf_params = dict(kdf_params) if kdf_params is not None else None
        self._v1_backup: Path | None = None
        self._auto_lock = auto_lock_seconds
        self._clipboard = clipboard if clipboard is not None else _PyperclipClipboard()
        self._clock = clock
        self._clear_after = clear_after
        self._timer_factory = timer_factory
        self._url_opener = url_opener if url_opener is not None else webbrowser.open
        self._lock = threading.RLock()
        self._vault: Vault | None = None
        self._last_activity = 0.0
        self._timer: Any = None
        self._copied: str | None = None

    @property
    def _store(self) -> SecretKeyStore:
        if self._store_obj is None:
            self._store_obj = default_store()
        return self._store_obj

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

    def _apply_settings(self) -> None:
        """Aplica os ajustes do cofre aberto (chamado com o lock adquirido)."""
        assert self._vault is not None
        self._auto_lock = self._vault.settings.auto_lock_minutes * 60
        self._clear_after = self._vault.settings.clipboard_clear_seconds

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

    def _catalog(self) -> Catalog:
        assert self._vault is not None
        services = self._vault.services
        return Catalog(services["custom"], services["overrides"])

    @staticmethod
    def _service_dict(service: Service) -> dict[str, Any]:
        return {
            "key": service.key,
            "name": service.name,
            "aliases": list(service.aliases),
            "login_url": service.login_url,
            "default_url": service.default_url,
            "icon": service.icon,
            "icon_url": icon_url(service.icon),
            "color": service.color or None,
            "builtin": service.builtin,
            "customized": service.customized,
        }

    def _summary(self, entry: Entry, catalog: Catalog | None = None) -> dict[str, Any]:
        catalog = catalog if catalog is not None else self._catalog()
        icons = brand_icons()
        recognized = catalog.match(entry.service)
        if entry.icon == "none":
            slug = ""
        elif entry.icon:
            slug = entry.icon
        else:
            slug = recognized.icon if recognized is not None else ""
        if slug not in icons:
            slug = ""
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
            "url": entry.url,
            "history_count": len(entry.password_history),
            "icon": entry.icon,
            "icon_url": icon_url(slug),
            "icon_color": icons[slug]["hex"] or None if slug else None,
            "service_key": recognized.key if recognized is not None else None,
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
            format_version: int | None = None
            secret_key_required = False
            if self._path.exists():
                try:
                    head = Vault.peek(self._path)
                    format_version = head["version"]
                    if format_version == 2:
                        try:
                            secret_key_required = self._store.get(head["vault_id"]) is None
                        except Exception:  # noqa: BLE001 - chaveiro indisponível
                            secret_key_required = True
                except (OSError, VaultCorruptedError):
                    format_version = None
            return {
                "ok": True,
                "exists": self._path.exists(),
                "unlocked": self._vault is not None,
                "vault_path": str(self._path),
                "auto_lock_seconds": self._auto_lock,
                "clipboard_clear_seconds": self._clear_after,
                "seconds_left": self._seconds_left(),
                "app_version": __version__,
                "format_version": format_version,
                "secret_key_required": secret_key_required,
                "key_storage": self._store.description,
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
                vault = Vault.create(self._path, password, self._store, kdf_params=self._kdf_params)
            except VaultExistsError:
                return _error("exists", "Já existe um cofre neste caminho.")
            except ValueError as exc:
                return _error("password_too_short", str(exc))
            except OSError:
                return _error("save_failed", "Não foi possível gravar o cofre.")
            secret_key = vault.secret_key_formatted
            vault.forget_secret_key_display()
            self._vault = vault
            self._apply_settings()
            self._last_activity = self._clock()
            return {"ok": True, "secret_key": secret_key}

    def unlock(self, password: str, secret_key: str | None = None) -> dict[str, Any]:
        """Abre o cofre com a senha mestra (e a Chave Secreta, se este aparelho não a tiver)."""
        with self._lock:
            if not isinstance(secret_key, str) or not secret_key.strip():
                secret_key = None
            try:
                vault = Vault.open(
                    self._path,
                    password if isinstance(password, str) else "",
                    self._store,
                    secret_key,
                )
            except FileNotFoundError:
                return _error("not_found", "Nenhum cofre encontrado neste caminho.")
            except WrongPasswordError:
                return _error("wrong_password", "Senha mestra incorreta.")
            except SecretKeyRequiredError:
                return _error(
                    "secret_key_required",
                    "Este cofre foi criado em outro computador. Digite a Chave Secreta do seu Kit de emergência.",
                )
            except WrongSecretKeyError:
                return _error("wrong_secret_key", "Chave Secreta incorreta para este cofre.")
            except InvalidSecretKeyError:
                return _error("invalid_secret_key", "Chave Secreta inválida: confira os caracteres.")
            except MigrationError:
                return _error(
                    "migration_failed",
                    "Não foi possível atualizar o cofre para o formato novo. Nada foi alterado.",
                )
            except VaultCorruptedError:
                bak = self._path.with_name(self._path.name + ".bak")
                return _error(
                    "corrupted",
                    f"O arquivo do cofre está corrompido. Uma cópia anterior pode estar em: {bak}",
                )
            except OSError:
                return _error("open_failed", "Não foi possível ler o arquivo do cofre.")
            result: dict[str, Any] = {"ok": True, "migrated": bool(vault.migrated)}
            if vault.migrated:
                self._v1_backup = vault.v1_backup_path
                result["v1_backup_path"] = str(vault.v1_backup_path)
                result["secret_key"] = vault.secret_key_formatted  # para a tela do Kit
                vault.forget_secret_key_display()
            if not vault.secret_key_persisted:
                result["key_save_failed"] = True
            self._vault = vault
            self._apply_settings()
            self._last_activity = self._clock()
            return result

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

    # ---- Chave Secreta e Kit de emergência ----
    def emergency_kit(self, password: str) -> dict[str, Any]:
        """Revela a Chave Secreta (exige cofre aberto e a senha mestra)."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            try:
                secret = self._vault.reveal_secret_key(password if isinstance(password, str) else "")
            except WrongPasswordError:
                return _error("wrong_password", "Senha mestra incorreta.")
            return {
                "ok": True,
                "secret_key": secret,
                "vault_id": self._vault.vault_id,
                "vault_path": str(self._path),
                "key_storage": self._store.description,
            }

    def save_emergency_kit(self, password: str) -> dict[str, Any]:
        """Grava o Kit de emergência (HTML para imprimir) no lugar escolhido pelo usuário."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            try:
                secret = self._vault.reveal_secret_key(password if isinstance(password, str) else "")
            except WrongPasswordError:
                return _error("wrong_password", "Senha mestra incorreta.")
            if self._save_dialog is None:
                return _error("save_failed", "Não foi possível abrir a janela para salvar.")
            try:
                chosen = self._save_dialog(_KIT_DEFAULT_NAME)
            except Exception:  # noqa: BLE001 - janela indisponível
                return _error("save_failed", "Não foi possível abrir a janela para salvar.")
            if isinstance(chosen, (tuple, list)):
                chosen = chosen[0] if chosen else None
            if not chosen or not isinstance(chosen, (str, Path)):
                return _error("cancelled", "Salvamento cancelado.")
            target = Path(chosen)
            if not target.suffix:
                target = target.with_name(target.name + ".html")
            content = _kit_html(
                secret,
                self._vault.vault_id,
                str(self._path),
                datetime.now().strftime("%d/%m/%Y"),
            )
            try:
                target.write_bytes(content.encode("utf-8"))
            except OSError:
                return _error("save_failed", "Não foi possível gravar o arquivo do Kit.")
            return {"ok": True, "path": str(target)}

    def delete_v1_backup(self) -> dict[str, Any]:
        """Apaga a cópia do cofre antigo criada pela migração desta sessão."""
        with self._lock:
            err = self._require()
            if err:
                return err
            backup = self._v1_backup
            if backup is None or not backup.is_file():
                self._v1_backup = None
                return _error("not_found", "Cópia do cofre antigo não encontrada.")
            try:
                backup.unlink()
            except OSError:
                return _error("delete_failed", "Não foi possível apagar a cópia do cofre antigo.")
            self._v1_backup = None
            return {"ok": True}

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
            catalog = self._catalog()
            return {
                "ok": True,
                "entries": [self._summary(e, catalog) for e in found],
                "stats": stats,
            }

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
            raw_url = data.get("url")
            url = _normalize_url(raw_url) if isinstance(raw_url, str) else ("" if not raw_url else None)
            if url is None:
                return _error("invalid_url", "Endereço do site inválido. Use http:// ou https://.")
            fields["url"] = url
            category_id = data.get("category_id")
            category_id = category_id if isinstance(category_id, str) else ""
            if category_id and self._find_category(category_id) is None:
                return _error("invalid_category", "Categoria inválida.")
            fields["category_id"] = category_id
            icon = data.get("icon")
            if icon is not None:
                if not isinstance(icon, str) or (icon not in ("", "none") and icon not in brand_icons()):
                    return _error("invalid_icon", "Ícone inválido.")
                fields["icon"] = icon
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

    # ---- histórico e site ----
    def get_password_history(self, id: str) -> dict[str, Any]:
        """Datas e força das senhas antigas (nunca as senhas)."""
        with self._lock:
            err = self._require()
            if err:
                return err
            entry = self._find(id)
            if entry is None:
                return _not_found()
            return {
                "ok": True,
                "created_at": entry.created_at,
                "history": [
                    {
                        "index": n,
                        "changed_at": item["changed_at"],
                        "length": len(item["password"]),
                        "strength": password_strength(item["password"]),
                    }
                    for n, item in enumerate(entry.password_history)
                ],
            }

    def _history_password(self, id: Any, index: Any) -> tuple[str | None, dict[str, Any] | None]:
        """Senha antiga por índice (0 = mais recente) ou o erro a devolver."""
        err = self._require()
        if err:
            return None, err
        entry = self._find(id)
        if entry is None:
            return None, _not_found()
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(entry.password_history)
        ):
            return None, _error("invalid_index", "Versão de senha inexistente.")
        return entry.password_history[index]["password"], None

    def reveal_history_password(self, id: str, index: int) -> dict[str, Any]:
        """Devolve uma senha antiga (0 = a mais recente)."""
        with self._lock:
            password, err = self._history_password(id, index)
            if err:
                return err
            return {"ok": True, "password": password}

    def copy_history_password(self, id: str, index: int) -> dict[str, Any]:
        """Copia uma senha antiga e agenda a limpeza da área de transferência."""
        with self._lock:
            password, err = self._history_password(id, index)
            if err:
                return err
            assert password is not None
            return self._copy_with_timer(password)

    def open_url(self, id: str) -> dict[str, Any]:
        """Abre o site salvo da conta no navegador padrão (só http/https)."""
        with self._lock:
            err = self._require()
            if err:
                return err
            entry = self._find(id)
            if entry is None:
                return _not_found()
            url, source = entry.url, "entry"
            if not url:
                recognized = self._catalog().match(entry.service)
                if recognized is None:
                    return _error("no_url", "Esta conta não tem um site salvo.")
                url, source = recognized.login_url, "library"
            if not _valid_http_url(url):
                return _error("invalid_url", "O endereço salvo não é um site http/https válido.")
        try:  # fora do lock: o navegador pode demorar
            opened = self._url_opener(url)
        except Exception:  # noqa: BLE001
            opened = False
        if opened is False:
            return _error("open_failed", "Não foi possível abrir o navegador.")
        return {"ok": True, "source": source}

    # ---- ajustes ----
    @staticmethod
    def _options(values: tuple[int, ...], recommended: int, label: Callable[[int], str]) -> list[dict[str, Any]]:
        return [
            {"value": v, "label": label(v), "recommended": v == recommended} for v in values
        ]

    def get_settings(self) -> dict[str, Any]:
        """Ajustes atuais e opções disponíveis."""
        with self._lock:
            err = self._require()
            if err:
                return err
            assert self._vault is not None
            st = self._vault.settings
            return {
                "ok": True,
                "settings": {
                    "auto_lock_minutes": st.auto_lock_minutes,
                    "clipboard_clear_seconds": st.clipboard_clear_seconds,
                },
                "options": {
                    "auto_lock_minutes": self._options(
                        AUTO_LOCK_OPTIONS, _RECOMMENDED_AUTO_LOCK,
                        lambda v: _plural(v, "minuto", "minutos"),
                    ),
                    "clipboard_clear_seconds": self._options(
                        CLIPBOARD_OPTIONS, _RECOMMENDED_CLIPBOARD, _seconds_label
                    ),
                },
            }

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Salva os ajustes e os aplica na hora (reinicia o prazo de inatividade)."""
        with self._lock:
            err = self._require()
            if err:
                return err
            vault = self._vault
            assert vault is not None
            data = data if isinstance(data, dict) else {}
            lock = data.get("auto_lock_minutes", vault.settings.auto_lock_minutes)
            clear = data.get("clipboard_clear_seconds", vault.settings.clipboard_clear_seconds)
            if not isinstance(lock, int) or isinstance(lock, bool) or lock not in AUTO_LOCK_OPTIONS:
                return _error("invalid_auto_lock", "Tempo de bloqueio automático inválido.")
            if not isinstance(clear, int) or isinstance(clear, bool) or clear not in CLIPBOARD_OPTIONS:
                return _error("invalid_clipboard", "Tempo de limpeza da área de transferência inválido.")
            try:
                saved = vault.update_settings(Settings(lock, clear))
            except OSError:
                return _error("save_failed", "Não foi possível salvar o cofre.")
            self._apply_settings()
            self._last_activity = self._clock()
            return {
                "ok": True,
                "settings": {
                    "auto_lock_minutes": saved.auto_lock_minutes,
                    "clipboard_clear_seconds": saved.clipboard_clear_seconds,
                },
            }

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

    # ---- biblioteca de serviços ----
    def lookup_service(self, name: str) -> dict[str, Any]:
        """Serviço reconhecido pelo nome digitado e sugestões."""
        with self._lock:
            err = self._require()
            if err:
                return err
            catalog = self._catalog()
            text = name if isinstance(name, str) else ""
            match = catalog.match(text)
            return {
                "ok": True,
                "match": self._service_dict(match) if match is not None else None,
                "suggestions": [self._service_dict(x) for x in catalog.suggest(text)],
            }

    def list_services(self, query: str = "") -> dict[str, Any]:
        """Lista a biblioteca (embutidos + personalizados), com busca por nome, apelido ou domínio."""
        with self._lock:
            err = self._require()
            if err:
                return err
            needle = normalize(query if isinstance(query, str) else "")
            found = []
            for service in self._catalog().all():
                if needle:
                    host = urlsplit(service.login_url).hostname or ""
                    haystack = [normalize(service.name), normalize(host)]
                    haystack += [normalize(a) for a in service.aliases]
                    if not any(needle in h for h in haystack):
                        continue
                found.append(self._service_dict(service))
            return {"ok": True, "services": found}

    def _save_services(self, custom: list[dict[str, Any]], overrides: dict[str, str]) -> dict[str, Any] | None:
        assert self._vault is not None
        try:
            self._vault.update_services(custom, overrides)
        except OSError:
            return _error("save_failed", "Não foi possível salvar o cofre.")
        return None

    def save_service(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria (sem key), edita personalizado ou altera só o link de um embutido."""
        with self._lock:
            err = self._require()
            if err:
                return err
            vault = self._vault
            assert vault is not None
            data = data if isinstance(data, dict) else {}
            catalog = self._catalog()
            custom = [dict(c) for c in vault.services["custom"]]
            overrides = dict(vault.services["overrides"])
            key = data.get("key")
            current = None
            if key:
                current = catalog.get(key)
                if current is None:
                    return _error("not_found", "Serviço não encontrado.")
            raw_url = data.get("login_url")
            url = _normalize_url(raw_url) if isinstance(raw_url, str) else None
            if not url:
                return _error("invalid_url", "Endereço de login inválido. Use http:// ou https://.")

            if current is not None and current.builtin:
                if url == current.default_url:
                    overrides.pop(current.key, None)
                else:
                    overrides[current.key] = url
                failed = self._save_services(custom, overrides)
                if failed:
                    return failed
                return {"ok": True, "service": self._service_dict(self._catalog().get(current.key))}

            name = data.get("name")
            name = name.strip() if isinstance(name, str) else ""
            if not name or not normalize(name):
                return _error("name_required", "Informe o nome do serviço.")
            if len(name) > _MAX_SERVICE_NAME:
                return _error(
                    "name_too_long", f"O nome deve ter no máximo {_MAX_SERVICE_NAME} caracteres."
                )
            raw_aliases = data.get("aliases")
            aliases: list[str] = []
            seen: set[str] = set()
            for alias in raw_aliases if isinstance(raw_aliases, list) else []:
                alias = alias.strip() if isinstance(alias, str) else ""
                norm = normalize(alias)
                if not norm or norm in seen:
                    continue
                if len(alias) > _MAX_SERVICE_NAME:
                    return _error(
                        "name_too_long",
                        f"Cada apelido deve ter no máximo {_MAX_SERVICE_NAME} caracteres.",
                    )
                seen.add(norm)
                aliases.append(alias)
            if len(aliases) > _MAX_ALIASES:
                return _error("too_many", f"O limite é de {_MAX_ALIASES} apelidos.")
            icon = data.get("icon", "")
            icon = "" if icon is None else icon
            if not isinstance(icon, str) or (icon and icon not in brand_icons()):
                return _error("invalid_icon", "Ícone inválido.")
            wanted = normalize(name)
            for other in catalog.all():
                if current is not None and other.key == current.key:
                    continue
                if wanted in (normalize(other.name), *map(normalize, other.aliases)):
                    return _error("name_exists", "Já existe um serviço com esse nome.")
            if current is None and len(custom) >= _MAX_CUSTOM_SERVICES:
                return _error(
                    "too_many", f"O limite é de {_MAX_CUSTOM_SERVICES} serviços personalizados."
                )
            record = {
                "key": current.key if current is not None else "custom-" + uuid.uuid4().hex,
                "name": name,
                "aliases": aliases,
                "login_url": url,
                "icon": icon,
            }
            if current is None:
                custom.append(record)
            else:
                custom = [record if c["key"] == record["key"] else c for c in custom]
            failed = self._save_services(custom, overrides)
            if failed:
                return failed
            return {"ok": True, "service": self._service_dict(self._catalog().get(record["key"]))}

    def reset_service(self, key: str) -> dict[str, Any]:
        """Restaura o link padrão de um serviço embutido."""
        with self._lock:
            err = self._require()
            if err:
                return err
            vault = self._vault
            assert vault is not None
            catalog = self._catalog()
            if not isinstance(key, str) or not catalog.is_builtin(key):
                return _error("not_found", "Serviço não encontrado.")
            overrides = dict(vault.services["overrides"])
            if key in overrides:
                del overrides[key]
                failed = self._save_services([dict(c) for c in vault.services["custom"]], overrides)
                if failed:
                    return failed
            return {"ok": True, "service": self._service_dict(self._catalog().get(key))}

    def delete_service(self, key: str) -> dict[str, Any]:
        """Remove um serviço personalizado (embutidos não podem ser removidos)."""
        with self._lock:
            err = self._require()
            if err:
                return err
            vault = self._vault
            assert vault is not None
            catalog = self._catalog()
            service = catalog.get(key)
            if service is None:
                return _error("not_found", "Serviço não encontrado.")
            if service.builtin:
                return _error("builtin_service", "Serviços da biblioteca não podem ser excluídos.")
            custom = [dict(c) for c in vault.services["custom"] if c["key"] != key]
            failed = self._save_services(custom, dict(vault.services["overrides"]))
            if failed:
                return failed
            return {"ok": True}

    def brand_icons(self) -> dict[str, Any]:
        """Ícones de marcas disponíveis. Não exige cofre aberto."""
        return {
            "ok": True,
            "icons": [
                {
                    "slug": i["slug"],
                    "title": i["title"],
                    "icon_url": icon_url(i["slug"]),
                    "color": brand_icons()[i["slug"]]["hex"] or None,
                }
                for i in Catalog.icons()
            ],
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
