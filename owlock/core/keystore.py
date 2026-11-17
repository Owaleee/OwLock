"""Onde a Chave Secreta fica guardada neste aparelho.

- KeyringStore: Gerenciador de Credenciais do Windows / Keychain / Secret Service
  (biblioteca `keyring`), com queda automática para FileStore se não houver backend utilizável.
- FileStore: arquivo `<vault_id>.key` com permissão 600 numa pasta do usuário.
- MemoryStore: só para testes.
"""
from __future__ import annotations

import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from .secret_key import format_secret_key, parse_secret_key
from .errors import InvalidSecretKeyError

KEYRING_SERVICE = "OwLock"
DEFAULT_KEYS_DIR = Path.home() / ".owlock" / "keys"
_VAULT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_FILE_DESCRIPTION = "arquivo protegido na sua pasta de usuário"


def _check_vault_id(vault_id: str) -> str:
    if not isinstance(vault_id, str) or not _VAULT_ID_RE.match(vault_id):
        raise ValueError("Identificador de cofre inválido.")
    return vault_id


class SecretKeyStore(ABC):
    """Guarda a Chave Secreta (bytes) de cada cofre, pelo vault_id (32 hex)."""

    @abstractmethod
    def get(self, vault_id: str) -> bytes | None: ...

    @abstractmethod
    def set(self, vault_id: str, secret_bytes: bytes) -> None: ...

    @abstractmethod
    def delete(self, vault_id: str) -> None: ...

    @property
    @abstractmethod
    def description(self) -> str: ...


class MemoryStore(SecretKeyStore):
    """Guarda na memória (testes)."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def get(self, vault_id: str) -> bytes | None:
        return self._data.get(_check_vault_id(vault_id))

    def set(self, vault_id: str, secret_bytes: bytes) -> None:
        self._data[_check_vault_id(vault_id)] = bytes(secret_bytes)

    def delete(self, vault_id: str) -> None:
        self._data.pop(_check_vault_id(vault_id), None)

    @property
    def description(self) -> str:
        return "memória (somente testes)"

    def __repr__(self) -> str:
        return f"MemoryStore({len(self._data)} chaves)"


class FileStore(SecretKeyStore):
    """Um arquivo `<vault_id>.key` por cofre (permissão 600, escrita atômica)."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else DEFAULT_KEYS_DIR

    def _file(self, vault_id: str) -> Path:
        return self.directory / f"{_check_vault_id(vault_id)}.key"

    def get(self, vault_id: str) -> bytes | None:
        path = self._file(vault_id)
        try:
            text = path.read_text(encoding="ascii")
        except FileNotFoundError:
            return None
        except (UnicodeDecodeError, IsADirectoryError):
            return None
        try:
            return parse_secret_key(text)
        except InvalidSecretKeyError:
            return None

    def set(self, vault_id: str, secret_bytes: bytes) -> None:
        path = self._file(vault_id)
        text = format_secret_key(secret_bytes) + "\n"
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.directory, 0o700)
        except OSError:
            pass
        tmp = path.with_name(path.name + ".tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(text.encode("ascii"))
                f.flush()
                os.fsync(f.fileno())
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def delete(self, vault_id: str) -> None:
        try:
            self._file(vault_id).unlink()
        except FileNotFoundError:
            pass

    @property
    def description(self) -> str:
        return _FILE_DESCRIPTION

    def __repr__(self) -> str:
        return f"FileStore({str(self.directory)!r})"


def _backend_usable() -> bool:
    """True se o keyring tem um backend real (nem `fail` nem `null`)."""
    try:
        import keyring
        from keyring.backends import fail, null

        backend = keyring.get_keyring()
        if isinstance(backend, (fail.Keyring, null.Keyring)):
            return False
        return float(backend.priority) > 0
    except Exception:  # noqa: BLE001 - qualquer falha = sem backend utilizável
        return False


def _keyring_description() -> str:
    if sys.platform == "win32":
        return "Gerenciador de Credenciais do Windows"
    if sys.platform == "darwin":
        return "Keychain do macOS"
    return "Chaveiro do sistema"


class KeyringStore(SecretKeyStore):
    """Chaveiro do sistema; se faltar backend ou der erro, usa um FileStore."""

    def __init__(self, fallback: FileStore | None = None) -> None:
        self._fallback = fallback if fallback is not None else FileStore()
        self._keyring_ok = _backend_usable()

    def get(self, vault_id: str) -> bytes | None:
        _check_vault_id(vault_id)
        if self._keyring_ok:
            try:
                import keyring

                value = keyring.get_password(KEYRING_SERVICE, vault_id)
                if value is not None:
                    return parse_secret_key(value)
            except Exception:  # noqa: BLE001 - erro do backend ou valor inválido
                pass
        return self._fallback.get(vault_id)

    def set(self, vault_id: str, secret_bytes: bytes) -> None:
        _check_vault_id(vault_id)
        text = format_secret_key(secret_bytes)
        if self._keyring_ok:
            try:
                import keyring

                keyring.set_password(KEYRING_SERVICE, vault_id, text)
                return
            except Exception:  # noqa: BLE001 - backend quebrou: cai para arquivo
                self._keyring_ok = False
        self._fallback.set(vault_id, secret_bytes)

    def delete(self, vault_id: str) -> None:
        _check_vault_id(vault_id)
        if self._keyring_ok:
            try:
                import keyring

                keyring.delete_password(KEYRING_SERVICE, vault_id)
            except Exception:  # noqa: BLE001 - não existia ou backend indisponível
                pass
        self._fallback.delete(vault_id)

    @property
    def description(self) -> str:
        return _keyring_description() if self._keyring_ok else self._fallback.description

    def __repr__(self) -> str:
        return f"KeyringStore(keyring={self._keyring_ok})"


def default_store() -> SecretKeyStore:
    """Chaveiro do sistema se houver backend utilizável; senão arquivo na pasta do usuário."""
    if _backend_usable():
        return KeyringStore()
    return FileStore()
