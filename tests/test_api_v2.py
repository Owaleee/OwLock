import json

import pytest

from owlock import __version__
from owlock.app.api import Api
from owlock.core import Entry, MemoryStore, Vault
from owlock.core.vault import _create_v1

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"


class Clip:
    text = ""

    def copy(self, t):
        self.text = t

    def paste(self):
        return self.text


class Dialog:
    def __init__(self, result=None, raises=False):
        self.result = result
        self.raises = raises
        self.names = []

    def __call__(self, name):
        self.names.append(name)
        if self.raises:
            raise RuntimeError("sem janela")
        return self.result


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


@pytest.fixture
def store():
    return MemoryStore()


def make_api(path, store, dialog=None):
    return Api(path, clipboard=Clip(), store=store, save_dialog=dialog, kdf_params=FAST)


def err(r, code):
    assert r["ok"] is False and r["error"] == code, r
    assert r["message"]


@pytest.fixture
def created(path, store):
    api = make_api(path, store)
    r = api.create_vault(PW, PW)
    assert r["ok"]
    return api, r["secret_key"]


# ---- status ----
def test_status_no_vault(path, store):
    s = make_api(path, store).status()
    assert s["exists"] is False and s["format_version"] is None
    assert s["secret_key_required"] is False
    assert s["app_version"] == __version__ == "0.5.0"
    assert s["key_storage"] == store.description


def test_status_v2_and_key_required_on_new_device(path, store, created):
    api, key = created
    s = api.status()
    assert s["format_version"] == 2 and s["secret_key_required"] is False
    other = make_api(path, MemoryStore())
    s2 = other.status()
    assert s2["format_version"] == 2 and s2["secret_key_required"] is True


def test_status_v1_and_corrupted(path, store, tmp_path):
    _create_v1(path, PW, FAST)
    s = make_api(path, store).status()
    assert s["format_version"] == 1 and s["secret_key_required"] is False
    path.write_text("lixo")
    assert make_api(path, store).status()["format_version"] is None


# ---- criação ----
def test_create_vault_returns_key_once(path, store, created):
    api, key = created
    assert key.startswith("OW2-")
    for call in (api.status(), api.touch(), api.list_entries(), api.lock()):
        assert key not in json.dumps(call)
    assert key not in json.dumps(api.unlock(PW))


def test_create_vault_save_failure(path):
    class Broken(MemoryStore):
        def set(self, vault_id, secret_bytes):
            raise RuntimeError("travado")

    err(make_api(path, Broken()).create_vault(PW, PW), "save_failed")
    assert not path.exists()


# ---- unlock ----
def test_unlock_codes(path, store, created):
    api, key = created
    api.lock()
    err(api.unlock("senha-errada-xx"), "wrong_password")
    r = api.unlock(PW)
    assert r == {"ok": True, "migrated": False}


def test_new_device_flow(path, store, created):
    _, key = created
    other_store = MemoryStore()
    api = make_api(path, other_store)
    assert api.status()["secret_key_required"] is True
    err(api.unlock(PW), "secret_key_required")
    err(api.unlock(PW, "isto não é"), "invalid_secret_key")
    wrong = "OW2-AAAQE-AYEAU-DAOCA-JBIFQ-YDIOB5-5O"
    err(api.unlock(PW, wrong), "wrong_secret_key")
    err(api.unlock("senha-errada-xx", key), "wrong_password")
    assert api.status()["secret_key_required"] is True
    r = api.unlock(PW, key.lower())
    assert r["ok"] is True and r["migrated"] is False and "secret_key" not in r
    assert api.status()["secret_key_required"] is False
    api.lock()
    assert api.unlock(PW)["ok"] is True  # próximo unlock sem chave


def test_blank_secret_key_is_treated_as_absent(path, store, created):
    api, _ = created
    api.lock()
    assert api.unlock(PW, "   ")["ok"] is True
    api.lock()
    assert api.unlock(PW, None)["ok"] is True


def test_unlock_not_found_and_corrupted(path, store):
    err(make_api(path, store).unlock(PW), "not_found")
    path.write_text("lixo")
    r = make_api(path, store).unlock(PW)
    err(r, "corrupted")
    assert ".bak" in r["message"]


def test_unlock_key_save_failure_flag(path, created):
    _, key = created

    class Broken(MemoryStore):
        def set(self, vault_id, secret_bytes):
            raise RuntimeError("travado")

    r = make_api(path, Broken()).unlock(PW, key)
    assert r["ok"] is True and r["key_save_failed"] is True


# ---- migração ----
def v1_file(path):
    _create_v1(path, PW, FAST, entries=[Entry("Conta Antiga", "u", "p")])
    return path.read_bytes()


def test_unlock_migrates_and_returns_key_once(path, store):
    original = v1_file(path)
    api = make_api(path, store)
    r = api.unlock(PW)
    assert r["ok"] and r["migrated"] is True
    assert r["secret_key"].startswith("OW2-")
    backup = path.with_name(path.name + ".v1-backup")
    assert r["v1_backup_path"] == str(backup) and backup.read_bytes() == original
    assert [e["service"] for e in api.list_entries()["entries"]] == ["Conta Antiga"]
    api.lock()
    again = api.unlock(PW)
    assert again == {"ok": True, "migrated": False}
    assert api.status()["format_version"] == 2


def test_migration_failure_code(path):
    original = v1_file(path)

    class Broken(MemoryStore):
        def set(self, vault_id, secret_bytes):
            raise RuntimeError("travado")

    err(make_api(path, Broken()).unlock(PW), "migration_failed")
    assert path.read_bytes() == original


def test_delete_v1_backup(path, store):
    v1_file(path)
    api = make_api(path, store)
    err(api.delete_v1_backup(), "locked")
    api.unlock(PW)
    backup = path.with_name(path.name + ".v1-backup")
    assert backup.exists()
    assert api.delete_v1_backup() == {"ok": True}
    assert not backup.exists()
    err(api.delete_v1_backup(), "not_found")


def test_delete_v1_backup_without_migration_deletes_nothing(path, store, created):
    api, _ = created
    stray = path.with_name(path.name + ".v1-backup")
    stray.write_bytes(b"x")
    err(api.delete_v1_backup(), "not_found")
    assert stray.exists()  # só apaga o caminho registrado na migração desta sessão


# ---- Kit de emergência ----
def test_emergency_kit(path, store, created):
    api, key = created
    r = api.emergency_kit(PW)
    assert r == {
        "ok": True, "secret_key": key, "vault_id": Vault.peek(path)["vault_id"],
        "vault_path": str(path), "key_storage": store.description,
    }
    err(api.emergency_kit("senha-errada-xx"), "wrong_password")
    api.lock()
    err(api.emergency_kit(PW), "locked")


def test_save_emergency_kit(path, store, created, tmp_path):
    api, key = created
    target = tmp_path / "kit.html"
    dialog = Dialog(str(target))
    api = make_api(path, store, dialog)
    api.unlock(PW)
    r = api.save_emergency_kit(PW)
    assert r == {"ok": True, "path": str(target)}
    assert dialog.names == ["OwLock-Kit-de-emergencia.html"]
    html_text = target.read_text(encoding="utf-8")
    assert key in html_text
    assert "Kit de emergência do OwLock" in html_text and "Senha mestra:" in html_text
    assert str(path) in html_text
    assert "http://" not in html_text and "https://" not in html_text
    for tag in ("<link", "<script", "<img", "@import", "url("):
        assert tag not in html_text
    assert PW not in html_text
    assert "@page" in html_text and "A4" in html_text
    # a resposta nunca devolve a chave
    assert key not in json.dumps(r)


def test_save_emergency_kit_escapes_values():
    """Todos os valores do Kit passam por html.escape (testado direto: o Windows proíbe < > " em nomes de arquivo)."""
    from owlock.app.api import _kit_html

    nasty = '<script>alert(1)</script>&"x".vault'
    html_text = _kit_html("OW2-<b>", "<id>", nasty, "<data>")
    assert "<script" not in html_text and "<b>" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;&amp;&quot;x&quot;.vault" in html_text
    assert "OW2-&lt;b&gt;" in html_text and "&lt;data&gt;" in html_text


def test_save_emergency_kit_adds_html_extension(path, store, created, tmp_path):
    dialog = Dialog(str(tmp_path / "meu-kit"))
    api = make_api(path, store, dialog)
    api.unlock(PW)
    assert api.save_emergency_kit(PW)["path"].endswith("meu-kit.html")
    assert (tmp_path / "meu-kit.html").exists()


def test_save_emergency_kit_errors(path, store, created, tmp_path):
    dialog = Dialog(None)
    api = make_api(path, store, dialog)
    api.unlock(PW)
    err(api.save_emergency_kit("senha-errada-xx"), "wrong_password")
    assert dialog.names == []  # senha errada: nem abre a janela
    err(api.save_emergency_kit(PW), "cancelled")
    dialog.result = ""
    err(api.save_emergency_kit(PW), "cancelled")
    dialog.result = str(tmp_path / "pasta" / "inexistente" / "kit.html")
    err(api.save_emergency_kit(PW), "save_failed")
    dialog.raises = True
    err(api.save_emergency_kit(PW), "save_failed")
    err(make_api(path, store).save_emergency_kit(PW), "locked")
    nodialog = make_api(path, store)
    nodialog.unlock(PW)
    err(nodialog.save_emergency_kit(PW), "save_failed")


def test_public_surface_has_new_methods(path, store):
    api = make_api(path, store)
    public = {n for n in dir(api) if not n.startswith("_") and callable(getattr(api, n))}
    assert {"emergency_kit", "save_emergency_kit", "delete_v1_backup"} <= public
