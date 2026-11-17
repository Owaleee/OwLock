"""Importar CSV (Chrome/Edge/Google, Bitwarden, Firefox, OwLock) e exportar o cofre."""
import pytest

from owlock.app.api import Api
from owlock.core import Entry, MemoryStore, Vault
from owlock.core.transfer import (
    ImportFormatError,
    base_domain,
    export_csv,
    find_duplicates,
    host_of,
    parse_csv,
)

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"

CHROME = (
    "name,url,username,password,note\r\n"
    "github.com,https://github.com/login,ale,Gh#123,\r\n"
    "accounts.google.com,https://accounts.google.com/,ale@gmail.com,\"vírgula, aspas \"\"x\"\"\",nota\r\n"
    "app,android://abc@com.app/,u,p,\r\n"
    ",,,,\r\n"
).encode("utf-8")

BITWARDEN = (
    "folder,favorite,type,name,notes,fields,reprompt,login_uri,login_username,login_password,login_totp\n"
    "Jogos,1,login,Steam,,,0,https://store.steampowered.com,ale,St3am!,otpauth://x\n"
    ",,note,Nota segura,texto,,0,,,,\n"
    "Trabalho,,login,Intranet,obs,,0,https://intra.empresa.com.br,ale.q,Intra1,\n"
).encode("utf-8")

FIREFOX = (
    '"url","username","password","httpRealm","formActionOrigin","guid","timeCreated","timeLastUsed","timePasswordChanged"\n'
    '"https://www.netflix.com","ale@x.com","Nf1",,"https://www.netflix.com","{1}","1","1","1"\n'
).encode("utf-8")


class Clip:
    text = ""

    def copy(self, t):
        self.text = t

    def paste(self):
        return self.text


def lookup(host):
    return {"github.com": "GitHub", "google.com": "Google"}.get(base_domain(host))


# ---- núcleo ----
def test_helpers():
    assert host_of("https://www.Netflix.com/br/") == "netflix.com"
    assert host_of("github.com") == "github.com"
    assert host_of("android://x@com.app/") == ""
    assert base_domain("accounts.google.com") == "google.com"
    assert base_domain("www.itau.com.br") == "itau.com.br"


def test_parse_chrome():
    r = parse_csv(CHROME, lookup)
    assert r.source == "chrome"
    assert [e.service for e in r.entries] == ["GitHub", "Google", "app"]
    assert r.entries[1].password == 'vírgula, aspas "x"'
    assert r.entries[1].notes == "nota"
    assert r.entries[2].url == ""  # android:// não vira link
    assert r.skipped == 0  # linha totalmente vazia é ignorada sem contar


def test_parse_bitwarden():
    r = parse_csv(BITWARDEN)
    assert r.source == "bitwarden"
    assert [e.service for e in r.entries] == ["Steam", "Intranet"]
    steam = r.entries[0]
    assert steam.favorite and steam.has_2fa and steam.twofa_app == "Bitwarden"
    assert r.categories == ["Jogos", "Trabalho"]
    assert r.skipped == 1  # nota segura não é login


def test_parse_firefox_and_cp1252():
    r = parse_csv(FIREFOX)
    assert r.source == "firefox"
    assert r.entries[0].service == "netflix.com" and r.entries[0].username == "ale@x.com"
    data = "name,url,username,password\nAção,https://a.com,joão,senhá\n".encode("cp1252")
    r2 = parse_csv(data)
    assert r2.entries[0].service == "Ação" and r2.entries[0].password == "senhá"


def test_parse_errors():
    with pytest.raises(ImportFormatError):
        parse_csv(b"")
    with pytest.raises(ImportFormatError):
        parse_csv(b"a,b,c\n1,2,3\n")
    with pytest.raises(ImportFormatError):
        parse_csv(b"x" * (10 * 1024 * 1024 + 1))


def test_export_roundtrip():
    entries = [
        Entry(service="Steam", username="ale", password='a,"b"\nc', url="https://store.steampowered.com",
              has_2fa=True, twofa_app="Steam Guard", notes="n1", category_id="c1", favorite=True),
        Entry(service="Banco", username="", password="=1+1"),
    ]
    text = export_csv(entries, {"c1": "Jogos"})
    assert text.startswith("service,url,username,password")
    r = parse_csv(text.encode("utf-8"))
    assert r.source == "owlock"
    by = {e.service: e for e in r.entries}
    assert by["Steam"].password == 'a,"b"\nc' and by["Steam"].has_2fa and by["Steam"].twofa_app == "Steam Guard"
    assert by["Steam"].favorite and by["Banco"].password == "=1+1"
    assert r.categories[[e.service for e in r.entries].index("Steam")] == "Jogos"


def test_duplicates():
    existing = [Entry(service="GitHub", username="Ale", password="x", url="https://github.com")]
    cands = [
        Entry(service="github.com", username="ale", password="x", url="https://www.github.com/login"),
        Entry(service="GitHub", username="ale", password="outra"),
        Entry(service="GitHub", username="ale", password="outra"),
    ]
    assert find_duplicates(cands, existing) == [True, False, True]


# ---- Api ----
@pytest.fixture
def api(tmp_path):
    saved = {}

    def save_dialog(name):
        saved["name"] = name
        return saved.get("target")

    api = Api(tmp_path / "c.vault", clipboard=Clip(), store=MemoryStore(), save_dialog=save_dialog, kdf_params=FAST)
    api._saved = saved
    assert api.create_vault(PW, PW)["ok"]
    return api


def write(tmp_path, data, name="senhas.csv"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_api_import_flow(api, tmp_path):
    src = write(tmp_path, BITWARDEN)
    r = api._import_preview_file(str(src))
    assert r["ok"] and r["source"] == "bitwarden" and r["total"] == 2 and r["new"] == 2
    assert r["skipped"] == 1 and r["new_categories"] == []  # "Jogos" e "Trabalho" já existem
    src = write(tmp_path, BITWARDEN.replace(b"Jogos", b"Steam e PC"))
    r = api._import_preview_file(str(src))
    assert r["new_categories"] == ["Steam e PC"]
    assert all("password" not in item for item in r["items"])
    assert api.import_confirm("errado")["error"] == "no_import"
    done = api.import_confirm(r["token"], False, True)
    assert done == {"ok": True, "imported": 2, "categories": 1, "deleted_file": True}
    assert not src.exists()
    entries = api.list_entries("", "all", "")["entries"]
    assert {e["service"] for e in entries} == {"Steam", "Intranet"}
    cats = {c["name"] for c in api.list_categories()["categories"]}
    assert "Steam e PC" in cats
    steam = next(e for e in entries if e["service"] == "Steam")
    assert steam["favorite"]
    # importar de novo: tudo duplicado, nada entra
    src = write(tmp_path, BITWARDEN)
    again = api._import_preview_file(str(src))
    assert again["duplicates"] == 2 and again["new"] == 0 and again["new_categories"] == []
    assert api.import_confirm(again["token"])["imported"] == 0
    assert src.exists()


def test_api_import_persists(api, tmp_path):
    r = api._import_preview_file(str(write(tmp_path, CHROME)))
    assert api.import_confirm(r["token"])["imported"] == 3
    api.lock()
    assert api.unlock(PW)["ok"]
    assert len(api.list_entries("", "all", "")["entries"]) == 3


def test_api_import_errors_and_lock(api, tmp_path):
    assert api._import_preview_file(str(tmp_path / "nao-existe.csv"))["error"] == "read_failed"
    assert api._import_preview_file(str(write(tmp_path, b"a,b\n1,2\n")))["error"] == "invalid_format"
    assert api.import_pick()["error"] == "open_failed"  # sem janela de abrir
    r = api._import_preview_file(str(write(tmp_path, CHROME)))
    api.lock()
    assert api._pending_import is None
    assert api.import_confirm(r["token"])["error"] == "locked"


def test_api_import_pick_uses_dialog(tmp_path):
    src = write(tmp_path, FIREFOX)
    api = Api(tmp_path / "c.vault", clipboard=Clip(), store=MemoryStore(), kdf_params=FAST,
              open_dialog=lambda: [str(src)])
    assert api.create_vault(PW, PW)["ok"]
    assert api.import_pick()["source"] == "firefox"
    api._open_dialog = lambda: None
    assert api.import_pick()["error"] == "cancelled"
    assert api.import_cancel() == {"ok": True} and api._pending_import is None


def test_api_export(api, tmp_path):
    api.save_entry({"service": "Steam", "username": "ale", "password": "St3am!"})
    assert api.export_vault("errada")["error"] == "wrong_password"
    assert api.export_vault(PW)["error"] == "cancelled"
    assert api._saved["name"].startswith("OwLock-exportacao-") and api._saved["name"].endswith(".csv")
    api._saved["target"] = str(tmp_path / "saida")
    r = api.export_vault(PW)
    assert r["ok"] and r["count"] == 1 and r["path"].endswith("saida.csv")
    text = (tmp_path / "saida.csv").read_text("utf-8")
    assert "Steam" in text and "St3am!" in text
    api.lock()
    assert api.export_vault(PW)["error"] == "locked"


def test_vault_add_many_rolls_back(tmp_path, monkeypatch):
    v = Vault.create(tmp_path / "v.vault", PW, kdf_params=FAST, store=MemoryStore())
    monkeypatch.setattr(v, "save", lambda: (_ for _ in ()).throw(OSError("disco")))
    with pytest.raises(OSError):
        v.add_many([Entry(service="a")])
    assert v.entries == []
