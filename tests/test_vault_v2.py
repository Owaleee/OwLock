import base64
import json
import os
import stat
import sys

import pytest

from owlock.core import (
    Category, Entry, InvalidSecretKeyError, MemoryStore, MigrationError, SecretKeyRequiredError,
    Settings, Vault, VaultCorruptedError, VaultExistsError, WrongPasswordError, WrongSecretKeyError,
)
from owlock.core import crypto
from owlock.core import vault as vault_mod
from owlock.core.secret_key import format_secret_key, parse_secret_key
from owlock.core.vault import _create_v1

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"
NEW_PW = "nova-senha-123"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "sub" / "cofre.vault"


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def vault(path, store):
    return Vault.create(path, PW, store, kdf_params=FAST)


def full_entry():
    return Entry(service="ServicoSecreto", username="usuario.unico@x.com", password="P@ssUnica#987",
                 has_2fa=True, twofa_app="Authy", notes="nota qualquer", url="https://link.secreto.exemplo")


def doc_of(path):
    return json.loads(path.read_text())


def write_doc(path, doc):
    path.write_text(json.dumps(doc))


def bak_of(path):
    return path.with_name(path.name + ".bak")


# ---- criação e leitura ----
def test_create_writes_v2_header_and_key_before_file(path, store):
    order = []
    real_set = store.set

    def spy(vid, secret):
        order.append(("set", path.exists()))
        real_set(vid, secret)

    store.set = spy
    v = Vault.create(path, PW, store, kdf_params=FAST)
    assert order == [("set", False)]  # a chave foi guardada antes de o arquivo existir
    doc = doc_of(path)
    assert doc["format"] == "owlock-vault" and doc["version"] == 2
    assert len(doc["vault_id"]) == 32 and len(doc["secret_key"]["id"]) == 16
    assert doc["cipher"] == {"name": "aes-256-gcm"}
    assert doc["kdf"]["name"] == "argon2id" and len(base64.b64decode(doc["kdf"]["salt"])) == 16
    assert doc["entries"] == []
    assert store.get(doc["vault_id"]) == parse_secret_key(v.secret_key_formatted)
    assert Vault.peek(path) == {"version": 2, "vault_id": doc["vault_id"], "secret_key_id": doc["secret_key"]["id"]}


def test_create_existing_short_password_and_failing_store(path, store, tmp_path):
    Vault.create(path, PW, store, kdf_params=FAST)
    with pytest.raises(VaultExistsError):
        Vault.create(path, PW, store, kdf_params=FAST)
    with pytest.raises(ValueError):
        Vault.create(tmp_path / "outro.vault", "curta", store, kdf_params=FAST)

    class Broken(MemoryStore):
        def set(self, vault_id, secret_bytes):
            raise RuntimeError("chaveiro travado")

    with pytest.raises(OSError):
        Vault.create(tmp_path / "x.vault", PW, Broken(), kdf_params=FAST)
    assert not (tmp_path / "x.vault").exists()


def test_create_failure_on_write_removes_key_from_store(path, store, monkeypatch):
    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(vault_mod.os, "replace", boom)
    with pytest.raises(OSError):
        Vault.create(path, PW, store, kdf_params=FAST)
    assert store._data == {}
    assert not path.exists()


def test_secret_key_display_only_after_create_then_reveal(path, store, vault):
    shown = vault.secret_key_formatted
    assert shown.startswith("OW2-")
    again = Vault.open(path, PW, store)
    assert again.secret_key_formatted is None
    assert again.reveal_secret_key(PW) == shown
    vault.forget_secret_key_display()
    assert vault.secret_key_formatted is None


def test_everything_persists(path, store, vault):
    e = vault.add(full_entry())
    cat = vault.add_category(Category("Minha Categoria Secreta", "blue", "user"))
    vault.update_settings(Settings(15, 90))
    vault.update_services(
        [{"key": "custom-1", "name": "PortalSecreto", "aliases": ["ps"],
          "login_url": "https://portal.secreto.exemplo", "icon": ""}],
        {"steam": "https://outro.exemplo/"},
    )
    vault.update(Entry.from_dict({**e.to_dict(), "password": "nova-senha-da-conta"}))
    again = Vault.open(path, PW, store)
    assert [x.service for x in again.entries] == ["ServicoSecreto"]
    assert again.entries[0].password == "nova-senha-da-conta"
    assert again.entries[0].password_history[0]["password"] == "P@ssUnica#987"
    assert cat.id in [c.id for c in again.categories]
    assert again.settings == Settings(15, 90)
    assert again.services["custom"][0]["name"] == "PortalSecreto"
    assert again.services["overrides"] == {"steam": "https://outro.exemplo/"}
    again.delete(e.id)
    assert Vault.open(path, PW, store).entries == []


def test_file_has_no_plaintext(path, vault):
    vault.add(full_entry())
    vault.add_category(Category("Minha Categoria Secreta", "blue", "user"))
    vault.update_services([{"key": "c1", "name": "PortalSecreto", "aliases": [],
                            "login_url": "https://portal.secreto.exemplo", "icon": ""}], {})
    data = path.read_bytes()
    for s in (b"ServicoSecreto", b"usuario.unico", b"P@ssUnica", b"Authy", b"nota qualquer",
              b"Minha Categoria Secreta", b"link.secreto", b"PortalSecreto", b"portal.secreto"):
        assert s not in data
    bak = bak_of(path).read_bytes()
    assert b"ServicoSecreto" not in bak


@pytest.mark.skipif(sys.platform == "win32", reason="permissões POSIX")
def test_file_permissions_600(path, vault):
    vault.add(full_entry())
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_repr_does_not_expose_keys(vault):
    text = repr(vault) + str(vault)
    assert vault.secret_key_formatted not in text
    assert vault._vault_key.hex() not in text and vault._kek.hex() not in text


# ---- senha e chave ----
def test_wrong_password_leaves_file_intact(path, store, vault):
    vault.add(full_entry())
    before = path.read_bytes()
    with pytest.raises(WrongPasswordError):
        Vault.open(path, "senha-errada-xx", store)
    assert path.read_bytes() == before


def test_wrong_secret_key(path, store, vault):
    other = format_secret_key(bytes(range(16)) + b"\x40")
    assert other != vault.secret_key_formatted
    with pytest.raises(WrongSecretKeyError):
        Vault.open(path, PW, store, secret_key=other)
    # nem a senha certa salva: chave errada vem antes
    with pytest.raises(WrongSecretKeyError):
        Vault.open(path, "senha-errada-xx", store, secret_key=other)
    # a chave errada não foi parar no store
    assert store.get(vault.vault_id) == parse_secret_key(vault.secret_key_formatted)


def test_stale_wrong_key_in_store(path, store, vault):
    store.set(vault.vault_id, bytes(range(16)) + b"\x40")
    with pytest.raises(WrongSecretKeyError):
        Vault.open(path, PW, store)
    opened = Vault.open(path, PW, store, secret_key=vault.secret_key_formatted)
    assert store.get(vault.vault_id) == parse_secret_key(vault.secret_key_formatted)
    assert opened.vault_id == vault.vault_id


def test_secret_key_required_when_store_is_empty(path, vault):
    with pytest.raises(SecretKeyRequiredError):
        Vault.open(path, PW, MemoryStore())


def test_invalid_secret_key_text(path, store, vault):
    with pytest.raises(InvalidSecretKeyError):
        Vault.open(path, PW, store, secret_key="isto não é uma chave")


def test_right_key_on_empty_store_opens_and_saves_to_store(path, vault):
    fresh = MemoryStore()
    shown = vault.secret_key_formatted
    opened = Vault.open(path, PW, fresh, secret_key=shown.lower().replace("-", " "))
    assert fresh.get(opened.vault_id) == parse_secret_key(shown)
    assert Vault.open(path, PW, fresh).vault_id == opened.vault_id  # próxima vez sem digitar


def test_key_given_but_store_save_fails_still_opens(path, vault):
    class Broken(MemoryStore):
        def set(self, vault_id, secret_bytes):
            raise RuntimeError("travado")

    opened = Vault.open(path, PW, Broken(), secret_key=vault.secret_key_formatted)
    assert opened.secret_key_persisted is False


def test_store_get_failing_means_key_required(path, vault):
    class Broken(MemoryStore):
        def get(self, vault_id):
            raise RuntimeError("travado")

    with pytest.raises(SecretKeyRequiredError):
        Vault.open(path, PW, Broken())


def test_key_and_password_both_matter(path, store, vault):
    # só com os dois certos abre; senha certa + chave de outro cofre não
    other = Vault.create(path.with_name("b.vault"), PW, store, kdf_params=FAST)
    with pytest.raises(WrongSecretKeyError):
        Vault.open(path, PW, store, secret_key=other.secret_key_formatted)


# ---- adulteração ----
@pytest.mark.parametrize("mutate", [
    lambda d: d["kdf"].__setitem__("salt", base64.b64encode(os.urandom(16)).decode()),
    lambda d: d["kdf"].__setitem__("memory_cost", 16384),
    lambda d: d["kdf"].__setitem__("time_cost", 2),
    lambda d: d["secret_key"].__setitem__("id", "0123456789abcdef"),
    lambda d: d.__setitem__("vault_id", "f" * 32),
])
def test_header_tampering_never_opens(path, store, vault, mutate):
    vault.add(full_entry())
    doc = doc_of(path)
    mutate(doc)
    write_doc(path, doc)
    errors = (WrongPasswordError, WrongSecretKeyError, VaultCorruptedError, SecretKeyRequiredError)
    with pytest.raises(errors):
        Vault.open(path, PW, store)
    with pytest.raises(errors):
        Vault.open(path, PW, store, secret_key=vault.secret_key_formatted)


def test_tampered_key_ciphertext_is_wrong_password(path, store, vault):
    doc = doc_of(path)
    ct = bytearray(base64.b64decode(doc["key"]["ciphertext"]))
    ct[0] ^= 1
    doc["key"]["ciphertext"] = base64.b64encode(bytes(ct)).decode()
    write_doc(path, doc)
    with pytest.raises(WrongPasswordError):
        Vault.open(path, PW, store)


def test_tampered_meta_and_entry_are_corrupted(path, store, vault):
    vault.add(full_entry())
    for block in ("meta", "entry"):
        doc = doc_of(path)
        target = doc["meta"] if block == "meta" else doc["entries"][0]
        ct = bytearray(base64.b64decode(target["ciphertext"]))
        ct[0] ^= 1
        target["ciphertext"] = base64.b64encode(bytes(ct)).decode()
        write_doc(path, doc)
        with pytest.raises(VaultCorruptedError):
            Vault.open(path, PW, store)
        vault.save()  # restaura


def test_swapping_ciphertext_between_entries_is_corrupted(path, store, vault):
    vault.add(Entry(service="Um", password="p1"))
    vault.add(Entry(service="Dois", password="p2"))
    doc = doc_of(path)
    a, b = doc["entries"]
    a["nonce"], b["nonce"] = b["nonce"], a["nonce"]
    a["ciphertext"], b["ciphertext"] = b["ciphertext"], a["ciphertext"]
    write_doc(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)


def test_swapping_external_ids_is_corrupted(path, store, vault):
    vault.add(Entry(service="Um", password="p1"))
    vault.add(Entry(service="Dois", password="p2"))
    doc = doc_of(path)
    doc["entries"][0]["id"], doc["entries"][1]["id"] = doc["entries"][1]["id"], doc["entries"][0]["id"]
    write_doc(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)


def test_duplicate_entry_id_is_corrupted(path, store, vault):
    vault.add(Entry(service="Um", password="p1"))
    doc = doc_of(path)
    doc["entries"].append(dict(doc["entries"][0]))
    write_doc(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)


def test_removing_an_entry_opens_without_it_known_limitation(path, store, vault):
    """Limitação conhecida: remover uma entrada do JSON não é detectado (cada uma é autenticada sozinha)."""
    vault.add(Entry(service="Um", password="p1"))
    vault.add(Entry(service="Dois", password="p2"))
    doc = doc_of(path)
    del doc["entries"][0]
    write_doc(path, doc)
    assert [e.service for e in Vault.open(path, PW, store).entries] == ["Dois"]


def test_internal_id_must_match_external(path, store, vault):
    e = vault.add(Entry(service="Um", password="p1"))
    doc = doc_of(path)
    old = doc["entries"][0]
    vid = doc["vault_id"]
    # reencripta com o id externo novo, mas conteúdo com id antigo
    new_id = "1" * 32
    n, c = crypto.encrypt(vault._vault_key, json.dumps(e.to_dict()).encode(),
                          b"owlock-v2|" + vid.encode() + b"|entry|" + new_id.encode())
    old.update(id=new_id, nonce=base64.b64encode(n).decode(), ciphertext=base64.b64encode(c).decode())
    write_doc(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)


@pytest.mark.parametrize("mutate", [
    lambda d: d.__setitem__("vault_id", "XYZ"),
    lambda d: d.__setitem__("vault_id", 5),
    lambda d: d["secret_key"].__setitem__("id", "curto"),
    lambda d: d.__setitem__("secret_key", "x"),
    lambda d: d["kdf"].__setitem__("salt", "!!!"),
    lambda d: d["kdf"].__setitem__("salt", base64.b64encode(b"curto").decode()),
    lambda d: d["key"].__setitem__("nonce", base64.b64encode(b"123").decode()),
    lambda d: d["meta"].__setitem__("nonce", base64.b64encode(b"x" * 13).decode()),
    lambda d: d["key"].__setitem__("ciphertext", "***"),
    lambda d: d.__setitem__("entries", "x"),
    lambda d: d.__setitem__("entries", [1]),
    lambda d: d.__setitem__("entries", [{"id": "a", "nonce": "AAAA"}]),
    lambda d: d["cipher"].__setitem__("name", "rot13"),
    lambda d: d["kdf"].__setitem__("name", "md5"),
    lambda d: d.__setitem__("version", 3),
    lambda d: d.__setitem__("version", "2"),
    lambda d: d.__setitem__("format", "outro"),
    lambda d: d.pop("meta"),
    lambda d: d.pop("kdf"),
])
def test_structural_validation(path, store, vault, mutate):
    doc = doc_of(path)
    mutate(doc)
    write_doc(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)


def test_broken_json_and_missing_file(path, store, vault, tmp_path):
    path.write_text("{ nao e json")
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)
    with pytest.raises(VaultCorruptedError):
        Vault.peek(path)
    with pytest.raises(FileNotFoundError):
        Vault.open(tmp_path / "nao.vault", PW, store)
    with pytest.raises(FileNotFoundError):
        Vault.peek(tmp_path / "nao.vault")


@pytest.mark.parametrize("field,value", [
    ("memory_cost", 10**9), ("memory_cost", 1), ("time_cost", 0), ("time_cost", 999),
    ("parallelism", 0), ("parallelism", 100), ("time_cost", True), ("memory_cost", "8192"),
])
def test_kdf_limits_checked_before_deriving(path, store, vault, monkeypatch, field, value):
    def boom(*a, **k):
        raise AssertionError("não deveria derivar")

    monkeypatch.setattr(crypto, "derive_key", boom)
    monkeypatch.setattr(crypto, "derive_kek", boom)
    doc = doc_of(path)
    doc["kdf"][field] = value
    write_doc(path, doc)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW, store)


def test_nothing_derived_when_key_missing_or_wrong(path, store, vault, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("não deveria derivar")

    monkeypatch.setattr(crypto, "derive_key", boom)
    with pytest.raises(SecretKeyRequiredError):
        Vault.open(path, PW, MemoryStore())
    with pytest.raises(WrongSecretKeyError):
        Vault.open(path, PW, store, secret_key=format_secret_key(bytes(range(16)) + b"\x40"))


# ---- nonces, save, backup ----
def test_fresh_nonces_on_every_save(path, vault):
    vault.add(full_entry())
    first = doc_of(path)
    vault.save()
    second = doc_of(path)
    assert first["key"]["nonce"] != second["key"]["nonce"]
    assert first["meta"]["nonce"] != second["meta"]["nonce"]
    assert first["entries"][0]["nonce"] != second["entries"][0]["nonce"]
    assert first["entries"][0]["id"] == second["entries"][0]["id"]
    assert first["entries"][0]["ciphertext"] != second["entries"][0]["ciphertext"]


def test_backup_and_no_tmp(path, vault):
    vault.add(full_entry())
    assert bak_of(path).exists()
    assert not path.with_name(path.name + ".tmp").exists()


def test_duplicate_ids_are_refused_at_save(path, vault):
    e = vault.add(Entry(service="Um"))
    with pytest.raises(ValueError):
        vault.add(Entry(service="Dois", id=e.id))
    assert len(vault.entries) == 1


def _fail_replace(monkeypatch):
    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(vault_mod.os, "replace", boom)


def test_failed_save_rolls_back_and_file_stays_good(path, store, vault, monkeypatch):
    vault.add(full_entry())
    before = path.read_bytes()
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.add(Entry(service="Outro"))
    assert len(vault.entries) == 1
    assert path.read_bytes() == before
    assert not path.with_name(path.name + ".tmp").exists()
    monkeypatch.undo()
    assert len(Vault.open(path, PW, store).entries) == 1


# ---- troca de senha mestra ----
def test_change_master_password(path, store, vault):
    e = vault.add(full_entry())
    vault.add_category(Category("Extra", "blue", "user"))
    shown = vault.secret_key_formatted
    key_id = doc_of(path)["secret_key"]["id"]
    vid = doc_of(path)["vault_id"]
    salt_before = doc_of(path)["kdf"]["salt"]
    with pytest.raises(WrongPasswordError):
        vault.change_master_password("errada-errada", NEW_PW)
    with pytest.raises(ValueError):
        vault.change_master_password(PW, "curta")
    vault.change_master_password(PW, NEW_PW)
    doc = doc_of(path)
    assert doc["kdf"]["salt"] != salt_before
    assert doc["secret_key"]["id"] == key_id and doc["vault_id"] == vid  # mesma Chave Secreta
    with pytest.raises(WrongPasswordError):
        Vault.open(path, PW, store)
    again = Vault.open(path, NEW_PW, store)
    assert again.entries == [e] and len(again.categories) == 7
    assert again.reveal_secret_key(NEW_PW) == shown
    # .bak: abre com a senha nova e NÃO com a antiga
    assert bak_of(path).read_bytes() == path.read_bytes()
    backup_copy = path.with_name("restaurado.vault")
    backup_copy.write_bytes(bak_of(path).read_bytes())
    assert Vault.open(backup_copy, NEW_PW, store).entries == [e]
    with pytest.raises(WrongPasswordError):
        Vault.open(backup_copy, PW, store)


def test_change_master_password_failure_restores_state(path, store, vault, monkeypatch):
    vault.add(full_entry())
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.change_master_password(PW, NEW_PW)
    monkeypatch.undo()
    vault.save()
    assert len(Vault.open(path, PW, store).entries) == 1
    with pytest.raises(WrongPasswordError):
        Vault.open(path, NEW_PW, store)


def test_change_master_password_keeps_working_after(path, store, vault):
    vault.change_master_password(PW, NEW_PW)
    vault.add(full_entry())
    assert len(Vault.open(path, NEW_PW, store).entries) == 1
    vault.change_master_password(NEW_PW, "terceira-senha-9")
    assert len(Vault.open(path, "terceira-senha-9", store).entries) == 1


def test_reveal_secret_key(vault, path, store):
    assert vault.reveal_secret_key(PW) == vault.secret_key_formatted
    with pytest.raises(WrongPasswordError):
        vault.reveal_secret_key("senha-errada-xx")
    assert Vault.open(path, PW, store).reveal_secret_key(PW) == vault.secret_key_formatted


def test_peek_v1_and_v2(path, tmp_path, vault):
    assert Vault.peek(path)["version"] == 2
    old = tmp_path / "velho.vault"
    _create_v1(old, PW, FAST)
    assert Vault.peek(old) == {"version": 1, "vault_id": None, "secret_key_id": None}


# ---- migração v1 -> v2 ----
def make_v1(path):
    entries = [full_entry(), Entry(service="Outra", username="u", password="p")]
    cats = [Category("Cat Secreta", "blue", "user")]
    _create_v1(path, PW, FAST, entries=entries, categories=cats,
               settings=Settings(10, 60),
               services={"custom": [], "overrides": {"steam": "https://x.exemplo/"}})
    return entries


def test_migration_v1_to_v2(path, store):
    entries = make_v1(path)
    original = path.read_bytes()
    assert json.loads(original)["version"] == 1
    v = Vault.open(path, PW, store)
    assert v.migrated is True
    assert v.v1_backup_path == path.with_name(path.name + ".v1-backup")
    assert v.v1_backup_path.read_bytes() == original
    assert [e.service for e in v.entries] == [e.service for e in entries]
    assert [c.name for c in v.categories] == ["Cat Secreta"]
    assert v.settings == Settings(10, 60)
    assert v.services["overrides"] == {"steam": "https://x.exemplo/"}
    doc = doc_of(path)
    assert doc["version"] == 2
    assert store.get(doc["vault_id"]) == parse_secret_key(v.secret_key_formatted)
    # .bak não guarda o v1 (que abriria sem a Chave Secreta)
    assert doc_of(bak_of(path))["version"] == 2
    # segunda abertura já é v2, sem migrar
    second = Vault.open(path, PW, store)
    assert second.migrated is False and second.v1_backup_path is None
    assert [e.service for e in second.entries] == [e.service for e in entries]
    assert b"ServicoSecreto" not in path.read_bytes()
    # sem a chave no store: pede a chave
    with pytest.raises(SecretKeyRequiredError):
        Vault.open(path, PW, MemoryStore())


def test_migration_wrong_password_changes_nothing(path, store):
    make_v1(path)
    original = path.read_bytes()
    with pytest.raises(WrongPasswordError):
        Vault.open(path, "senha-errada-xx", store)
    assert path.read_bytes() == original
    assert store._data == {}
    assert not path.with_name(path.name + ".v1-backup").exists()


def test_migration_does_not_overwrite_existing_backup(path, store):
    make_v1(path)
    first = path.with_name(path.name + ".v1-backup")
    first.write_bytes(b"cofre antigo anterior")
    v = Vault.open(path, PW, store)
    assert first.read_bytes() == b"cofre antigo anterior"
    assert v.v1_backup_path == path.with_name(path.name + ".v1-backup.2")
    assert json.loads(v.v1_backup_path.read_bytes())["version"] == 1


def test_migration_store_failure_leaves_file_untouched(path):
    make_v1(path)
    original = path.read_bytes()

    class Broken(MemoryStore):
        def set(self, vault_id, secret_bytes):
            raise RuntimeError("chaveiro travado")

    with pytest.raises(MigrationError):
        Vault.open(path, PW, Broken())
    assert path.read_bytes() == original
    assert not path.with_name(path.name + ".v1-backup").exists()
    assert not bak_of(path).exists()
    assert not path.with_name(path.name + ".tmp").exists()
    # e ainda dá para migrar depois
    assert Vault.open(path, PW, MemoryStore()).migrated is True


def test_migration_write_failure_leaves_file_untouched(path, store, monkeypatch):
    make_v1(path)
    original = path.read_bytes()
    _fail_replace(monkeypatch)
    with pytest.raises(MigrationError):
        Vault.open(path, PW, store)
    monkeypatch.undo()
    assert path.read_bytes() == original
    assert not path.with_name(path.name + ".v1-backup").exists()  # cópia inútil é removida
    assert not path.with_name(path.name + ".tmp").exists()
    assert store._data == {}  # chave órfã removida do store


def test_migration_backup_failure_leaves_file_untouched(path, store, monkeypatch):
    make_v1(path)
    original = path.read_bytes()

    def boom(*a, **k):
        raise OSError("sem espaço")

    monkeypatch.setattr(Vault, "_unique_backup_path", staticmethod(boom))
    with pytest.raises(MigrationError):
        Vault.open(path, PW, store)
    assert path.read_bytes() == original
    assert store._data == {}
