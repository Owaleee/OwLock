import os
import stat
import sys

import keyring
import pytest
from keyring.backends import fail
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError

from owlock.core import FileStore, KeyringStore, MemoryStore, default_store
from owlock.core import keystore as keystore_mod
from owlock.core.secret_key import generate_secret_key

VID = "ab" * 16
VID2 = "cd" * 16


class MemoryKeyring(KeyringBackend):
    """Backend de chaveiro em memória para os testes."""

    priority = 1

    def __init__(self):
        super().__init__()
        self.data = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.data:
            raise keyring.errors.PasswordDeleteError("não existe")
        del self.data[(service, username)]


class BrokenKeyring(MemoryKeyring):
    def get_password(self, service, username):
        raise KeyringError("travado")

    def set_password(self, service, username, password):
        raise KeyringError("travado")


@pytest.fixture(autouse=True)
def _restore_keyring():
    previous = keyring.get_keyring()
    yield
    keyring.set_keyring(previous)


def test_memory_store_roundtrip():
    s = MemoryStore()
    key = generate_secret_key()
    assert s.get(VID) is None
    s.set(VID, key)
    assert s.get(VID) == key and s.get(VID2) is None
    s.delete(VID)
    s.delete(VID)  # inexistente: sem erro
    assert s.get(VID) is None


def test_store_rejects_bad_vault_id(tmp_path):
    for store in (MemoryStore(), FileStore(tmp_path)):
        for bad in ("../x", "abc", "", "AB" * 16, "ab" * 16 + "/"):
            with pytest.raises(ValueError):
                store.get(bad)
            with pytest.raises(ValueError):
                store.set(bad, generate_secret_key())


def test_file_store_roundtrip_missing_and_delete(tmp_path):
    s = FileStore(tmp_path / "keys")
    key = generate_secret_key()
    assert s.get(VID) is None
    s.set(VID, key)
    assert (tmp_path / "keys" / f"{VID}.key").is_file()
    assert s.get(VID) == key
    s.set(VID, generate_secret_key())  # sobrescreve
    assert s.get(VID) != key
    s.delete(VID)
    s.delete(VID)
    assert s.get(VID) is None
    assert "arquivo protegido" in s.description


@pytest.mark.skipif(sys.platform == "win32", reason="permissões POSIX")
def test_file_store_permissions_are_600(tmp_path):
    s = FileStore(tmp_path / "keys")
    s.set(VID, generate_secret_key())
    mode = stat.S_IMODE(os.stat(tmp_path / "keys" / f"{VID}.key").st_mode)
    assert mode == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "keys").st_mode) == 0o700


def test_file_store_is_atomic_and_leaves_no_tmp(tmp_path, monkeypatch):
    s = FileStore(tmp_path)
    old = generate_secret_key()
    s.set(VID, old)

    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(keystore_mod.os, "replace", boom)
    with pytest.raises(OSError):
        s.set(VID, generate_secret_key())
    monkeypatch.undo()
    assert s.get(VID) == old  # o valor antigo continua inteiro
    assert [p.name for p in tmp_path.iterdir()] == [f"{VID}.key"]


def test_file_store_ignores_garbage_file(tmp_path):
    (tmp_path / f"{VID}.key").write_text("lixo")
    assert FileStore(tmp_path).get(VID) is None


def test_keyring_store_with_fake_backend(tmp_path):
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    s = KeyringStore(fallback=FileStore(tmp_path))
    key = generate_secret_key()
    assert s.get(VID) is None
    s.set(VID, key)
    assert s.get(VID) == key
    # serviço "OwLock", usuário = vault_id, valor = chave formatada
    value = backend.data[("OwLock", VID)]
    assert value.startswith("OW2-")
    assert list(tmp_path.iterdir()) == []  # nada foi para o arquivo
    assert s.description in (
        "Gerenciador de Credenciais do Windows", "Keychain do macOS", "Chaveiro do sistema")
    s.delete(VID)
    assert s.get(VID) is None
    s.delete(VID)  # inexistente: sem erro


def test_keyring_store_falls_back_when_backend_is_fail(tmp_path):
    keyring.set_keyring(fail.Keyring())
    s = KeyringStore(fallback=FileStore(tmp_path))
    key = generate_secret_key()
    s.set(VID, key)
    assert (tmp_path / f"{VID}.key").is_file()
    assert s.get(VID) == key
    assert "arquivo protegido" in s.description


def test_keyring_store_falls_back_when_backend_raises(tmp_path):
    keyring.set_keyring(BrokenKeyring())
    s = KeyringStore(fallback=FileStore(tmp_path))
    key = generate_secret_key()
    s.set(VID, key)
    assert s.get(VID) == key
    assert (tmp_path / f"{VID}.key").is_file()
    assert "arquivo protegido" in s.description


def test_default_store_choice(tmp_path):
    keyring.set_keyring(fail.Keyring())
    assert isinstance(default_store(), FileStore)
    keyring.set_keyring(MemoryKeyring())
    assert isinstance(default_store(), KeyringStore)
