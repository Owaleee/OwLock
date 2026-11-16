import json

import pytest

from owlock.app.api import Api
from owlock.core import Entry, Vault

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeClipboard:
    def __init__(self):
        self.text = ""

    def copy(self, text):
        self.text = text

    def paste(self):
        return self.text


class FakeTimer:
    created = []

    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.daemon = False
        self.started = False
        self.cancelled = False
        FakeTimer.created.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.function()


@pytest.fixture(autouse=True)
def _reset_timers():
    FakeTimer.created = []


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


@pytest.fixture
def seeded(path):
    v = Vault.create(path, PW, kdf_params=FAST)
    v.add(Entry("zeta", "u1@x.com", "123456", True, "Authy", "nota um"))
    v.add(Entry("Alfa", "u2@x.com", "T7#qLm9!vRz2@kWp", False))
    v.add(Entry("beta", "u3@x.com", "senha123", False, "", "banco"))
    v.add(Entry("Épico", "u4@x.com", "Gx4!nP8s#Qd1", True, "Google"))
    return v


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def clip():
    return FakeClipboard()


@pytest.fixture
def api(path, seeded, clock, clip):
    return Api(path, clipboard=clip, clock=clock, timer_factory=FakeTimer)


@pytest.fixture
def opened(api):
    assert api.unlock(PW)["ok"]
    return api


def ids(api):
    return {e["service"]: e["id"] for e in api.list_entries()["entries"]}


def err(result, code):
    assert result["ok"] is False
    assert result["error"] == code
    assert isinstance(result["message"], str) and result["message"]


# ---- estado e abertura ----
def test_status_before_and_after(api, path):
    s = api.status()
    assert s["ok"] and s["exists"] and not s["unlocked"]
    assert s["vault_path"] == str(path)
    assert s["auto_lock_seconds"] == 300 and s["seconds_left"] == 0
    api.unlock(PW)
    s = api.status()
    assert s["unlocked"] and s["seconds_left"] == 300


def test_status_missing_vault(tmp_path):
    a = Api(tmp_path / "nao.vault", clipboard=FakeClipboard())
    assert a.status()["exists"] is False
    err(a.unlock(PW), "not_found")


def test_unlock_wrong_password(api):
    err(api.unlock("errada-errada"), "wrong_password")
    assert not api.status()["unlocked"]


def test_unlock_corrupted_mentions_bak(api, path):
    path.write_text("lixo lixo")
    r = api.unlock(PW)
    err(r, "corrupted")
    assert str(path) + ".bak" in r["message"]


def test_create_vault_codes(tmp_path):
    p = tmp_path / "novo" / "c.vault"
    a = Api(p, clipboard=FakeClipboard())
    err(a.create_vault("curta", "curta"), "password_too_short")
    err(a.create_vault("senha-longa-1", "outra-coisa-1"), "mismatch")
    assert not p.exists()
    assert a.create_vault("senha-longa-1", "senha-longa-1") == {"ok": True}
    assert p.exists() and a.status()["unlocked"]
    err(a.create_vault("senha-longa-1", "senha-longa-1"), "exists")


def test_create_vault_exists(api):
    err(api.create_vault("senha-longa-1", "senha-longa-1"), "exists")


# ---- listagem ----
def test_list_never_contains_password(opened):
    secrets = {"123456", "T7#qLm9!vRz2@kWp", "senha123", "Gx4!nP8s#Qd1"}
    r = opened.list_entries()
    assert len(r["entries"]) == 4
    blob = json.dumps(r)
    for e in r["entries"]:
        assert "password" not in e
        assert e["password_length"] > 0
        assert set(e["strength"]) == {"score", "label"}
    for s in secrets:
        assert s not in blob
    one = opened.get_entry(r["entries"][0]["id"])
    assert "password" not in one["entry"]
    assert not any(s in json.dumps(one) for s in secrets)


def test_list_sorted_casefold(opened):
    names = [e["service"] for e in opened.list_entries()["entries"]]
    assert names == ["Alfa", "beta", "zeta", "Épico"]


def test_filters_and_stats(opened):
    r2 = opened.list_entries(filter="2fa")
    assert [e["service"] for e in r2["entries"]] == ["zeta", "Épico"]
    ra = opened.list_entries(filter="attention")
    assert [e["service"] for e in ra["entries"]] == ["beta", "zeta"]
    assert ra["stats"] == {"total": 4, "with_2fa": 2, "attention": 2}
    err(opened.list_entries(filter="xyz"), "invalid_filter")


def test_search(opened):
    assert [e["service"] for e in opened.list_entries(query="epico")["entries"]] == ["Épico"]
    assert [e["service"] for e in opened.list_entries(query="banco")["entries"]] == ["beta"]
    assert opened.list_entries(query="T7#qLm9")["entries"] == []
    r = opened.list_entries(query="x.com", filter="2fa")
    assert len(r["entries"]) == 2
    assert r["stats"]["total"] == 4


def test_get_entry_not_found(opened):
    err(opened.get_entry("nao-existe"), "not_found")


def test_reveal(opened):
    i = ids(opened)
    assert opened.reveal_password(i["Alfa"]) == {"ok": True, "password": "T7#qLm9!vRz2@kWp"}
    err(opened.reveal_password("x"), "not_found")


# ---- área de transferência ----
def test_copy_and_conditional_clear(opened, clip):
    i = ids(opened)["Alfa"]
    r = opened.copy_field(i, "password")
    assert r == {"ok": True, "clear_in": 30}
    assert clip.text == "T7#qLm9!vRz2@kWp"
    t = FakeTimer.created[-1]
    assert t.interval == 30 and t.daemon and t.started
    t.fire()
    assert clip.text == ""


def test_copy_username(opened, clip):
    opened.copy_field(ids(opened)["Alfa"], "username")
    assert clip.text == "u2@x.com"


def test_no_clear_if_user_copied_other(opened, clip):
    opened.copy_field(ids(opened)["Alfa"], "password")
    clip.text = "outra coisa"
    FakeTimer.created[-1].fire()
    assert clip.text == "outra coisa"


def test_new_copy_cancels_previous_timer(opened, clip):
    i = ids(opened)
    opened.copy_field(i["Alfa"], "password")
    first = FakeTimer.created[-1]
    opened.copy_field(i["Alfa"], "username")
    assert first.cancelled
    first.function()  # mesmo disparado à força, o timer antigo não limpa
    assert clip.text == "u2@x.com"
    FakeTimer.created[-1].fire()
    assert clip.text == ""


def test_copy_errors(opened):
    i = ids(opened)["Alfa"]
    err(opened.copy_field(i, "notes"), "invalid_field")
    err(opened.copy_field("x", "password"), "not_found")


def test_lock_cancels_timer_and_clears(opened, clip):
    opened.copy_field(ids(opened)["Alfa"], "password")
    t = FakeTimer.created[-1]
    assert opened.lock() == {"ok": True}
    assert t.cancelled and clip.text == ""
    assert not opened.status()["unlocked"]


def test_shutdown_clears_clipboard(opened, clip):
    opened.copy_field(ids(opened)["Alfa"], "password")
    assert opened.shutdown() == {"ok": True}
    assert clip.text == "" and not opened.status()["unlocked"]


def test_shutdown_keeps_foreign_clipboard(opened, clip):
    opened.copy_field(ids(opened)["Alfa"], "password")
    clip.text = "do usuario"
    opened.shutdown()
    assert clip.text == "do usuario"


def test_shutdown_without_copy(api, clip):
    clip.text = "x"
    assert api.shutdown()["ok"]
    assert clip.text == "x"


# ---- salvar e apagar ----
def test_save_new(opened, path):
    r = opened.save_entry({"service": "  Nova  ", "username": "me", "password": "abc",
                           "has_2fa": False, "twofa_app": "Authy", "notes": "n"})
    assert r["ok"] and r["entry"]["service"] == "Nova"
    assert r["entry"]["twofa_app"] == ""
    assert "password" not in r["entry"]
    assert len(Vault.open(path, PW).entries) == 5


def test_save_edit_keeps_password(opened, path):
    i = ids(opened)["Alfa"]
    created = opened.get_entry(i)["entry"]["created_at"]
    for pw in (None, "absent"):
        data = {"id": i, "service": "Alfa2", "username": "novo", "has_2fa": True,
                "twofa_app": "Authy", "notes": ""}
        if pw is None:
            data["password"] = None
        r = opened.save_entry(data)
        assert r["ok"] and r["entry"]["service"] == "Alfa2"
        assert r["entry"]["has_2fa"] and r["entry"]["twofa_app"] == "Authy"
        assert r["entry"]["created_at"] == created
        assert opened.reveal_password(i)["password"] == "T7#qLm9!vRz2@kWp"
    assert Vault.open(path, PW).entries[1].service == "Alfa2"


def test_save_edit_changes_password_and_clears_2fa_app(opened):
    i = ids(opened)["Épico"]
    r = opened.save_entry({"id": i, "service": "Épico", "password": "novaSenha!1",
                           "has_2fa": False, "twofa_app": "Google"})
    assert r["entry"]["twofa_app"] == ""
    assert opened.reveal_password(i)["password"] == "novaSenha!1"


def test_save_errors(opened):
    err(opened.save_entry({"service": "   "}), "service_required")
    err(opened.save_entry({"service": ""}), "service_required")
    err(opened.save_entry({"id": "nao-existe", "service": "X"}), "not_found")


def test_save_failed_on_oserror(opened, monkeypatch):
    def boom(self):
        raise OSError("disco cheio")

    monkeypatch.setattr(Vault, "save", boom)
    err(opened.save_entry({"service": "X"}), "save_failed")
    err(opened.delete_entry(ids(opened)["Alfa"]), "save_failed")
    assert len(opened.list_entries()["entries"]) == 4


def test_delete(opened, path):
    i = ids(opened)["beta"]
    assert opened.delete_entry(i) == {"ok": True}
    err(opened.delete_entry(i), "not_found")
    assert len(Vault.open(path, PW).entries) == 3


# ---- senhas ----
def test_generate_password(api):
    r = api.generate_password(24)
    assert r["ok"] and len(r["password"]) == 24 and r["strength"]["score"] == 4
    err(api.generate_password(10, False, False, False, False), "invalid_options")
    err(api.generate_password(500), "invalid_options")


def test_check_strength_without_vault(api):
    r = api.check_strength("123456")
    assert r["ok"] and r["score"] == 0 and r["label"] == "Muito fraca"


def test_change_master_password_codes(opened, path):
    err(opened.change_master_password(PW, "nova-senha-9", "diferente-9"), "mismatch")
    err(opened.change_master_password(PW, "curta", "curta"), "password_too_short")
    err(opened.change_master_password(PW, PW, PW), "same_password")
    err(opened.change_master_password("errada-errada", "nova-senha-9", "nova-senha-9"), "wrong_password")
    assert opened.change_master_password(PW, "nova-senha-9", "nova-senha-9") == {"ok": True}
    assert len(Vault.open(path, "nova-senha-9").entries) == 4


# ---- bloqueio automático ----
def test_auto_lock_on_inactivity(opened, clock):
    clock.advance(301)
    err(opened.list_entries(), "locked")
    assert not opened.status()["unlocked"]


def test_activity_keeps_open(opened, clock):
    clock.advance(200)
    r = opened.touch()
    assert r["ok"] and r["seconds_left"] == 300
    clock.advance(200)
    assert opened.list_entries()["ok"]
    clock.advance(299)
    assert opened.touch()["ok"]


def test_status_does_not_count_as_activity(opened, clock):
    clock.advance(100)
    assert opened.status()["seconds_left"] == 200
    assert opened.status()["seconds_left"] == 200
    clock.advance(201)
    assert opened.status()["unlocked"] is False
    assert opened.status()["seconds_left"] == 0


def test_auto_lock_clears_clipboard(opened, clock, clip):
    opened.copy_field(ids(opened)["Alfa"], "password")
    clock.advance(301)
    err(opened.touch(), "locked")
    assert clip.text == ""


def test_unlock_after_auto_lock(opened, clock):
    clock.advance(400)
    err(opened.touch(), "locked")
    assert opened.unlock(PW)["ok"]
    assert opened.touch()["ok"]


# ---- bloqueado ----
def test_locked_methods(api):
    calls = [
        lambda: api.touch(),
        lambda: api.list_entries(),
        lambda: api.get_entry("x"),
        lambda: api.reveal_password("x"),
        lambda: api.copy_field("x", "password"),
        lambda: api.save_entry({"service": "X"}),
        lambda: api.delete_entry("x"),
        lambda: api.change_master_password(PW, "nova-senha-9", "nova-senha-9"),
    ]
    for call in calls:
        err(call(), "locked")
    assert api.lock() == {"ok": True}


def test_public_surface(api):
    public = {n for n in dir(api) if not n.startswith("_") and callable(getattr(api, n))}
    assert public == {
        "status", "create_vault", "unlock", "lock", "touch", "list_entries", "get_entry",
        "reveal_password", "copy_field",
        "copy_text", "save_entry", "delete_entry", "generate_password",
        "check_strength", "change_master_password", "shutdown",
    }


def test_copy_text_clears_like_copy_field(opened, clip):
    """copy_text usa a mesma limpeza condicional de copy_field."""
    r = opened.copy_text("Gerada#123abc")
    assert r == {"ok": True, "clear_in": 30}
    assert clip.text == "Gerada#123abc"
    FakeTimer.created[-1].fire()
    assert clip.text == ""
    assert opened.copy_text("")["error"] == "invalid_text"
    assert opened.copy_text("x" * 2000)["error"] == "invalid_text"


def test_copy_text_requires_unlocked(api):
    assert api.copy_text("abc")["error"] == "locked"
