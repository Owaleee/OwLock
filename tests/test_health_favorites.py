"""Saúde das senhas (repetidas/antigas) e contas favoritas."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from owlock.app.api import Api
from owlock.core import Entry, Vault, password_health
from tests._store import STORE

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"
NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)


def iso(moment):
    return moment.isoformat(timespec="seconds")


def ago(days, base=NOW):
    return iso(base - timedelta(days=days))


def entry(service, password, created_days=10, history=None, **kw):
    return Entry(service, "u", password, created_at=ago(created_days), password_history=history or [], **kw)


# ---------------- função pura ----------------
def test_reused_two_accounts():
    a, b, c = entry("A", "Igual#12345"), entry("B", "Igual#12345"), entry("C", "Outra#98765")
    h = password_health([a, b, c], NOW)
    assert h[a.id]["reused"] and h[b.id]["reused"]
    assert h[a.id]["reused_count"] == 1 and h[a.id]["reused_with"] == [b.id]
    assert h[b.id]["reused_with"] == [a.id]
    assert not h[c.id]["reused"] and h[c.id]["reused_count"] == 0 and h[c.id]["reused_with"] == []


def test_reused_three_accounts():
    items = [entry(n, "Igual#12345") for n in "ABC"]
    h = password_health(items, NOW)
    for e in items:
        assert h[e.id]["reused"] and h[e.id]["reused_count"] == 2
        assert sorted(h[e.id]["reused_with"]) == sorted(o.id for o in items if o is not e)


def test_empty_password_is_not_reused():
    a, b = entry("A", ""), entry("B", "")
    h = password_health([a, b], NOW)
    assert not h[a.id]["reused"] and h[a.id]["reused_count"] == 0
    assert not h[b.id]["reused"]


def test_reused_compares_exact_password_only():
    a, b = entry("A", "Senha#12345"), entry("B", "senha#12345")
    assert not password_health([a, b], NOW)[a.id]["reused"]


def test_stale_boundary_365_vs_366_days():
    exact, over = entry("A", "x1", created_days=365), entry("B", "x2", created_days=366)
    h = password_health([exact, over], NOW)
    assert h[exact.id]["stale"] is False
    assert h[over.id]["stale"] is True


def test_stale_uses_utc_dates_with_injected_clock():
    e = entry("A", "x1", created_days=366)
    assert password_health([e], NOW)[e.id]["stale"] is True
    # relógio voltando no tempo: deixa de ser antiga
    assert password_health([e], NOW - timedelta(days=10))[e.id]["stale"] is False
    # data local com fuso diferente vira a mesma data UTC
    sp = timezone(timedelta(hours=-3))
    assert password_health([e], NOW.astimezone(sp))[e.id]["stale"] is True


def test_stale_uses_latest_history_change():
    old_hist = [{"password": "p1", "changed_at": ago(800)}, {"password": "p0", "changed_at": ago(30)}]
    e = entry("A", "x1", created_days=1000, history=old_hist)
    assert password_health([e], NOW)[e.id]["stale"] is False  # trocada há 30 dias
    e2 = entry("B", "x2", created_days=10, history=[{"password": "p", "changed_at": ago(400)}])
    assert password_health([e2], NOW)[e2.id]["stale"] is True  # histórico manda, não o created_at
    e3 = entry("C", "x3", created_days=1000, history=[{"password": "p", "changed_at": ago(365)}])
    assert password_health([e3], NOW)[e3.id]["stale"] is False


def test_stale_unparseable_dates_are_not_stale():
    e = Entry("A", "u", "x1", created_at="ontem")
    assert password_health([e], NOW)[e.id]["stale"] is False


def test_health_never_contains_passwords():
    a, b = entry("A", "Igual#12345"), entry("B", "Igual#12345")
    assert "Igual#12345" not in json.dumps(password_health([a, b], NOW))


# ---------------- Api ----------------
@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


def build(path, entries):
    v = Vault.create(path, PW, STORE, kdf_params=FAST)
    for e in entries:
        v.add(e)
    api = Api(path, store=STORE, kdf_params=FAST)
    assert api.unlock(PW)["ok"]
    api._vault.clock = lambda: NOW
    return api


STRONG1, STRONG2, STRONG3 = "Gx4!nP8s#Qd1vL2@", "T7#qLm9!vRz2@kWp", "Hk3$wTz9&pLq5!mB"


def by_service(api, **kw):
    return {e["service"]: e for e in api.list_entries(**kw)["entries"]}


def test_summary_health_fields_and_stats(path):
    api = build(path, [
        entry("Steam", STRONG2), entry("Netflix", STRONG2), entry("Limpa", STRONG1),
        entry("Velha", STRONG3, created_days=400), entry("Fraca", "123456"),
    ])
    r = api.list_entries()
    rows = {e["service"]: e for e in r["entries"]}
    assert rows["Steam"]["reused"] and rows["Steam"]["reused_count"] == 1
    assert rows["Netflix"]["reused"] and rows["Netflix"]["reused_count"] == 1
    assert not rows["Limpa"]["reused"] and rows["Limpa"]["reused_count"] == 0
    assert rows["Velha"]["stale"] and not rows["Limpa"]["stale"]
    assert all(e["favorite"] is False for e in rows.values())
    assert r["stats"]["reused"] == 2 and r["stats"]["stale"] == 1
    # fraca (score <= 2) + 2 repetidas + 1 antiga
    assert r["stats"]["attention"] == 4
    assert r["stats"]["total"] == 5


def test_attention_filter_includes_reused_and_stale(path):
    api = build(path, [
        entry("Steam", STRONG2), entry("Netflix", STRONG2), entry("Limpa", STRONG1),
        entry("Velha", STRONG3, created_days=400), entry("Fraca", "123456"),
    ])
    names = [e["service"] for e in api.list_entries(filter="attention")["entries"]]
    assert names == ["Fraca", "Netflix", "Steam", "Velha"]
    assert "Limpa" not in names


def test_stale_with_history_is_not_attention(path):
    hist = [{"password": "antiga", "changed_at": ago(20)}]
    api = build(path, [entry("Recente", STRONG1, created_days=900, history=hist)])
    row = by_service(api)["Recente"]
    assert row["stale"] is False
    assert api.list_entries(filter="attention")["entries"] == []
    assert api.list_entries()["stats"]["attention"] == 0


def test_get_entry_reused_with_has_only_id_and_service(path):
    api = build(path, [entry("Steam", STRONG2), entry("Netflix", STRONG2), entry("Epic", STRONG2), entry("Limpa", STRONG1)])
    rows = by_service(api)
    got = api.get_entry(rows["Steam"]["id"])["entry"]
    assert got["reused_count"] == 2
    assert sorted(got["reused_with"], key=lambda x: x["service"]) == [
        {"id": rows["Epic"]["id"], "service": "Epic"},
        {"id": rows["Netflix"]["id"], "service": "Netflix"},
    ]
    assert api.get_entry(rows["Limpa"]["id"])["entry"]["reused_with"] == []


def test_no_password_leaks_in_any_response(path):
    api = build(path, [entry("Steam", STRONG2), entry("Netflix", STRONG2)])
    rows = by_service(api)
    dumped = json.dumps(api.list_entries()) + json.dumps(api.get_entry(rows["Steam"]["id"]))
    dumped += json.dumps(api.toggle_favorite(rows["Steam"]["id"]))
    assert STRONG2 not in dumped
    assert "password" not in api.get_entry(rows["Steam"]["id"])["entry"]


def test_health_updates_when_password_changes(path):
    api = build(path, [entry("Steam", STRONG2), entry("Netflix", STRONG2)])
    rows = by_service(api)
    assert api.save_entry({"id": rows["Netflix"]["id"], "service": "Netflix", "password": STRONG1})["ok"]
    after = by_service(api)
    assert not after["Steam"]["reused"] and not after["Netflix"]["reused"]
    assert api.list_entries()["stats"]["reused"] == 0


def test_save_entry_summary_has_health_and_favorite(path):
    api = build(path, [entry("Steam", STRONG2)])
    r = api.save_entry({"service": "Netflix", "password": STRONG2})
    assert r["entry"]["reused"] and r["entry"]["reused_count"] == 1 and r["entry"]["favorite"] is False


# ---------------- favoritas ----------------
def test_toggle_favorite_roundtrip_and_persistence(path):
    api = build(path, [entry("Alfa", STRONG1), entry("Beta", STRONG2)])
    alfa = by_service(api)["Alfa"]["id"]
    updated = api.get_entry(alfa)["entry"]["updated_at"]
    assert api.toggle_favorite(alfa) == {"ok": True, "favorite": True}
    assert api.get_entry(alfa)["entry"]["favorite"] is True
    assert api.get_entry(alfa)["entry"]["updated_at"] == updated
    reopened = Vault.open(path, PW, STORE)
    assert [e.favorite for e in reopened.entries if e.service == "Alfa"] == [True]
    assert [e.favorite for e in reopened.entries if e.service == "Beta"] == [False]
    assert api.toggle_favorite(alfa) == {"ok": True, "favorite": False}
    assert Vault.open(path, PW, STORE).entries[0].favorite is False


def test_favorite_survives_edit(path):
    api = build(path, [entry("Alfa", STRONG1)])
    alfa = by_service(api)["Alfa"]["id"]
    api.toggle_favorite(alfa)
    assert api.save_entry({"id": alfa, "service": "Alfa 2", "password": STRONG2})["entry"]["favorite"] is True


def test_toggle_favorite_errors(path):
    api = build(path, [entry("Alfa", STRONG1)])
    assert api.toggle_favorite("nao-existe")["error"] == "not_found"
    assert api.toggle_favorite(None)["error"] == "not_found"
    api.lock()
    assert api.toggle_favorite("x")["error"] == "locked"


def test_toggle_favorite_failure_reverts(path, monkeypatch):
    api = build(path, [entry("Alfa", STRONG1)])
    alfa = by_service(api)["Alfa"]["id"]

    def boom(self):
        raise OSError("disco cheio")

    monkeypatch.setattr(Vault, "save", boom)
    assert api.toggle_favorite(alfa)["error"] == "save_failed"
    monkeypatch.undo()
    assert api.get_entry(alfa)["entry"]["favorite"] is False


def test_favorites_come_first_and_filter(path):
    api = build(path, [entry("Alfa", STRONG1), entry("Beta", STRONG2), entry("Zeta", STRONG3), entry("Gama", "123456")])
    rows = by_service(api)
    api.toggle_favorite(rows["Zeta"]["id"])
    api.toggle_favorite(rows["Beta"]["id"])
    names = [e["service"] for e in api.list_entries()["entries"]]
    assert names == ["Beta", "Zeta", "Alfa", "Gama"]
    assert [e["service"] for e in api.list_entries(filter="favorites")["entries"]] == ["Beta", "Zeta"]
    # filtro combina com busca e categoria
    assert [e["service"] for e in api.list_entries(query="zet", filter="favorites")["entries"]] == ["Zeta"]
    assert api.list_entries(query="alfa", filter="favorites")["entries"] == []
    # ordem com favoritas primeiro também vale no filtro de atenção
    api.toggle_favorite(rows["Gama"]["id"])
    assert [e["service"] for e in api.list_entries(filter="attention")["entries"]][0] == "Gama"


def test_invalid_filter_still_rejected(path):
    api = build(path, [entry("Alfa", STRONG1)])
    for bad in ("xyz", "favorite", "", None, 3):
        r = api.list_entries(filter=bad)
        assert r["ok"] is False and r["error"] == "invalid_filter"


def test_entry_favorite_from_dict_defaults():
    d = Entry("A").to_dict()
    d.pop("favorite")
    assert Entry.from_dict(d).favorite is False
    d["favorite"] = "sim"
    assert Entry.from_dict(d).favorite is False
    d["favorite"] = True
    assert Entry.from_dict(d).favorite is True


def test_old_vault_without_favorite_field_opens(path):
    v = Vault.create(path, PW, STORE, kdf_params=FAST)
    v.add(Entry("Alfa", "u", STRONG1))
    # o campo extra não existia antes: o arquivo continua abrindo e favorite vira False
    assert Vault.open(path, PW, STORE).entries[0].favorite is False


# ---------------- exemplo do devserver ----------------
def test_devserver_seed_shows_health_and_favorites(tmp_path):
    from owlock.app.devserver import SEED_PASSWORD, dev_store, seed_vault
    from owlock.core import crypto

    path = tmp_path / "seed.vault"
    orig = crypto.DEFAULT_KDF_PARAMS.copy()
    crypto.DEFAULT_KDF_PARAMS.update(FAST)
    try:
        seed_vault(path)
    finally:
        crypto.DEFAULT_KDF_PARAMS.update(orig)
    api = Api(path, store=dev_store(path), kdf_params=FAST)
    assert api.unlock(SEED_PASSWORD)["ok"]
    rows = by_service(api)
    assert {n for n, e in rows.items() if e["favorite"]} == {"Google", "GitHub"}
    assert rows["Steam"]["reused"] and rows["Netflix"]["reused"]
    assert rows["Epic Games"]["stale"]
    assert sum(1 for e in rows.values() if e["stale"]) == 1
    assert len(api.list_backups()["backups"]) == 2
