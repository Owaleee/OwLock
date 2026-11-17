"""Cofre criptografado: criar, abrir, CRUD, salvar e trocar senha mestra."""
from __future__ import annotations

import base64
import copy
import binascii
import hmac
import json
import os
import re
import secrets
import shutil
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from . import crypto
from .errors import (
    MigrationError,
    SecretKeyRequiredError,
    VaultCorruptedError,
    VaultExistsError,
    WrongPasswordError,
    WrongSecretKeyError,
)
from .keystore import SecretKeyStore
from .models import Category, Entry, Settings
from .secret_key import (
    format_secret_key,
    generate_secret_key,
    parse_secret_key,
    secret_key_id,
)

DEFAULT_VAULT_PATH = Path.home() / ".owlock" / "owlock.vault"
MIN_MASTER_PASSWORD_LENGTH = 8
MAX_PASSWORD_HISTORY = 20

FORMAT_NAME = "owlock-vault"
FORMAT_VERSION = 2
LEGACY_VERSION = 1
KDF_NAME = "argon2id"
CIPHER_NAME = "aes-256-gcm"

_VAULT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_KEY_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_MAX_ENTRY_ID = 128
_SALT_LENGTH_V2 = crypto.SALT_LENGTH

# Limites aceitos ao ler parâmetros do arquivo (evita travar a máquina).
_LIMITS = {
    "time_cost": (1, 20),
    "memory_cost": (8192, 1048576),
    "parallelism": (1, 16),
}


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(value: Any) -> bytes:
    if not isinstance(value, str):
        raise VaultCorruptedError("Arquivo do cofre inválido.")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VaultCorruptedError("Arquivo do cofre inválido (base64).") from exc


def _validate_kdf_params(params: dict[str, Any]) -> dict[str, int]:
    """Valida e devolve time_cost/memory_cost/parallelism dentro dos limites."""
    out: dict[str, int] = {}
    for name, (low, high) in _LIMITS.items():
        value = params.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise VaultCorruptedError("Parâmetros de derivação inválidos.")
        if not low <= value <= high:
            raise VaultCorruptedError("Parâmetros de derivação fora dos limites.")
        out[name] = value
    return out


def _normalize(text: str) -> str:
    """casefold + remoção de acentos."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _check_master(password: str) -> None:
    if len(password) < MIN_MASTER_PASSWORD_LENGTH:
        raise ValueError(
            f"A senha mestra deve ter ao menos {MIN_MASTER_PASSWORD_LENGTH} caracteres."
        )


def default_categories() -> list[Category]:
    """Categorias criadas em cofres novos e em cofres anteriores às categorias."""
    return [
        Category("Pessoal", "mint", "user"),
        Category("Trabalho", "blue", "briefcase"),
        Category("Jogos", "violet", "gamepad"),
        Category("Redes sociais", "pink", "chat"),
        Category("Financeiro", "amber", "card"),
        Category("Streaming", "coral", "play"),
    ]


def empty_services() -> dict[str, Any]:
    return {"custom": [], "overrides": {}}


def _parse_services(raw: Any) -> dict[str, Any]:
    """Valida o bloco "services" e devolve uma cópia normalizada (ValueError se inválido)."""
    if not isinstance(raw, dict):
        raise ValueError("Bloco de serviços inválido.")
    custom_raw = raw.get("custom", [])
    overrides_raw = raw.get("overrides", {})
    if not isinstance(custom_raw, list) or not isinstance(overrides_raw, dict):
        raise ValueError("Bloco de serviços inválido.")
    custom: list[dict[str, Any]] = []
    for item in custom_raw:
        if not isinstance(item, dict):
            raise ValueError("Serviço personalizado inválido.")
        for name in ("key", "name", "login_url"):
            if not isinstance(item.get(name), str):
                raise ValueError("Serviço personalizado inválido.")
        aliases = item.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise ValueError("Serviço personalizado inválido.")
        icon = item.get("icon", "")
        if not isinstance(icon, str):
            raise ValueError("Serviço personalizado inválido.")
        custom.append(
            {
                "key": item["key"],
                "name": item["name"],
                "aliases": list(aliases),
                "login_url": item["login_url"],
                "icon": icon,
            }
        )
    for k, v in overrides_raw.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("Links alterados inválidos.")
    return {"custom": custom, "overrides": dict(overrides_raw)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_meta_blocks(data: dict[str, Any]) -> tuple[list[Category], Settings, dict[str, Any]]:
    """Lê categorias, ajustes e serviços de um dict (ValueError/KeyError/TypeError se inválido)."""
    if "categories" in data:
        categories = [Category.from_dict(d) for d in data["categories"]]
    else:
        categories = default_categories()
    settings = Settings.from_dict(data.get("settings"))
    services = _parse_services(data["services"]) if "services" in data else empty_services()
    return categories, settings, services


def _read_doc(path: Path) -> tuple[bytes, dict[str, Any]]:
    """Lê o arquivo do cofre e devolve (bytes, documento JSON)."""
    raw = path.read_bytes()  # FileNotFoundError se não existir
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VaultCorruptedError("Arquivo do cofre corrompido.") from exc
    if not isinstance(doc, dict):
        raise VaultCorruptedError("Arquivo do cofre corrompido.")
    if doc.get("format") != FORMAT_NAME:
        raise VaultCorruptedError("Formato ou versão do cofre não suportado.")
    return raw, doc


def _doc_version(doc: dict[str, Any]) -> int:
    version = doc.get("version")
    if type(version) is not int or version not in (LEGACY_VERSION, FORMAT_VERSION):
        raise VaultCorruptedError("Formato ou versão do cofre não suportado.")
    return version


# ---- formato v1 (somente leitura para migração; a criação existe para testes) ----
def _v1_header(salt: bytes, params: dict[str, int]) -> dict[str, Any]:
    return {
        "format": FORMAT_NAME,
        "version": LEGACY_VERSION,
        "kdf": {
            "name": KDF_NAME,
            "salt": _b64e(salt),
            "time_cost": params["time_cost"],
            "memory_cost": params["memory_cost"],
            "parallelism": params["parallelism"],
        },
        "cipher": {"name": CIPHER_NAME},
    }


def _v1_aad(header: dict[str, Any]) -> bytes:
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode()


def _open_v1(
    doc: dict[str, Any], password: str
) -> tuple[list[Entry], list[Category], Settings, dict[str, Any], dict[str, int]]:
    """Abre o conteúdo de um cofre v1 (já lido). Devolve dados e parâmetros do kdf."""
    kdf, cipher = doc.get("kdf"), doc.get("cipher")
    if not isinstance(kdf, dict) or not isinstance(cipher, dict):
        raise VaultCorruptedError("Arquivo do cofre incompleto.")
    if kdf.get("name") != KDF_NAME or cipher.get("name") != CIPHER_NAME:
        raise VaultCorruptedError("Algoritmos do cofre não suportados.")
    if "salt" not in kdf or "nonce" not in cipher or "ciphertext" not in doc:
        raise VaultCorruptedError("Arquivo do cofre incompleto.")
    params = _validate_kdf_params(kdf)
    salt = _b64d(kdf["salt"])
    nonce = _b64d(cipher["nonce"])
    ciphertext = _b64d(doc["ciphertext"])
    if len(nonce) != crypto.NONCE_LENGTH or not salt:
        raise VaultCorruptedError("Arquivo do cofre inválido.")
    header = _v1_header(salt, params)
    key = crypto.derive_key(password, salt, **params)
    try:
        plain = crypto.decrypt(key, nonce, ciphertext, _v1_aad(header))
    except InvalidTag as exc:
        raise WrongPasswordError("Senha mestra incorreta ou arquivo alterado") from exc
    try:
        data = json.loads(plain.decode("utf-8"))
        entries = [Entry.from_dict(d) for d in data["entries"]]
        categories, settings, services = _parse_meta_blocks(data)
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise VaultCorruptedError("Conteúdo do cofre corrompido.") from exc
    return entries, categories, settings, services, params


def _create_v1(
    path: str | Path,
    master_password: str,
    kdf_params: dict[str, int] | None = None,
    entries: list[Entry] | None = None,
    categories: list[Category] | None = None,
    settings: Settings | None = None,
    services: dict[str, Any] | None = None,
) -> None:
    """Grava um cofre no formato v1 (legado). Existe só para testar a migração."""
    path = Path(path)
    params = _validate_kdf_params(dict(kdf_params or crypto.DEFAULT_KDF_PARAMS))
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = crypto.new_salt()
    key = crypto.derive_key(master_password, salt, **params)
    header = _v1_header(salt, params)
    plain = json.dumps(
        {
            "entries": [e.to_dict() for e in (entries or [])],
            "categories": [c.to_dict() for c in (categories if categories is not None else default_categories())],
            "settings": (settings or Settings()).to_dict(),
            "services": services if services is not None else empty_services(),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    nonce, ciphertext = crypto.encrypt(key, plain, _v1_aad(header))
    doc = json.loads(json.dumps(header))
    doc["cipher"]["nonce"] = _b64e(nonce)
    doc["ciphertext"] = _b64e(ciphertext)
    path.write_bytes(json.dumps(doc, indent=2).encode("utf-8"))


# ---- formato v2 ----
def _v2_header(
    vault_id: str, salt: bytes, params: dict[str, int], key_id: str
) -> dict[str, Any]:
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "vault_id": vault_id,
        "kdf": {
            "name": KDF_NAME,
            "salt": _b64e(salt),
            "time_cost": params["time_cost"],
            "memory_cost": params["memory_cost"],
            "parallelism": params["parallelism"],
        },
        "secret_key": {"id": key_id},
        "cipher": {"name": CIPHER_NAME},
    }


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _meta_aad(vault_id: str) -> bytes:
    return b"owlock-v2|" + vault_id.encode("ascii") + b"|meta"


def _entry_aad(vault_id: str, entry_id: str) -> bytes:
    return b"owlock-v2|" + vault_id.encode("ascii") + b"|entry|" + entry_id.encode("utf-8")


def _blob(doc: dict[str, Any], name: str) -> tuple[bytes, bytes]:
    """Lê {"nonce", "ciphertext"} de doc[name], validando base64 e o tamanho do nonce."""
    block = doc.get(name)
    if not isinstance(block, dict) or "nonce" not in block or "ciphertext" not in block:
        raise VaultCorruptedError("Arquivo do cofre incompleto.")
    nonce = _b64d(block["nonce"])
    ciphertext = _b64d(block["ciphertext"])
    if len(nonce) != crypto.NONCE_LENGTH or not ciphertext:
        raise VaultCorruptedError("Arquivo do cofre inválido.")
    return nonce, ciphertext


def _vault_id_of(doc: dict[str, Any]) -> str:
    vault_id = doc.get("vault_id")
    if not isinstance(vault_id, str) or not _VAULT_ID_RE.match(vault_id):
        raise VaultCorruptedError("Identificador do cofre inválido.")
    return vault_id


def _key_id_of(doc: dict[str, Any]) -> str:
    block = doc.get("secret_key")
    key_id = block.get("id") if isinstance(block, dict) else None
    if not isinstance(key_id, str) or not _KEY_ID_RE.match(key_id):
        raise VaultCorruptedError("Identificador da Chave Secreta inválido.")
    return key_id


def _write_new(path: Path, data: bytes, mode: int = 0o600) -> None:
    """Cria um arquivo NOVO (falha se existir) com permissão restrita."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _persist_secret(store: SecretKeyStore, vault_id: str, secret: bytes) -> None:
    try:
        store.set(vault_id, secret)
    except Exception as exc:  # noqa: BLE001 - qualquer falha do chaveiro/arquivo
        raise OSError("Não foi possível guardar a Chave Secreta neste aparelho.") from exc


class Vault:
    """Cofre de senhas em memória, ligado a um arquivo cifrado (formato v2)."""

    def __init__(
        self,
        path: Path,
        vault_id: str,
        vault_key: bytes,
        kek: bytes,
        salt: bytes,
        kdf_params: dict[str, int],
        secret_bytes: bytes,
        entries: list[Entry] | None = None,
        categories: list[Category] | None = None,
        settings: Settings | None = None,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.path = Path(path)
        self.entries: list[Entry] = entries if entries is not None else []
        self.categories: list[Category] = categories if categories is not None else []
        self.settings: Settings = settings if settings is not None else Settings()
        self.services: dict[str, Any] = services if services is not None else empty_services()
        self.migrated = False
        self.v1_backup_path: Path | None = None
        self.secret_key_persisted = True
        self._vault_id = vault_id
        self._vault_key = vault_key
        self._kek = kek
        self._salt = salt
        self._kdf = dict(kdf_params)
        self._secret = secret_bytes
        self._secret_display: str | None = None

    def __repr__(self) -> str:  # nunca expõe chaves
        return f"<Vault path={str(self.path)!r} entries={len(self.entries)}>"

    @property
    def vault_id(self) -> str:
        return self._vault_id

    @property
    def secret_key_formatted(self) -> str | None:
        """Chave Secreta formatada, só logo após criar/migrar (depois, use reveal_secret_key)."""
        return self._secret_display

    def forget_secret_key_display(self) -> None:
        """Descarta a cópia de exibição da Chave Secreta."""
        self._secret_display = None

    # ---- construção ----
    @classmethod
    def create(
        cls,
        path: str | Path,
        master_password: str,
        store: SecretKeyStore,
        kdf_params: dict[str, int] | None = None,
    ) -> "Vault":
        """Cria um cofre v2 novo com Chave Secreta nova e o salva.

        A Chave Secreta vai para o `store` ANTES de o arquivo ser gravado.
        `kdf_params` é para uso em testes.
        """
        _check_master(master_password)
        path = Path(path)
        if path.exists():
            raise VaultExistsError("Já existe um cofre neste caminho.")
        params = _validate_kdf_params(dict(kdf_params or crypto.DEFAULT_KDF_PARAMS))
        path.parent.mkdir(parents=True, exist_ok=True)
        vault = cls._fresh(path, master_password, params, categories=default_categories())
        _persist_secret(store, vault._vault_id, vault._secret)
        try:
            vault.save()
        except BaseException:
            try:
                store.delete(vault._vault_id)
            except Exception:  # noqa: BLE001 - limpeza best-effort
                pass
            raise
        vault._secret_display = format_secret_key(vault._secret)
        return vault

    @classmethod
    def _fresh(
        cls,
        path: Path,
        master_password: str,
        params: dict[str, int],
        entries: list[Entry] | None = None,
        categories: list[Category] | None = None,
        settings: Settings | None = None,
        services: dict[str, Any] | None = None,
    ) -> "Vault":
        """Monta um cofre v2 em memória (ids, Chave Secreta, vault key e KEK novos)."""
        vault_id = uuid.uuid4().hex
        secret = generate_secret_key()
        salt = crypto.new_salt()
        kek = crypto.derive_kek(
            master_password, salt, secret, bytes.fromhex(vault_id), **params
        )
        vault_key = secrets.token_bytes(crypto.KEY_LENGTH)
        return cls(
            path, vault_id, vault_key, kek, salt, params, secret,
            entries, categories, settings, services,
        )

    @classmethod
    def peek(cls, path: str | Path) -> dict[str, Any]:
        """Lê só o cabeçalho (sem senha): {version, vault_id, secret_key_id}."""
        _, doc = _read_doc(Path(path))
        version = _doc_version(doc)
        if version == LEGACY_VERSION:
            return {"version": 1, "vault_id": None, "secret_key_id": None}
        return {"version": 2, "vault_id": _vault_id_of(doc), "secret_key_id": _key_id_of(doc)}

    @classmethod
    def open(
        cls,
        path: str | Path,
        master_password: str,
        store: SecretKeyStore,
        secret_key: str | None = None,
    ) -> "Vault":
        """Abre um cofre (v2, ou v1 que é migrado para v2) com a senha mestra.

        `secret_key` (texto) é a Chave Secreta digitada; sem ela, usa a do `store`.
        """
        path = Path(path)
        raw, doc = _read_doc(path)
        if _doc_version(doc) == LEGACY_VERSION:
            return cls._migrate(path, raw, doc, master_password, store)
        return cls._open_v2(path, doc, master_password, store, secret_key)

    @classmethod
    def _open_v2(
        cls,
        path: Path,
        doc: dict[str, Any],
        master_password: str,
        store: SecretKeyStore,
        secret_key: str | None,
    ) -> "Vault":
        # 1) estrutura e limites, tudo antes de qualquer derivação cara
        vault_id = _vault_id_of(doc)
        key_id = _key_id_of(doc)
        kdf, cipher = doc.get("kdf"), doc.get("cipher")
        if not isinstance(kdf, dict) or not isinstance(cipher, dict):
            raise VaultCorruptedError("Arquivo do cofre incompleto.")
        if kdf.get("name") != KDF_NAME or cipher.get("name") != CIPHER_NAME:
            raise VaultCorruptedError("Algoritmos do cofre não suportados.")
        params = _validate_kdf_params(kdf)
        if "salt" not in kdf:
            raise VaultCorruptedError("Arquivo do cofre incompleto.")
        salt = _b64d(kdf["salt"])
        if len(salt) != _SALT_LENGTH_V2:
            raise VaultCorruptedError("Arquivo do cofre inválido.")
        key_nonce, key_ct = _blob(doc, "key")
        meta_nonce, meta_ct = _blob(doc, "meta")
        raw_entries = doc.get("entries")
        if not isinstance(raw_entries, list):
            raise VaultCorruptedError("Arquivo do cofre incompleto.")
        blobs: list[tuple[str, bytes, bytes]] = []
        seen: set[str] = set()
        for item in raw_entries:
            if not isinstance(item, dict):
                raise VaultCorruptedError("Arquivo do cofre inválido.")
            entry_id = item.get("id")
            if not isinstance(entry_id, str) or not 0 < len(entry_id) <= _MAX_ENTRY_ID:
                raise VaultCorruptedError("Arquivo do cofre inválido.")
            if entry_id in seen:
                raise VaultCorruptedError("Arquivo do cofre corrompido (entrada repetida).")
            seen.add(entry_id)
            nonce, ciphertext = _blob({"x": item}, "x")
            blobs.append((entry_id, nonce, ciphertext))

        # 2) Chave Secreta: informada ou guardada neste aparelho
        from_input = secret_key is not None
        if from_input:
            secret = parse_secret_key(secret_key)  # InvalidSecretKeyError
        else:
            try:
                secret = store.get(vault_id)
            except Exception:  # noqa: BLE001 - chaveiro indisponível: pedir a chave
                secret = None
            if secret is None:
                raise SecretKeyRequiredError(
                    "Este cofre precisa da Chave Secreta, que não está neste aparelho."
                )
        vault_id_bytes = bytes.fromhex(vault_id)
        expected = secret_key_id(secret, vault_id_bytes)
        if not hmac.compare_digest(expected.encode("ascii"), key_id.encode("ascii")):
            raise WrongSecretKeyError("Chave Secreta incorreta para este cofre.")

        # 3) senha mestra -> KEK -> chave do cofre
        kek = crypto.derive_kek(master_password, salt, secret, vault_id_bytes, **params)
        header = _v2_header(vault_id, salt, params, key_id)
        try:
            vault_key = crypto.decrypt(kek, key_nonce, key_ct, _canonical(header))
        except InvalidTag as exc:
            raise WrongPasswordError("Senha mestra incorreta ou arquivo alterado") from exc
        if len(vault_key) != crypto.KEY_LENGTH:
            raise VaultCorruptedError("Arquivo do cofre inválido.")

        # 4) metadados e entradas
        try:
            meta_plain = crypto.decrypt(vault_key, meta_nonce, meta_ct, _meta_aad(vault_id))
            meta = json.loads(meta_plain.decode("utf-8"))
            if not isinstance(meta, dict):
                raise ValueError("meta")
            categories, settings, services = _parse_meta_blocks(meta)
        except InvalidTag as exc:
            raise VaultCorruptedError("Conteúdo do cofre corrompido.") from exc
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            raise VaultCorruptedError("Conteúdo do cofre corrompido.") from exc
        entries: list[Entry] = []
        for entry_id, nonce, ciphertext in blobs:
            try:
                plain = crypto.decrypt(vault_key, nonce, ciphertext, _entry_aad(vault_id, entry_id))
                entry = Entry.from_dict(json.loads(plain.decode("utf-8")))
            except InvalidTag as exc:
                raise VaultCorruptedError("Conteúdo do cofre corrompido.") from exc
            except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
                raise VaultCorruptedError("Conteúdo do cofre corrompido.") from exc
            if entry.id != entry_id:
                raise VaultCorruptedError("Conteúdo do cofre corrompido (id divergente).")
            entries.append(entry)

        vault = cls(
            path, vault_id, vault_key, kek, salt, params, secret,
            entries, categories, settings, services,
        )
        if from_input:
            # chave digitada e correta: guarda neste aparelho (falha não impede de abrir)
            try:
                store.set(vault_id, secret)
            except Exception:  # noqa: BLE001
                vault.secret_key_persisted = False
        return vault

    @classmethod
    def _migrate(
        cls,
        path: Path,
        raw: bytes,
        doc: dict[str, Any],
        master_password: str,
        store: SecretKeyStore,
    ) -> "Vault":
        """Abre um cofre v1 e o converte para v2. Em falha, o arquivo original não muda."""
        entries, categories, settings, services, params = _open_v1(doc, master_password)
        try:
            vault = cls._fresh(path, master_password, params, entries, categories, settings, services)
        except (ValueError, OSError) as exc:  # pragma: no cover - defensivo
            raise MigrationError("Não foi possível converter o cofre para o formato v2.") from exc
        try:
            store.set(vault._vault_id, vault._secret)  # ANTES de tocar no arquivo
        except Exception as exc:  # noqa: BLE001
            raise MigrationError(
                "Não foi possível guardar a Chave Secreta neste aparelho; o cofre não foi alterado."
            ) from exc
        backup: Path | None = None
        try:
            backup = cls._unique_backup_path(path)
            _write_new(backup, raw)
            vault._write(vault._serialize(), keep_bak=False)
        except BaseException as exc:
            if backup is not None:
                try:
                    backup.unlink()
                except OSError:
                    pass
            try:
                store.delete(vault._vault_id)
            except Exception:  # noqa: BLE001 - limpeza best-effort
                pass
            if isinstance(exc, Exception):
                raise MigrationError(
                    "Não foi possível converter o cofre para o formato v2; o arquivo original não foi alterado."
                ) from exc
            raise
        vault.migrated = True
        vault.v1_backup_path = backup
        vault._secret_display = format_secret_key(vault._secret)
        # o .bak antigo seria um cofre v1 (abre sem a Chave Secreta): troca pelo arquivo novo
        try:
            vault._refresh_bak()
        except OSError:
            pass
        return vault

    @staticmethod
    def _unique_backup_path(path: Path) -> Path:
        base = path.with_name(path.name + ".v1-backup")
        if not base.exists():
            return base
        for n in range(2, 1000):
            candidate = path.with_name(f"{path.name}.v1-backup.{n}")
            if not candidate.exists():
                return candidate
        raise OSError("Muitas cópias do cofre antigo.")

    # ---- persistência ----
    def _serialize(self) -> bytes:
        ids = [e.id for e in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("Há contas com o mesmo identificador.")
        if any(not isinstance(i, str) or not 0 < len(i) <= _MAX_ENTRY_ID for i in ids):
            raise ValueError("Identificador de conta inválido.")
        vid = self._vault_id
        key_id = secret_key_id(self._secret, bytes.fromhex(vid))
        header = _v2_header(vid, self._salt, self._kdf, key_id)
        key_nonce, key_ct = crypto.encrypt(self._kek, self._vault_key, _canonical(header))
        meta_plain = json.dumps(
            {
                "categories": [c.to_dict() for c in self.categories],
                "settings": self.settings.to_dict(),
                "services": self.services,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        meta_nonce, meta_ct = crypto.encrypt(self._vault_key, meta_plain, _meta_aad(vid))
        enc_entries = []
        for entry in self.entries:
            plain = json.dumps(entry.to_dict(), ensure_ascii=False).encode("utf-8")
            nonce, ct = crypto.encrypt(self._vault_key, plain, _entry_aad(vid, entry.id))
            enc_entries.append({"id": entry.id, "nonce": _b64e(nonce), "ciphertext": _b64e(ct)})
        doc = json.loads(json.dumps(header))
        doc["key"] = {"nonce": _b64e(key_nonce), "ciphertext": _b64e(key_ct)}
        doc["meta"] = {"nonce": _b64e(meta_nonce), "ciphertext": _b64e(meta_ct)}
        doc["entries"] = enc_entries
        return json.dumps(doc, indent=2).encode("utf-8")

    def _write(self, data: bytes, keep_bak: bool = True) -> None:
        tmp = self.path.with_name(self.path.name + ".tmp")
        bak = self.path.with_name(self.path.name + ".bak")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if keep_bak and self.path.exists():
                shutil.copy2(self.path, bak)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def save(self) -> None:
        """Cifra e grava o cofre de forma atômica, mantendo um .bak."""
        self._write(self._serialize())

    def _refresh_bak(self) -> None:
        """Sobrescreve o .bak com o arquivo atual (o .bak não pode guardar estado antigo).

        Se não der para sobrescrever, tenta apagar o .bak; se nem isso, levanta OSError.
        """
        bak = self.path.with_name(self.path.name + ".bak")
        tmp = self.path.with_name(self.path.name + ".bak.tmp")
        try:
            data = self.path.read_bytes()
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, bak)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            try:
                bak.unlink()
            except FileNotFoundError:
                pass
            return
        try:
            os.chmod(bak, 0o600)
        except OSError:
            pass

    # ---- CRUD ----
    def add(self, entry: Entry) -> Entry:
        """Adiciona uma entrada e salva."""
        previous = list(self.entries)
        self.entries.append(entry)
        try:
            self.save()
        except BaseException:
            self.entries = previous
            raise
        return entry

    def _index(self, entry_id: str) -> int:
        for i, e in enumerate(self.entries):
            if e.id == entry_id:
                return i
        raise KeyError(entry_id)

    def update(self, entry: Entry) -> Entry:
        """Atualiza a entrada pelo id (preserva created_at) e salva.

        Se a senha mudou em relação à salva, a senha antiga entra no início do
        histórico (máximo MAX_PASSWORD_HISTORY itens). Em falha, tudo é restaurado.
        """
        i = self._index(entry.id)
        stored = self.entries[i]
        previous = list(self.entries)
        old_created, old_updated = entry.created_at, entry.updated_at
        old_history = copy.deepcopy(entry.password_history)
        history = copy.deepcopy(stored.password_history)
        if entry.password != stored.password:
            history.insert(0, {"password": stored.password, "changed_at": _now()})
        entry.password_history = history[:MAX_PASSWORD_HISTORY]
        entry.created_at = stored.created_at
        entry.updated_at = _now()
        self.entries[i] = entry
        try:
            self.save()
        except BaseException:
            self.entries = previous
            entry.created_at, entry.updated_at = old_created, old_updated
            entry.password_history = old_history
            raise
        return entry

    def delete(self, entry_id: str) -> None:
        """Remove a entrada pelo id e salva."""
        i = self._index(entry_id)
        previous = list(self.entries)
        del self.entries[i]
        try:
            self.save()
        except BaseException:
            self.entries = previous
            raise

    # ---- categorias ----
    def _category_index(self, category_id: str) -> int:
        for i, c in enumerate(self.categories):
            if c.id == category_id:
                return i
        raise KeyError(category_id)

    def add_category(self, category: Category) -> Category:
        """Adiciona uma categoria e salva."""
        previous = list(self.categories)
        self.categories.append(category)
        try:
            self.save()
        except BaseException:
            self.categories = previous
            raise
        return category

    def update_category(self, category: Category) -> Category:
        """Atualiza a categoria pelo id e salva."""
        i = self._category_index(category.id)
        previous = list(self.categories)
        self.categories[i] = category
        try:
            self.save()
        except BaseException:
            self.categories = previous
            raise
        return category

    def delete_category(self, category_id: str) -> int:
        """Remove a categoria (contas ficam sem categoria) e salva uma vez.

        Devolve quantas contas ficaram sem categoria.
        """
        i = self._category_index(category_id)
        previous = list(self.categories)
        affected = [e for e in self.entries if e.category_id == category_id]
        del self.categories[i]
        for e in affected:
            e.category_id = ""
        try:
            self.save()
        except BaseException:
            self.categories = previous
            for e in affected:
                e.category_id = category_id
            raise
        return len(affected)

    # ---- ajustes ----
    def update_settings(self, settings: Settings) -> Settings:
        """Troca os ajustes e salva; em falha, restaura os anteriores."""
        if not isinstance(settings, Settings) or not settings.is_valid():
            raise ValueError("Ajustes inválidos.")
        previous = self.settings
        self.settings = Settings(**settings.to_dict())
        try:
            self.save()
        except BaseException:
            self.settings = previous
            raise
        return self.settings

    # ---- biblioteca de serviços ----
    def update_services(self, custom: list[dict[str, Any]], overrides: dict[str, str]) -> dict[str, Any]:
        """Troca serviços personalizados e links alterados e salva; em falha, restaura."""
        parsed = _parse_services(copy.deepcopy({"custom": custom, "overrides": overrides}))
        previous = self.services
        self.services = parsed
        try:
            self.save()
        except BaseException:
            self.services = previous
            raise
        return self.services

    def search(self, text: str) -> list[Entry]:
        """Busca sem diferenciar maiúsculas/acentos (nunca na senha)."""
        needle = _normalize(text.strip())
        if not needle:
            return list(self.entries)
        return [
            e
            for e in self.entries
            if any(
                needle in _normalize(v)
                for v in (e.service, e.username, e.twofa_app, e.notes)
            )
        ]

    def _derive_kek(self, password: str, salt: bytes) -> bytes:
        return crypto.derive_kek(
            password, salt, self._secret, bytes.fromhex(self._vault_id), **self._kdf
        )

    def _check_current(self, password: str) -> None:
        check = self._derive_kek(password, self._salt)
        if not hmac.compare_digest(check, self._kek):
            raise WrongPasswordError("Senha mestra atual incorreta")

    def change_master_password(self, current: str, new: str) -> None:
        """Troca a senha mestra (novo salt, nova KEK; só `key` é refeito) e salva.

        Depois de salvar, o .bak é sobrescrito com o arquivo novo (não abre com a senha antiga).
        """
        self._check_current(current)
        _check_master(new)
        old_kek, old_salt = self._kek, self._salt
        salt = crypto.new_salt()
        self._kek = self._derive_kek(new, salt)
        self._salt = salt
        try:
            self.save()
        except BaseException:
            self._kek, self._salt = old_kek, old_salt
            raise
        self._refresh_bak()

    def reveal_secret_key(self, password: str) -> str:
        """Confere a senha mestra e devolve a Chave Secreta formatada."""
        self._check_current(password)
        return format_secret_key(self._secret)
