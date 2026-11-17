import json

import pytest

from owlock.app.api import Api
from owlock.core import (
    AUTO_LOCK_OPTIONS, CLIPBOARD_OPTIONS, Entry, Settings, Vault, VaultCorruptedError,
)
from tests.test_categories import _rewrite_plain
from tests.test_api import FakeClipboard, FakeClock, FakeTimer, err

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"


@pytest.fixture(autouse=True)
def _reset_timers():
    FakeTimer.created = []


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


@pytest.fixture
def vault(path):
    return Vault.create(path, PW, kdf_params=FAST)


def change(vault, entry, password):
    import dataclasses

    return vault.update(dataclasses.replace(entry, password=password))


# ---------------- núcleo: histórico ----------------
def test_new_entry_fields_default():
    e = Entry("X")
    assert e.url == "" and e.password_history == []
    assert Entry.from_dict(e.to_dict()) == e


def test_password_change_creates_version(vault):
    e = vault.add(Entry("A", password="antiga"))
    e = change(vault, e, "nova")
    assert [h["password"] for h in e.password_history] == ["antiga"]
    assert e.password_history[0]["changed_at"].endswith("+00:00")
    e = change(vault, e, "novissima")
    assert [h["password"] for h in e.password_history] == ["nova", "antiga"]


def test_same_password_no_version(vault):
    import dataclasses

    e = vault.add(Entry("A", password="x"))
    vault.update(dataclasses.replace(e, username="outro"))
    assert vault.entries[0].password_history == []


def test_history_limit_20(vault):
    e = vault.add(Entry("A", password="p0"))
    for n in range(1, 26):
        e = change(vault, e, f"p{n}")
    hist = e.password_history
    assert len(hist) == 20
    assert hist[0]["password"] == "p24" and hist[-1]["password"] == "p5"


def test_history_persists_after_reopen(vault, path):
    e = vault.add(Entry("A", password="a", url="https://a.com"))
    change(vault, e, "b")
    reopened = Vault.open(path, PW).entries[0]
    assert reopened.url == "https://a.com"
    assert [h["password"] for h in reopened.password_history] == ["a"]


def test_old_vault_without_new_fields_opens(vault, path):
    vault.add(Entry("A", password="a"))

    def strip(data):
        for e in data["entries"]:
            e.pop("url", None)
            e.pop("password_history", None)
        data.pop("settings", None)
        return data

    _rewrite_plain(path, strip)
    e = Vault.open(path, PW).entries[0]
    assert e.url == "" and e.password_history == []


@pytest.mark.parametrize(
    "bad",
    ["texto", {"password": "x"}, [1], [{"password": "x"}], [{"password": 1, "changed_at": "d"}],
     [{"password": "x", "changed_at": 5}]],
)
def test_invalid_history_is_corrupted(vault, path, bad):
    vault.add(Entry("A", password="a"))

    def breakit(data):
        data["entries"][0]["password_history"] = bad
        return data

    _rewrite_plain(path, breakit)
    with pytest.raises(VaultCorruptedError):
        Vault.open(path, PW)


def test_update_rollback_restores_history(vault, monkeypatch):
    e = vault.add(Entry("A", password="a"))
    e = change(vault, e, "b")
    before = json.loads(json.dumps(vault.entries[0].to_dict()))

    def boom():
        raise OSError("disco cheio")

    monkeypatch.setattr(vault, "save", boom)
    with pytest.raises(OSError):
        change(vault, vault.entries[0], "c")
    assert vault.entries[0].to_dict() == before
    assert [h["password"] for h in vault.entries[0].password_history] == ["a"]


# ---------------- núcleo: settings ----------------
def test_settings_defaults(vault, path):
    assert vault.settings == Settings(5, 30)
    assert Vault.open(path, PW).settings == Settings(5, 30)
    assert AUTO_LOCK_OPTIONS == (1, 2, 5, 10, 15, 30)
    assert CLIPBOARD_OPTIONS == (10, 20, 30, 45, 60, 90)


def test_settings_persist(vault, path):
    vault.update_settings(Settings(15, 90))
    assert Vault.open(path, PW).settings == Settings(15, 90)


@pytest.mark.parametrize(
    "raw", [{"auto_lock_minutes": 7, "clipboard_clear_seconds": 25},
            {"auto_lock_minutes": "5", "clipboard_clear_seconds": True},
            {"auto_lock_minutes": None}, "lixo", [], {}],
)
def test_invalid_settings_in_file_fall_back(vault, path, raw):
    def put(data):
        data["settings"] = raw
        return data

    _rewrite_plain(path, put)
    assert Vault.open(path, PW).settings == Settings(5, 30)


def test_partially_valid_settings_keep_valid_part(vault, path):
    def put(data):
        data["settings"] = {"auto_lock_minutes": 10, "clipboard_clear_seconds": 7}
        return data

    _rewrite_plain(path, put)
    assert Vault.open(path, PW).settings == Settings(10, 30)


def test_update_settings_rejects_invalid(vault):
    with pytest.raises(ValueError):
        vault.update_settings(Settings(3, 30))
    assert vault.settings == Settings(5, 30)


def test_update_settings_rollback(vault, monkeypatch):
    def boom():
        raise OSError("x")

    monkeypatch.setattr(vault, "save", boom)
    with pytest.raises(OSError):
        vault.update_settings(Settings(1, 10))
    assert vault.settings == Settings(5, 30)


# ---------------- Api ----------------
class Opener:
    def __init__(self, result=True):
        self.calls = []
        self.result = result

    def __call__(self, url):
        self.calls.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def clip():
    return FakeClipboard()


@pytest.fixture
def opener():
    return Opener()


@pytest.fixture
def api(path, vault, clock, clip, opener):
    vault.add(Entry("Site", "u", "atual"))
    return Api(path, clipboard=clip, clock=clock, timer_factory=FakeTimer, url_opener=opener)


@pytest.fixture
def opened(api):
    assert api.unlock(PW)["ok"]
    return api


def sid(api):
    return api.list_entries()["entries"][0]["id"]


def save(api, **data):
    base = {"service": "Novo", "username": "u", "password": "p"}
    base.update(data)
    return api.save_entry(base)


# ---- settings ----
def test_get_settings_shape_and_labels(opened):
    r = opened.get_settings()
    assert r["settings"] == {"auto_lock_minutes": 5, "clipboard_clear_seconds": 30}
    lock = r["options"]["auto_lock_minutes"]
    assert [o["value"] for o in lock] == [1, 2, 5, 10, 15, 30]
    assert [o["label"] for o in lock][:3] == ["1 minuto", "2 minutos", "5 minutos"]
    assert [o["value"] for o in lock if o["recommended"]] == [5]
    clip = r["options"]["clipboard_clear_seconds"]
    assert [o["label"] for o in clip] == [
        "10 segundos", "20 segundos", "30 segundos", "45 segundos",
        "1 minuto", "1 minuto e 30 segundos",
    ]
    assert [o["value"] for o in clip if o["recommended"]] == [30]


def test_settings_require_unlocked(api):
    err(api.get_settings(), "locked")
    err(api.save_settings({"auto_lock_minutes": 1}), "locked")


def test_status_reports_current_values(opened):
    s = opened.status()
    assert s["auto_lock_seconds"] == 300 and s["clipboard_clear_seconds"] == 30


def test_auto_lock_uses_setting(opened, clock):
    r = opened.save_settings({"auto_lock_minutes": 1, "clipboard_clear_seconds": 30})
    assert r["ok"] and r["settings"]["auto_lock_minutes"] == 1
    assert opened.status()["auto_lock_seconds"] == 60
    clock.advance(61)
    err(opened.list_entries(), "locked")


def test_auto_lock_setting_applies_on_next_unlock(opened, clock):
    opened.save_settings({"auto_lock_minutes": 1, "clipboard_clear_seconds": 30})
    opened.lock()
    assert opened.unlock(PW)["ok"]
    assert opened.status()["auto_lock_seconds"] == 60
    clock.advance(59)
    assert opened.list_entries()["ok"]
    clock.advance(61)
    err(opened.list_entries(), "locked")


def test_save_settings_restarts_inactivity(opened, clock):
    clock.advance(200)
    opened.save_settings({"auto_lock_minutes": 5, "clipboard_clear_seconds": 30})
    clock.advance(200)
    assert opened.list_entries()["ok"]


def test_clear_after_uses_setting(opened, clip):
    opened.save_settings({"auto_lock_minutes": 5, "clipboard_clear_seconds": 90})
    r = opened.copy_field(sid(opened), "password")
    assert r == {"ok": True, "clear_in": 90}
    assert FakeTimer.created[-1].interval == 90
    assert opened.status()["clipboard_clear_seconds"] == 90


def test_settings_persist_across_api_unlock(path, vault, clock, clip):
    a = Api(path, clipboard=clip, clock=clock, timer_factory=FakeTimer)
    a.unlock(PW)
    a.save_settings({"auto_lock_minutes": 10, "clipboard_clear_seconds": 60})
    b = Api(path, clipboard=clip, clock=clock, timer_factory=FakeTimer)
    b.unlock(PW)
    assert b.get_settings()["settings"] == {"auto_lock_minutes": 10, "clipboard_clear_seconds": 60}
    assert b.status()["auto_lock_seconds"] == 600


def test_create_vault_applies_defaults(tmp_path, clock, clip):
    a = Api(tmp_path / "novo.vault", auto_lock_seconds=99, clipboard=clip, clock=clock)
    assert a.create_vault("senha-longa-1", "senha-longa-1")["ok"]
    assert a.status()["auto_lock_seconds"] == 300


@pytest.mark.parametrize(
    "data,code",
    [
        ({"auto_lock_minutes": 7, "clipboard_clear_seconds": 30}, "invalid_auto_lock"),
        ({"auto_lock_minutes": "5", "clipboard_clear_seconds": 30}, "invalid_auto_lock"),
        ({"auto_lock_minutes": True, "clipboard_clear_seconds": 30}, "invalid_auto_lock"),
        ({"auto_lock_minutes": 5.0, "clipboard_clear_seconds": 30}, "invalid_auto_lock"),
        ({"auto_lock_minutes": 5, "clipboard_clear_seconds": 15}, "invalid_clipboard"),
        ({"auto_lock_minutes": 5, "clipboard_clear_seconds": None}, "invalid_clipboard"),
    ],
)
def test_save_settings_invalid(opened, data, code):
    err(opened.save_settings(data), code)
    assert opened.get_settings()["settings"] == {"auto_lock_minutes": 5, "clipboard_clear_seconds": 30}


def test_save_settings_save_failed(opened, monkeypatch):
    monkeypatch.setattr(opened._vault, "save", lambda: (_ for _ in ()).throw(OSError("x")))
    err(opened.save_settings({"auto_lock_minutes": 1, "clipboard_clear_seconds": 10}), "save_failed")
    assert opened.status()["auto_lock_seconds"] == 300
    assert opened.get_settings()["settings"]["auto_lock_minutes"] == 5


# ---- url ----
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),
        ("   ", ""),
        ("  example.com  ", "https://example.com"),
        ("example.com/login?a=1", "https://example.com/login?a=1"),
        ("http://example.com", "http://example.com"),
        ("HTTPS://Example.com/x", "HTTPS://Example.com/x"),
        ("localhost:8080/app", "https://localhost:8080/app"),
    ],
)
def test_url_normalized(opened, raw, expected):
    r = save(opened, url=raw)
    assert r["ok"] and r["entry"]["url"] == expected


@pytest.mark.parametrize(
    "raw",
    ["javascript:alert(1)", "ftp://example.com", "file:///etc/passwd", "mailto:a@b.com",
     "https://", "http:///x", "//example.com", "exa mple.com", "https://a.com:99999",
     "https://" + "a" * 2050, 123],
)
def test_url_rejected(opened, raw):
    err(save(opened, url=raw), "invalid_url")
    assert len(opened.list_entries()["entries"]) == 1


def test_url_max_length_boundary(opened):
    ok = "https://a.com/" + "x" * (2048 - len("https://a.com/"))
    assert len(ok) == 2048
    assert save(opened, url=ok)["ok"]
    err(save(opened, url=ok + "x"), "invalid_url")


def test_url_kept_when_editing(opened):
    e = save(opened, url="example.com")["entry"]
    r = opened.save_entry({"id": e["id"], "service": "Novo", "url": "https://outro.com"})
    assert r["entry"]["url"] == "https://outro.com"


def test_summary_has_url_and_history_count(opened):
    e = opened.list_entries()["entries"][0]
    assert e["url"] == "" and e["history_count"] == 0


# ---- open_url ----
def test_open_url_ok(opened, opener):
    e = save(opened, url="example.com")["entry"]
    assert opened.open_url(e["id"]) == {"ok": True}
    assert opener.calls == ["https://example.com"]


def test_open_url_errors(opened, opener):
    err(opened.open_url("nope"), "not_found")
    err(opened.open_url(sid(opened)), "no_url")
    assert opener.calls == []


def test_open_url_revalidates_saved_scheme(opened, opener):
    e = save(opened, url="https://example.com")["entry"]
    opened._vault.entries[-1].url = "javascript:alert(1)"
    err(opened.open_url(e["id"]), "invalid_url")
    assert opener.calls == []


@pytest.mark.parametrize("result", [False, RuntimeError("x")])
def test_open_url_failure(path, vault, clock, clip, result):
    op = Opener(result)
    a = Api(path, clipboard=clip, clock=clock, timer_factory=FakeTimer, url_opener=op)
    a.unlock(PW)
    e = save(a, url="example.com")["entry"]
    err(a.open_url(e["id"]), "open_failed")


def test_open_url_called_outside_lock(path, vault, clock, clip):
    seen = {}

    def op(url):
        seen["owned"] = a._lock._is_owned()
        return True

    a = Api(path, clipboard=clip, clock=clock, timer_factory=FakeTimer, url_opener=op)
    a.unlock(PW)
    e = save(a, url="example.com")["entry"]
    assert a.open_url(e["id"])["ok"]
    assert seen["owned"] is False


def test_open_url_locked(api):
    err(api.open_url("x"), "locked")


# ---- histórico na Api ----
def make_history(api):
    eid = sid(api)
    api.save_entry({"id": eid, "service": "Site", "password": "segunda-Senha#1"})
    api.save_entry({"id": eid, "service": "Site", "password": "terceira"})
    return eid


def test_history_listing_never_exposes_passwords(opened):
    eid = make_history(opened)
    r = opened.get_password_history(eid)
    assert r["ok"] and r["created_at"]
    assert [h["index"] for h in r["history"]] == [0, 1]
    assert [h["length"] for h in r["history"]] == [len("segunda-Senha#1"), len("atual")]
    assert set(r["history"][0]) == {"index", "changed_at", "length", "strength"}
    assert set(r["history"][0]["strength"]) == {"score", "label"}
    blob = json.dumps([r, opened.get_entry(eid), opened.list_entries(), opened.save_entry(
        {"id": eid, "service": "Site"})])
    for secret in ("atual", "segunda-Senha#1"):
        assert f'"{secret}"' not in blob
    assert opened.get_entry(eid)["entry"]["history_count"] == 2


def test_history_empty_and_errors(opened, api):
    r = opened.get_password_history(sid(opened))
    assert r["ok"] and r["history"] == []
    err(opened.get_password_history("nope"), "not_found")


def test_history_requires_unlocked(api):
    err(api.get_password_history("x"), "locked")
    err(api.reveal_history_password("x", 0), "locked")
    err(api.copy_history_password("x", 0), "locked")


def test_reveal_history_by_index(opened):
    eid = make_history(opened)
    assert opened.reveal_history_password(eid, 0) == {"ok": True, "password": "segunda-Senha#1"}
    assert opened.reveal_history_password(eid, 1) == {"ok": True, "password": "atual"}
    assert opened.reveal_password(eid)["password"] == "terceira"


@pytest.mark.parametrize("index", [-1, 2, 99, "0", None, 1.0, True])
def test_history_invalid_index(opened, index):
    eid = make_history(opened)
    err(opened.reveal_history_password(eid, index), "invalid_index")
    err(opened.copy_history_password(eid, index), "invalid_index")


def test_history_not_found(opened):
    err(opened.reveal_history_password("nope", 0), "not_found")
    err(opened.copy_history_password("nope", 0), "not_found")


def test_copy_history_clears_like_copy_field(opened, clip):
    eid = make_history(opened)
    r = opened.copy_history_password(eid, 1)
    assert r == {"ok": True, "clear_in": 30}
    assert clip.text == "atual"
    FakeTimer.created[-1].fire()
    assert clip.text == ""


def test_save_entry_without_password_keeps_history_unchanged(opened):
    eid = make_history(opened)
    opened.save_entry({"id": eid, "service": "Site", "username": "novo"})
    assert opened.get_entry(eid)["entry"]["history_count"] == 2
