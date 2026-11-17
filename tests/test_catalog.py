import json

import pytest

from owlock.core import Catalog, Entry, Vault, VaultCorruptedError, normalize
from owlock.core import catalog as catalog_module
from tests.test_categories import _rewrite_plain

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


@pytest.fixture
def vault(path):
    return Vault.create(path, PW, kdf_params=FAST)


def custom(name="Portal", aliases=(), url="https://portal.exemplo.edu.br", icon="", key="custom-1"):
    return {"key": key, "name": name, "aliases": list(aliases), "login_url": url, "icon": icon}


# ---- normalize ----
@pytest.mark.parametrize(
    "text,expected",
    [("Epic Games", "epicgames"), ("gov.br", "govbr"), ("  Itaú  ", "itau"), ("Ação-123!", "acao123"), ("", ""), ("...", "")],
)
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_normalize_non_string():
    assert normalize(None) == ""


# ---- dados embutidos ----
def test_builtin_data_loaded_and_consistent():
    cat = Catalog()
    services = cat.all()
    assert len(services) == 67
    names = [normalize(s.name) for s in services]
    assert names == sorted(names)
    icons = {i["slug"] for i in Catalog.icons()}
    for s in services:
        assert s.builtin and not s.customized and s.login_url == s.default_url
        assert s.login_url.startswith("https://")
        assert s.icon == "" or s.icon in icons
        assert (s.color == "") == (s.icon == "")


def test_cache_is_shared():
    Catalog()
    first = catalog_module._builtin_services()
    Catalog()
    assert catalog_module._builtin_services() is first


def test_icons_list():
    icons = Catalog.icons()
    assert icons and set(icons[0]) == {"slug", "title"}
    titles = [i["title"].casefold() for i in icons]
    assert titles == sorted(titles)


# ---- match ----
@pytest.mark.parametrize(
    "text,key",
    [("Epic", "epicgames"), ("epic games", "epicgames"), ("EPICGAMES", "epicgames"), ("gov", "govbr"),
     ("gov.br", "govbr"), ("Itau", "itau"), ("Itaú", "itau"), ("twitter", "x"), ("X", "x")],
)
def test_match(text, key):
    found = Catalog().match(text)
    assert found is not None and found.key == key


@pytest.mark.parametrize("text", ["", "   ", "!!!", "servico-inexistente-xyz", "epi"])
def test_match_none(text):
    assert Catalog().match(text) is None


# ---- suggest ----
def test_suggest_prefix_before_contains_and_no_repeats():
    cat = Catalog()
    result = cat.suggest("epic", limit=50)
    assert result[0].key == "epicgames"
    keys = [s.key for s in result]
    assert len(keys) == len(set(keys))
    # "contém" vem depois de todos os prefixos
    seen_contains = False
    for s in result:
        names = [normalize(s.name), *map(normalize, s.aliases)]
        is_prefix = any(n.startswith("epic") for n in names)
        if not is_prefix:
            seen_contains = True
        assert not (seen_contains and is_prefix)


def test_suggest_contains_and_one_char_and_limit():
    cat = Catalog()
    assert "googledrive" in [s.key for s in cat.suggest("drive")]
    assert cat.suggest("g")  # 1 caractere já sugere
    assert len(cat.suggest("g", limit=3)) == 3
    assert len(cat.suggest("a")) <= 6
    assert cat.suggest("") == [] and cat.suggest("   ") == [] and cat.suggest("zzzzqqq") == []
    assert cat.suggest("g", limit=0) == []


def test_suggest_order_is_stable():
    cat = Catalog()
    assert [s.key for s in cat.suggest("a", 20)] == [s.key for s in Catalog().suggest("a", 20)]


def test_suggest_prefix_precedes_contains_example():
    cat = Catalog([custom("Xepic", key="custom-a"), custom("Epico", key="custom-b")])
    keys = [s.key for s in cat.suggest("epic", 10)]
    assert keys.index("custom-b") < keys.index("custom-a")
    assert keys.index("epicgames") < keys.index("custom-a")


# ---- overrides e personalizados ----
def test_overrides_apply_only_to_builtin():
    cat = Catalog(url_overrides={"steam": "https://meu.exemplo/steam", "inexistente": "https://x.com"})
    steam = cat.get("steam")
    assert steam.customized and steam.login_url == "https://meu.exemplo/steam"
    assert steam.default_url != steam.login_url
    assert cat.get("inexistente") is None
    assert not cat.get("github").customized
    assert len(cat.all()) == 67


def test_custom_services_in_all_and_match_priority():
    cat = Catalog([custom("Minha Steam", ["steam"], key="custom-1", icon="steam")])
    assert cat.get("custom-1").builtin is False and cat.get("custom-1").color != ""
    assert cat.match("steam").key == "custom-1"  # personalizado vence o embutido
    assert Catalog().match("steam").key == "steam"
    assert len(cat.all()) == 68
    names = [normalize(s.name) for s in cat.all()]
    assert names == sorted(names)


def test_custom_without_icon_has_no_color():
    s = Catalog([custom()]).get("custom-1")
    assert s.icon == "" and s.color == "" and s.default_url == s.login_url and not s.customized


# ---- cofre ----
def test_vault_new_has_empty_services(vault):
    assert vault.services == {"custom": [], "overrides": {}}


def test_services_persist(vault, path):
    vault.update_services([custom(aliases=["faculdade"])], {"steam": "https://x.exemplo/"})
    again = Vault.open(path, PW)
    assert again.services["custom"][0]["aliases"] == ["faculdade"]
    assert again.services["overrides"] == {"steam": "https://x.exemplo/"}


def test_update_services_copies_input(vault):
    items = [custom()]
    vault.update_services(items, {})
    items[0]["name"] = "mudou"
    assert vault.services["custom"][0]["name"] == "Portal"


def test_old_vault_without_services_opens(vault, path):
    vault.add(Entry("A", password="a"))
    vault.update_services([custom()], {})

    def strip(data):
        data.pop("services")
        return data

    _rewrite_plain(path, strip)
    v = Vault.open(path, PW)
    assert v.services == {"custom": [], "overrides": {}}
    assert v.entries[0].icon == ""


def test_services_partial_keys_default_empty(vault, path):
    def partial(data):
        data["services"] = {"overrides": {"steam": "https://x.exemplo/"}}
        return data

    _rewrite_plain(path, partial)
    assert Vault.open(path, PW).services == {"custom": [], "overrides": {"steam": "https://x.exemplo/"}}


@pytest.mark.parametrize(
    "bad",
    [
        "texto", [], {"custom": "x"}, {"custom": ["x"]}, {"custom": [{"key": "k"}]},
        {"custom": [{"key": "k", "name": "n", "login_url": 1, "aliases": []}]},
        {"custom": [{"key": "k", "name": "n", "login_url": "u", "aliases": "a"}]},
        {"custom": [{"key": "k", "name": "n", "login_url": "u", "aliases": [1]}]},
        {"custom": [{"key": "k", "name": "n", "login_url": "u", "aliases": [], "icon": 3}]},
        {"overrides": []}, {"overrides": {"a": 1}},
    ],
)
def test_invalid_services_is_corrupted(vault, path, bad):
    def breakit(data):
        data["services"] = bad
        return data

    _rewrite_plain(path, breakit)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def test_update_services_rollback(vault, monkeypatch):
    vault.update_services([custom()], {"steam": "https://a.exemplo/"})
    before = json.loads(json.dumps(vault.services))

    def boom():
        raise OSError("disco cheio")

    monkeypatch.setattr(vault, "save", boom)
    with pytest.raises(OSError):
        vault.update_services([], {})
    assert vault.services == before


def test_update_services_invalid_raises_and_keeps(vault):
    with pytest.raises(ValueError):
        vault.update_services([{"key": "k"}], {})
    assert vault.services == {"custom": [], "overrides": {}}


def test_entry_icon_roundtrip():
    e = Entry("A", icon="steam")
    assert Entry.from_dict(e.to_dict()).icon == "steam"
    assert Entry.from_dict({"service": "A", "id": "1", "icon": 5}).icon == ""
    assert Entry.from_dict({"service": "A", "id": "1"}).icon == ""
