"""Cofre criptografado: criar, abrir, CRUD, salvar e trocar senha mestra."""
from __future__ import annotations

import base64
import copy
import binascii
import hmac
import json
import os
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from . import crypto
from .errors import VaultCorruptedError, VaultExistsError, WrongPasswordError
from .models import Category, Entry, Settings

DEFAULT_VAULT_PATH = Path.home() / ".owlock" / "owlock.vault"
MIN_MASTER_PASSWORD_LENGTH = 8
MAX_PASSWORD_HISTORY = 20

FORMAT_NAME = "owlock-vault"
FORMAT_VERSION = 1
KDF_NAME = "argon2id"
CIPHER_NAME = "aes-256-gcm"

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Vault:
    """Cofre de senhas em memória, ligado a um arquivo cifrado."""

    def __init__(
        self,
        path: Path,
        key: bytes,
        salt: bytes,
        kdf_params: dict[str, int],
        entries: list[Entry] | None = None,
        categories: list[Category] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.path = Path(path)
        self.entries: list[Entry] = entries if entries is not None else []
        self.categories: list[Category] = categories if categories is not None else []
        self.settings: Settings = settings if settings is not None else Settings()
        self._key = key
        self._salt = salt
        self._kdf = dict(kdf_params)

    # ---- construção ----
    @classmethod
    def create(
        cls,
        path: str | Path,
        master_password: str,
        kdf_params: dict[str, int] | None = None,
    ) -> "Vault":
        """Cria um cofre novo e o salva. `kdf_params` é para uso em testes."""
        _check_master(master_password)
        path = Path(path)
        if path.exists():
            raise VaultExistsError("Já existe um cofre neste caminho.")
        params = _validate_kdf_params(dict(kdf_params or crypto.DEFAULT_KDF_PARAMS))
        path.parent.mkdir(parents=True, exist_ok=True)
        salt = crypto.new_salt()
        key = crypto.derive_key(master_password, salt, **params)
        vault = cls(path, key, salt, params, categories=default_categories())
        vault.save()
        return vault

    @classmethod
    def open(cls, path: str | Path, master_password: str) -> "Vault":
        """Abre um cofre existente com a senha mestra."""
        path = Path(path)
        raw = path.read_bytes()  # FileNotFoundError se não existir
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise VaultCorruptedError("Arquivo do cofre corrompido.") from exc
        if not isinstance(doc, dict):
            raise VaultCorruptedError("Arquivo do cofre corrompido.")
        if doc.get("format") != FORMAT_NAME or doc.get("version") != FORMAT_VERSION:
            raise VaultCorruptedError("Formato ou versão do cofre não suportado.")
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

        header = cls._header(salt, params)
        key = crypto.derive_key(master_password, salt, **params)
        try:
            plain = crypto.decrypt(key, nonce, ciphertext, cls._aad(header))
        except InvalidTag as exc:
            raise WrongPasswordError("Senha mestra incorreta ou arquivo alterado") from exc
        try:
            data = json.loads(plain.decode("utf-8"))
            entries = [Entry.from_dict(d) for d in data["entries"]]
            if "categories" in data:
                categories = [Category.from_dict(d) for d in data["categories"]]
            else:
                categories = default_categories()
            settings = Settings.from_dict(data.get("settings"))
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            raise VaultCorruptedError("Conteúdo do cofre corrompido.") from exc
        return cls(path, key, salt, params, entries, categories, settings)

    # ---- formato ----
    @staticmethod
    def _header(salt: bytes, params: dict[str, int]) -> dict[str, Any]:
        return {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "kdf": {
                "name": KDF_NAME,
                "salt": _b64e(salt),
                "time_cost": params["time_cost"],
                "memory_cost": params["memory_cost"],
                "parallelism": params["parallelism"],
            },
            "cipher": {"name": CIPHER_NAME},
        }

    @staticmethod
    def _aad(header: dict[str, Any]) -> bytes:
        return json.dumps(header, sort_keys=True, separators=(",", ":")).encode()

    # ---- persistência ----
    def save(self) -> None:
        """Cifra e grava o cofre de forma atômica, mantendo um .bak."""
        header = self._header(self._salt, self._kdf)
        plain = json.dumps(
            {
                "entries": [e.to_dict() for e in self.entries],
                "categories": [c.to_dict() for c in self.categories],
                "settings": self.settings.to_dict(),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        nonce, ciphertext = crypto.encrypt(self._key, plain, self._aad(header))
        doc = json.loads(json.dumps(header))
        doc["cipher"]["nonce"] = _b64e(nonce)
        doc["ciphertext"] = _b64e(ciphertext)
        data = json.dumps(doc, indent=2).encode("utf-8")

        tmp = self.path.with_name(self.path.name + ".tmp")
        bak = self.path.with_name(self.path.name + ".bak")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if self.path.exists():
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

    def change_master_password(self, current: str, new: str) -> None:
        """Troca a senha mestra (novo salt) e salva."""
        check = crypto.derive_key(current, self._salt, **self._kdf)
        if not hmac.compare_digest(check, self._key):
            raise WrongPasswordError("Senha mestra atual incorreta")
        _check_master(new)
        old_key, old_salt = self._key, self._salt
        salt = crypto.new_salt()
        self._key = crypto.derive_key(new, salt, **self._kdf)
        self._salt = salt
        try:
            self.save()
        except BaseException:
            self._key, self._salt = old_key, old_salt
            raise
