import json

import pytest

from owlock.core import (
    CATEGORY_COLORS, CATEGORY_ICONS, Category, Entry, Vault, VaultCorruptedError,
)
from owlock.core import vault as vault_mod
from owlock.core import crypto

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"

DEFAULTS = [
    ("Pessoal", "mint", "user"),
    ("Trabalho", "blue", "briefcase"),
    ("Jogos", "violet", "gamepad"),
    ("Redes sociais", "pink", "chat"),
    ("Financeiro", "amber", "card"),
    ("Streaming", "coral", "play"),
]


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


@pytest.fixture
def vault(path):
    return Vault.create(path, PW, kdf_params=FAST)


def _rewrite_plain(path, mutate):
    """Reescreve o conteúdo cifrado do cofre, aplicando `mutate` ao dict claro."""
    doc = json.loads(path.read_text())
    import base64

    salt = base64.b64decode(doc["kdf"]["salt"])
    params = {k: doc["kdf"][k] for k in ("time_cost", "memory_cost", "parallelism")}
    header = Vault._header(salt, params)
    key = crypto.derive_key(PW, salt, **params)
    plain = crypto.decrypt(
        key, base64.b64decode(doc["cipher"]["nonce"]),
        base64.b64decode(doc["ciphertext"]), Vault._aad(header),
    )
    data = mutate(json.loads(plain))
    nonce, ct = crypto.encrypt(key, json.dumps(data).encode(), Vault._aad(header))
    doc["cipher"]["nonce"] = base64.b64encode(nonce).decode()
    doc["ciphertext"] = base64.b64encode(ct).decode()
    path.write_text(json.dumps(doc))


def test_palette_and_icons():
    assert list(CATEGORY_COLORS) == [
        "mint", "blue", "violet", "pink", "amber", "coral", "lime", "gray"
    ]
    assert CATEGORY_COLORS["mint"] == "#9FE3D3"
    assert CATEGORY_COLORS["gray"] == "#A1A6B4"
    assert CATEGORY_ICONS == (
        "user", "briefcase", "gamepad", "chat", "card", "play",
        "home", "cart", "school", "code", "heart", "star",
    )


def test_category_dict_roundtrip_and_validation():
    c = Category("Teste", "pink", "home")
    assert Category.from_dict(c.to_dict()) == c
    assert Category.from_dict({"id": "x", "name": "N", "extra": 1}).id == "x"
    with pytest.raises(ValueError):
        Category.from_dict({"name": "sem id"})
    with pytest.raises(ValueError):
        Category.from_dict({"id": "x"})
    with pytest.raises(ValueError):
        Category.from_dict("texto")


def test_new_vault_has_default_categories(path, vault):
    assert [(c.name, c.color, c.icon) for c in vault.categories] == DEFAULTS
    assert len({c.id for c in vault.categories}) == 6
    again = Vault.open(path, PW)
    assert again.categories == vault.categories


def test_old_vault_without_key_gets_defaults_and_persists(path, vault):
    vault.add(Entry("Antiga", "u", "p"))
    _rewrite_plain(path, lambda d: {"entries": d["entries"]})
    old = Vault.open(path, PW)
    assert [(c.name, c.color, c.icon) for c in old.categories] == DEFAULTS
    ids_first = [c.id for c in old.categories]
    old.save()
    again = Vault.open(path, PW)
    assert [c.id for c in again.categories] == ids_first
    assert len(again.entries) == 1


def test_present_empty_key_does_not_recreate(path, vault):
    _rewrite_plain(path, lambda d: {**d, "categories": []})
    assert Vault.open(path, PW).categories == []


def test_entry_without_category_id_opens_empty(path, vault):
    vault.add(Entry("Antiga", "u", "p"))

    def strip(d):
        for e in d["entries"]:
            e.pop("category_id", None)
        return d

    _rewrite_plain(path, strip)
    assert Vault.open(path, PW).entries[0].category_id == ""


def test_invalid_category_in_file_is_corrupted(path, vault):
    _rewrite_plain(path, lambda d: {**d, "categories": [{"name": "sem id"}]})
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)
    _rewrite_plain(path, lambda d: {**d, "categories": ["texto"]})
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def test_add_update_delete_category(path, vault):
    c = vault.add_category(Category("Estudos", "lime", "school"))
    assert Vault.open(path, PW).categories[-1] == c
    vault.update_category(Category("Faculdade", "blue", "code", id=c.id))
    reopened = Vault.open(path, PW)
    assert (reopened.categories[-1].name, reopened.categories[-1].icon) == ("Faculdade", "code")
    vault.delete_category(c.id)
    assert c.id not in [x.id for x in Vault.open(path, PW).categories]
    with pytest.raises(KeyError):
        vault.update_category(Category("X", id="nao-existe"))
    with pytest.raises(KeyError):
        vault.delete_category("nao-existe")


def test_delete_category_moves_entries_and_saves_once(path, vault, monkeypatch):
    cat = vault.categories[0]
    other = vault.categories[1]
    a = vault.add(Entry("A", category_id=cat.id))
    b = vault.add(Entry("B", category_id=cat.id))
    c = vault.add(Entry("C", category_id=other.id))
    calls = []
    real_save = Vault.save
    monkeypatch.setattr(Vault, "save", lambda self: (calls.append(1), real_save(self))[1])
    assert vault.delete_category(cat.id) == 2
    assert len(calls) == 1
    again = Vault.open(path, PW)
    by_service = {e.service: e.category_id for e in again.entries}
    assert by_service == {"A": "", "B": "", "C": other.id}
    assert a.category_id == b.category_id == "" and c.category_id == other.id


def _fail_replace(monkeypatch):
    def boom(*a, **k):
        raise OSError("falha simulada")

    monkeypatch.setattr(vault_mod.os, "replace", boom)


def test_category_failures_roll_back(path, vault, monkeypatch):
    cat = vault.categories[0]
    entry = vault.add(Entry("A", category_id=cat.id))
    before = list(vault.categories)
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        vault.add_category(Category("Nova"))
    assert vault.categories == before
    with pytest.raises(OSError):
        vault.update_category(Category("Renomeada", id=cat.id))
    assert vault.categories == before and vault.categories[0].name == "Pessoal"
    with pytest.raises(OSError):
        vault.delete_category(cat.id)
    assert vault.categories == before
    assert entry.category_id == cat.id
