import base64
import json

import pytest

from cofre.core import (
    Entry, Vault, VaultCorruptedError, VaultExistsError, WrongPasswordError,
)

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "sub" / "cofre.vault"


@pytest.fixture
def vault(path):
    return Vault.create(path, PW, kdf_params=FAST)


def _full_entry():
    return Entry(service="ServicoSecreto", username="usuario.unico@x.com",
                 password="P@ssUnica#987", has_2fa=True, twofa_app="Authy",
                 notes="nota qualquer")


def _doc(path):
    return json.loads(path.read_text())


def _write(path, doc):
    path.write_text(json.dumps(doc))


def test_roundtrip(path, vault):
    e = vault.add(_full_entry())
    again = Vault.open(path, PW)
    assert again.entries == [e]


def test_wrong_password_leaves_file_intact(path, vault):
    vault.add(_full_entry())
    before = path.read_bytes()
    with pytest.raises(WrongPasswordError):
        Vault.open(path, "senha-errada-xx")
    assert path.read_bytes() == before


def test_tampered_ciphertext(path, vault):
    vault.add(_full_entry())
    doc = _doc(path)
    ct = bytearray(base64.b64decode(doc["ciphertext"]))
    ct[0] ^= 1
    doc["ciphertext"] = base64.b64encode(bytes(ct)).decode()
    _write(path, doc)
    with pytest.raises(WrongPasswordError):
        Vault.open(path, PW)


def test_tampered_kdf_param_detected(path, vault):
    doc = _doc(path)
    doc["kdf"]["memory_cost"] = 16384
    _write(path, doc)
    with pytest.raises((WrongPasswordError, VaultCorruptedError)):
        Vault.open(path, PW)


def test_broken_json(path, vault):
    path.write_text("{ nao e json")
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def test_unknown_version(path, vault):
    doc = _doc(path)
    doc["version"] = 2
    _write(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def test_absurd_memory_cost_rejected_without_deriving(path, vault, monkeypatch):
    from cofre.core import crypto

    def boom(*a, **k):
        raise AssertionError("não deveria derivar")

    monkeypatch.setattr(crypto, "derive_key", boom)
    doc = _doc(path)
    doc["kdf"]["memory_cost"] = 10**9
    _write(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def test_missing_fields_and_bad_base64(path, vault):
    doc = _doc(path)
    del doc["ciphertext"]
    _write(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)
    doc = _doc_with_bad_b64(path)
    _write(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def _doc_with_bad_b64(path):
    return {
        "format": "cofre-vault", "version": 1,
        "kdf": {"name": "argon2id", "salt": "!!!", **FAST},
        "cipher": {"name": "aes-256-gcm", "nonce": "AAAA"},
        "ciphertext": "AAAA",
    }


def test_open_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        Vault.open(tmp_path / "nao-existe.vault", PW)


def test_file_has_no_plaintext(path, vault):
    vault.add(_full_entry())
    data = path.read_bytes()
    for s in (b"ServicoSecreto", b"usuario.unico", b"P@ssUnica#987", b"Authy"):
        assert s not in data


def test_nonce_changes_between_saves(path, vault):
    n1 = _doc(path)["cipher"]["nonce"]
    vault.save()
    n2 = _doc(path)["cipher"]["nonce"]
    assert n1 != n2


def test_create_existing_and_short_password(path, vault, tmp_path):
    with pytest.raises(VaultExistsError):
        Vault.create(path, PW, kdf_params=FAST)
    with pytest.raises(ValueError):
        Vault.create(tmp_path / "outro.vault", "curta", kdf_params=FAST)
    assert not (tmp_path / "outro.vault").exists()


def test_update_delete_keyerror(vault):
    with pytest.raises(KeyError):
        vault.update(Entry(service="X", id="nao-existe"))
    with pytest.raises(KeyError):
        vault.delete("nao-existe")


def test_update_changes_updated_at_keeps_created_at(path, vault):
    e = vault.add(_full_entry())
    e.created_at = e.updated_at = "2000-01-01T00:00:00+00:00"
    vault.save()
    changed = Entry.from_dict({**e.to_dict(), "notes": "novo",
                               "created_at": "1999-01-01T00:00:00+00:00"})
    vault.update(changed)
    got = Vault.open(path, PW).entries[0]
    assert got.notes == "novo"
    assert got.created_at == "2000-01-01T00:00:00+00:00"
    assert got.updated_at != "2000-01-01T00:00:00+00:00"


def test_delete(path, vault):
    e = vault.add(_full_entry())
    vault.delete(e.id)
    assert Vault.open(path, PW).entries == []


def test_search(vault):
    vault.add(Entry(service="Google", username="a@x.com", password="zzsecretzz"))
    vault.add(Entry(service="Steam", notes="Autenticação por app"))
    assert len(vault.search("")) == 2
    assert [e.service for e in vault.search("goo")] == ["Google"]
    assert [e.service for e in vault.search("STEAM")] == ["Steam"]
    assert [e.service for e in vault.search("autenticacao")] == ["Steam"]
    assert vault.search("secret") == []


def test_change_master_password(path, vault):
    vault.add(_full_entry())
    salt_before = _doc(path)["kdf"]["salt"]
    with pytest.raises(WrongPasswordError):
        vault.change_master_password("errada-errada", "nova-senha-123")
    with pytest.raises(ValueError):
        vault.change_master_password(PW, "curta")
    vault.change_master_password(PW, "nova-senha-123")
    assert _doc(path)["kdf"]["salt"] != salt_before
    with pytest.raises(WrongPasswordError):
        Vault.open(path, PW)
    assert len(Vault.open(path, "nova-senha-123").entries) == 1


def test_backup_after_second_save(path, vault):
    bak = path.with_name(path.name + ".bak")
    vault.add(_full_entry())
    assert bak.exists()
    assert not path.with_name(path.name + ".tmp").exists()


def _fail_replace(monkeypatch):
    from cofre.core import vault as vault_mod

    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(vault_mod.os, "replace", boom)


def test_add_failure_rolls_back(path, vault, monkeypatch):
    vault.add(_full_entry())
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.add(Entry(service="Outro"))
    assert len(vault.entries) == 1
    monkeypatch.undo()
    assert [e.service for e in Vault.open(path, PW).entries] == ["ServicoSecreto"]


def test_update_failure_rolls_back(path, vault, monkeypatch):
    e = vault.add(_full_entry())
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.update(Entry.from_dict({**e.to_dict(), "notes": "mudou"}))
    assert vault.entries[0].notes == "nota qualquer"


def test_delete_failure_keeps_entry(vault, monkeypatch):
    e = vault.add(_full_entry())
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.delete(e.id)
    assert len(vault.entries) == 1


def test_change_master_failure_restores_key(path, vault, monkeypatch):
    vault.add(_full_entry())
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.change_master_password(PW, "nova-senha-123")
    monkeypatch.undo()
    assert len(Vault.open(path, PW).entries) == 1
    vault.save()
    assert len(Vault.open(path, PW).entries) == 1
    with pytest.raises(WrongPasswordError):
        Vault.open(path, "nova-senha-123")


def test_no_tmp_left_after_failure(path, vault, monkeypatch):
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.add(Entry(service="Outro"))
    assert not path.with_name(path.name + ".tmp").exists()
