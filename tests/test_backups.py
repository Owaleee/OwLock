"""Backups com histórico: snapshots, limite, restauração e troca de senha mestra."""
import json
import os
import re
import stat
import sys
from datetime import datetime, timedelta, timezone

import pytest

from owlock.app.api import Api
from owlock.core import (
    Entry, MemoryStore, Vault, VaultCorruptedError, WrongPasswordError,
)
from owlock.core import crypto
from owlock.core import vault as vault_mod
from owlock.core.vault import _create_v1

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"
NEW_PW = "nova-senha-123"
T0 = datetime(2026, 11, 17, 10, 0, 0, tzinfo=timezone.utc)
ID_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
posix = pytest.mark.skipif(sys.platform == "win32", reason="permissões POSIX")


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cofre.vault"


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def vault(path, store, clock):
    v = Vault.create(path, PW, store, kdf_params=FAST)
    v.clock = clock
    return v


def ent(name, password="P@ssUnica#987"):
    return Entry(service=name, username="u", password=password)


def ids_of(vault):
    return [b["id"] for b in vault.list_backups()]


def snap_file(vault, backup_id):
    return vault.backups_dir / f"{backup_id}.vault"


# ---------------- criação dos snapshots ----------------
def test_no_snapshot_on_create_and_first_save_snapshots_previous_state(vault, clock):
    assert vault.list_backups() == []
    vault.add(ent("A"))
    (b,) = vault.list_backups()
    assert b["entries"] == 0  # o snapshot é do estado ANTES de gravar
    assert b["created_at"] == "2026-11-17T10:00:00+00:00"
    assert b["id"] == "20261117-100000"
    assert b["size"] == snap_file(vault, b["id"]).stat().st_size


def test_one_hour_rule_with_injected_clock(vault, clock):
    vault.add(ent("A"))                      # snapshot 1 (0 contas)
    clock.advance(minutes=30)
    vault.add(ent("B"))                      # < 1h: nada
    clock.advance(minutes=30)
    vault.add(ent("C"))                      # exatamente 1h desde o último: ainda nada
    assert len(vault.list_backups()) == 1
    clock.advance(seconds=1)
    vault.add(ent("D"))                      # 1h e 1s: snapshot com A, B, C
    backups = vault.list_backups()
    assert [b["entries"] for b in backups] == [3, 0]
    assert backups[0]["created_at"] == "2026-11-17T11:00:01+00:00"


def test_snapshot_is_exact_copy_of_previous_file(vault, clock):
    vault.add(ent("A"))
    before = vault.path.read_bytes()
    clock.advance(hours=2)
    vault.add(ent("B"))
    newest = ids_of(vault)[0]
    assert snap_file(vault, newest).read_bytes() == before


def test_limit_keeps_20_most_recent(vault, clock):
    made = []
    for i in range(25):
        vault.add(ent(f"E{i}"))
        clock.advance(hours=2)
        made.append(ids_of(vault)[0])
    kept = ids_of(vault)
    assert len(kept) == 20
    assert kept == list(reversed(made))[:20]
    assert len(list(vault.backups_dir.glob("*.vault"))) == 20


def test_create_backup_ignores_one_hour_rule(vault):
    vault.add(ent("A"))                      # snapshot automático (0 contas)
    made = vault.create_backup()             # logo em seguida: mesmo assim cria
    assert ID_RE.match(made)
    assert len(ids_of(vault)) == 2
    assert vault.list_backups()[0]["entries"] == 1


def test_same_second_collision_suffixes_are_2_then_3(path, store, clock):
    v = Vault.create(path, PW, store, kdf_params=FAST)
    v.clock = clock
    assert v.create_backup() == "20261117-100000"
    assert v.create_backup() == "20261117-100000-2"
    assert v.create_backup() == "20261117-100000-3"
    assert ids_of(v) == ["20261117-100000-3", "20261117-100000-2", "20261117-100000"]


def test_suffix_ordering_beyond_9(path, store, clock):
    v = Vault.create(path, PW, store, kdf_params=FAST)
    v.clock = clock
    made = [v.create_backup() for _ in range(12)]
    assert ids_of(v) == list(reversed(made))  # -10 vem depois de -9


@posix
def test_permissions_700_dir_and_600_files(vault, clock):
    vault.add(ent("A"))
    clock.advance(hours=2)
    vault.add(ent("B"))
    assert stat.S_IMODE(os.stat(vault.backups_dir).st_mode) == 0o700
    files = list(vault.backups_dir.iterdir())
    assert files and all(stat.S_IMODE(os.stat(f).st_mode) == 0o600 for f in files)
    assert not [f for f in files if f.name.endswith(".tmp")]  # escrita atômica não deixa temporário


@posix
def test_backup_dir_permission_fixed_if_it_already_existed_open(vault):
    vault.backups_dir.mkdir(mode=0o755)
    os.chmod(vault.backups_dir, 0o755)
    vault.create_backup()
    assert stat.S_IMODE(os.stat(vault.backups_dir).st_mode) == 0o700


def test_snapshot_failure_does_not_block_save(vault, clock, store, monkeypatch):
    vault.add(ent("A"))
    clock.advance(hours=2)

    def boom(self):
        raise OSError("sem espaço")

    monkeypatch.setattr(Vault, "_snapshot", boom)
    vault.add(ent("B"))  # não levanta
    assert len(Vault.open(vault.path, PW, store).entries) == 2



# ---------------- listagem ----------------
def test_list_backups_does_not_decrypt(vault, clock, monkeypatch):
    vault.add(ent("A"))
    clock.advance(hours=2)
    vault.add(ent("B"))

    def no_decrypt(*a, **k):
        raise AssertionError("list_backups não deve decifrar")

    monkeypatch.setattr(crypto, "decrypt", no_decrypt)
    backups = vault.list_backups()
    assert [b["entries"] for b in backups] == [1, 0]
    assert set(backups[0]) == {"id", "created_at", "size", "entries"}


def test_list_backups_skips_foreign_garbage_and_odd_names(vault, store, tmp_path):
    vault.add(ent("A"))
    good = ids_of(vault)
    other = Vault.create(tmp_path / "outro.vault", PW, store, kdf_params=FAST)
    (vault.backups_dir / "20260101-000000.vault").write_bytes(other.path.read_bytes())  # outro cofre
    (vault.backups_dir / "20260102-000000.vault").write_bytes(b"lixo")
    (vault.backups_dir / "notas.txt").write_text("x")
    (vault.backups_dir / "2026-01-01.vault").write_bytes(vault.path.read_bytes())
    (vault.backups_dir / "20260103-000000.vault.tmp").write_bytes(b"x")
    (vault.backups_dir / "99999999-999999.vault").write_bytes(vault.path.read_bytes())  # data impossível
    assert ids_of(vault) == good


def test_list_backups_empty_when_folder_missing(vault):
    assert not vault.backups_dir.exists()
    assert vault.list_backups() == []


# ---------------- restauração ----------------
def prepare(vault, clock):
    """Cria um backup com A, B e devolve (id, estado atual com A, B, C)."""
    vault.add(ent("A"))
    vault.add(ent("B"))
    backup_id = vault.create_backup()
    clock.advance(hours=3)
    vault.add(ent("C"))
    vault.delete(vault.entries[0].id)  # tira A
    return backup_id


def test_restore_ok(vault, clock, path, store):
    backup_id = prepare(vault, clock)
    assert [e.service for e in vault.entries] == ["B", "C"]
    before = ids_of(vault)
    assert vault.restore_backup(backup_id, PW) == 2
    assert sorted(e.service for e in vault.entries) == ["A", "B"]
    reopened = Vault.open(path, PW, store)
    assert sorted(e.service for e in reopened.entries) == ["A", "B"]
    # o .bak acompanha o arquivo restaurado
    assert path.with_name(path.name + ".bak").read_bytes() == path.read_bytes()
    # estado anterior à restauração virou snapshot (B, C)
    new = [i for i in ids_of(vault) if i not in before]
    assert len(new) == 1
    pre = vault.list_backups()[0]
    assert pre["id"] == new[0] and pre["entries"] == 2
    snap = Vault.open(snap_file(vault, new[0]), PW, store)
    assert sorted(e.service for e in snap.entries) == ["B", "C"]


def test_restore_keeps_categories_settings_services(vault, clock, path, store):
    from owlock.core import Category, Settings

    vault.add_category(Category("Extra", "blue", "star"))
    vault.update_settings(Settings(auto_lock_minutes=10, clipboard_clear_seconds=60))
    backup_id = vault.create_backup()
    vault.delete_category(vault.categories[-1].id)
    vault.update_settings(Settings())
    vault.restore_backup(backup_id, PW)
    reopened = Vault.open(path, PW, store)
    assert reopened.categories[-1].name == "Extra"
    assert reopened.settings.auto_lock_minutes == 10


def test_restore_wrong_password_changes_nothing(vault, clock, path):
    backup_id = prepare(vault, clock)
    file_before, ids_before = path.read_bytes(), ids_of(vault)
    names = [e.service for e in vault.entries]
    with pytest.raises(WrongPasswordError):
        vault.restore_backup(backup_id, "senha-errada-99")
    assert path.read_bytes() == file_before
    assert ids_of(vault) == ids_before
    assert [e.service for e in vault.entries] == names


@pytest.mark.parametrize(
    "bad",
    ["../x", "../../etc/passwd", "..", ".", "", "a", "20261117-100000/../x", "20261117-100000\n",
     "20261117-100000-", "20261117-100000-x", "２０２６１１１７-１００００００", "/etc/passwd", None, 5, ["x"]],
)
def test_restore_invalid_id_is_not_found(vault, clock, path, bad):
    prepare(vault, clock)
    file_before = path.read_bytes()
    with pytest.raises(FileNotFoundError):
        vault.restore_backup(bad, PW)
    assert path.read_bytes() == file_before


def test_path_traversal_never_reads_outside_backups(vault, clock, path):
    prepare(vault, clock)
    # um arquivo válido FORA da pasta de backups, alcançável por "../"
    (path.parent / "x.vault").write_bytes(path.read_bytes())
    file_before = path.read_bytes()
    with pytest.raises(FileNotFoundError):
        vault.restore_backup("../x", PW)
    with pytest.raises(FileNotFoundError):
        vault.restore_backup("../cofre", PW)
    assert path.read_bytes() == file_before


def test_restore_missing_valid_id_is_not_found(vault):
    vault.add(ent("A"))
    with pytest.raises(FileNotFoundError):
        vault.restore_backup("20200101-000000", PW)


def test_restore_other_vault_is_corrupted(vault, clock, path, store, tmp_path):
    prepare(vault, clock)
    other = Vault.create(tmp_path / "outro.vault", PW, store, kdf_params=FAST)
    other.add(ent("Intruso"))
    (vault.backups_dir / "20200101-000000.vault").write_bytes(other.path.read_bytes())
    file_before = path.read_bytes()
    with pytest.raises(VaultCorruptedError):
        vault.restore_backup("20200101-000000", PW)
    assert path.read_bytes() == file_before
    assert [e.service for e in vault.entries] == ["B", "C"]


def test_restore_same_id_different_key_is_corrupted(vault, clock, path):
    """Mesmo vault_id, mas chave do cofre diferente (forjado): a decifragem completa barra."""
    prepare(vault, clock)
    doc = json.loads(path.read_text())
    forged = vault_mod.Vault._fresh(path, PW, FAST, entries=[ent("Falso")])
    forged._vault_id = vault.vault_id
    forged._secret = vault._secret
    forged._kek = vault._kek
    forged._salt = vault._salt
    (vault.backups_dir / "20200101-000000.vault").write_bytes(forged._serialize())
    file_before = path.read_bytes()
    with pytest.raises(VaultCorruptedError):
        vault.restore_backup("20200101-000000", PW)
    assert path.read_bytes() == file_before
    assert doc["vault_id"] == vault.vault_id


@pytest.mark.parametrize("kind", ["garbage", "not_json_object", "tampered_entry", "tampered_meta", "truncated", "wrong_format"])
def test_restore_corrupted_file_changes_nothing(vault, clock, path, kind):
    backup_id = prepare(vault, clock)
    file = snap_file(vault, backup_id)
    doc = json.loads(file.read_text())
    if kind == "garbage":
        file.write_bytes(b"\x00\xffnada")
    elif kind == "not_json_object":
        file.write_text("[1, 2]")
    elif kind == "tampered_entry":
        ct = doc["entries"][0]["ciphertext"]
        doc["entries"][0]["ciphertext"] = ("A" if ct[0] != "A" else "B") + ct[1:]
        file.write_text(json.dumps(doc))
    elif kind == "tampered_meta":
        ct = doc["meta"]["ciphertext"]
        doc["meta"]["ciphertext"] = ("A" if ct[0] != "A" else "B") + ct[1:]
        file.write_text(json.dumps(doc))
    elif kind == "truncated":
        file.write_bytes(file.read_bytes()[:40])
    else:
        doc["format"] = "outra-coisa"
        file.write_text(json.dumps(doc))
    file_before, ids_before = path.read_bytes(), ids_of(vault)
    names = [e.service for e in vault.entries]
    with pytest.raises(VaultCorruptedError):
        vault.restore_backup(backup_id, PW)
    assert path.read_bytes() == file_before
    assert [e.service for e in vault.entries] == names
    assert not [i for i in ids_of(vault) if i not in ids_before]  # nenhum snapshot novo


def test_restore_write_failure_leaves_state_untouched(vault, clock, path, monkeypatch):
    backup_id = prepare(vault, clock)
    file_before = path.read_bytes()
    names = [e.service for e in vault.entries]

    def boom(self, data, keep_bak=True):
        raise OSError("disco cheio")

    monkeypatch.setattr(Vault, "_write", boom)
    with pytest.raises(OSError):
        vault.restore_backup(backup_id, PW)
    monkeypatch.undo()
    assert path.read_bytes() == file_before
    assert [e.service for e in vault.entries] == names


def test_restore_aborts_if_pre_restore_snapshot_fails(vault, clock, path, monkeypatch):
    backup_id = prepare(vault, clock)
    file_before = path.read_bytes()

    def boom(self):
        raise OSError("sem espaço")

    monkeypatch.setattr(Vault, "_snapshot", boom)
    with pytest.raises(OSError):
        vault.restore_backup(backup_id, PW)
    assert path.read_bytes() == file_before


def test_restored_vault_keeps_working_and_saving(vault, clock, path, store):
    backup_id = prepare(vault, clock)
    vault.restore_backup(backup_id, PW)
    vault.add(ent("Nova"))
    assert sorted(e.service for e in Vault.open(path, PW, store).entries) == ["A", "B", "Nova"]


# ---------------- troca de senha mestra ----------------
def open_copy(src, tmp_path, store, password, name="copia.vault"):
    dest = tmp_path / name
    dest.write_bytes(src.read_bytes())
    return Vault.open(dest, password, store)


def test_password_change_updates_every_valid_snapshot(vault, clock, path, store, tmp_path):
    for i in range(4):
        vault.add(ent(f"E{i}"))
        clock.advance(hours=2)
    ids = ids_of(vault)
    assert len(ids) >= 3
    # o snapshot com a senha antiga abre antes da troca
    assert open_copy(snap_file(vault, ids[0]), tmp_path, store, PW).entries is not None
    originals = {i: json.loads(snap_file(vault, i).read_text()) for i in ids}

    vault.change_master_password(PW, NEW_PW)  # (o próprio save da troca cria mais um snapshot)

    after = ids_of(vault)
    assert set(ids) < set(after) and len(after) == len(ids) + 1
    assert vault.backup_report == {"updated": sorted(after), "skipped": []}
    for i in after:
        with pytest.raises(WrongPasswordError):
            open_copy(snap_file(vault, i), tmp_path, store, PW)
        open_copy(snap_file(vault, i), tmp_path, store, NEW_PW)
    for i in ids:
        with pytest.raises(WrongPasswordError):
            open_copy(snap_file(vault, i), tmp_path, store, PW)
        opened = open_copy(snap_file(vault, i), tmp_path, store, NEW_PW)
        assert len(opened.entries) == len(originals[i]["entries"])
        # só kdf.salt e o bloco key mudam; o resto do JSON é preservado
        now = json.loads(snap_file(vault, i).read_text())
        assert now["kdf"]["salt"] != originals[i]["kdf"]["salt"]
        assert now["key"] != originals[i]["key"]
        for k in ("format", "version", "vault_id", "secret_key", "cipher", "meta", "entries"):
            assert now[k] == originals[i][k]
        assert {k: v for k, v in now["kdf"].items() if k != "salt"} == {k: v for k, v in originals[i]["kdf"].items() if k != "salt"}
    assert path.with_name(path.name + ".bak").read_bytes() == path.read_bytes()


def test_password_change_ignores_foreign_and_invalid_snapshots(vault, clock, path, store, tmp_path):
    vault.add(ent("A"))
    clock.advance(hours=2)
    vault.add(ent("B"))
    good = ids_of(vault)
    other = Vault.create(tmp_path / "outro.vault", PW, store, kdf_params=FAST)
    foreign = other.path.read_bytes()
    (vault.backups_dir / "20200101-000000.vault").write_bytes(foreign)
    (vault.backups_dir / "20200102-000000.vault").write_bytes(b"lixo")
    tampered = json.loads(snap_file(vault, good[0]).read_text())
    ct = tampered["entries"][0]["ciphertext"]
    tampered["entries"][0]["ciphertext"] = ("A" if ct[0] != "A" else "B") + ct[1:]
    (vault.backups_dir / "20200103-000000.vault").write_text(json.dumps(tampered))
    invalid_before = (vault.backups_dir / "20200103-000000.vault").read_bytes()

    vault.change_master_password(PW, NEW_PW)

    assert sorted(vault.backup_report["updated"]) == sorted(good)
    assert sorted(vault.backup_report["skipped"]) == ["20200101-000000", "20200102-000000", "20200103-000000"]
    assert (vault.backups_dir / "20200101-000000.vault").read_bytes() == foreign  # intocado
    assert (vault.backups_dir / "20200102-000000.vault").read_bytes() == b"lixo"
    assert (vault.backups_dir / "20200103-000000.vault").read_bytes() == invalid_before
    for i in good:
        open_copy(snap_file(vault, i), tmp_path, store, NEW_PW)


def test_password_change_wrong_current_touches_no_snapshot(vault, clock, store, tmp_path):
    vault.add(ent("A"))
    clock.advance(hours=2)
    vault.add(ent("B"))
    before = {i: snap_file(vault, i).read_bytes() for i in ids_of(vault)}
    with pytest.raises(WrongPasswordError):
        vault.change_master_password("senha-errada-99", NEW_PW)
    assert {i: snap_file(vault, i).read_bytes() for i in ids_of(vault)} == before


def test_password_change_snapshot_taken_during_save_is_updated_too(vault, clock, store, tmp_path):
    vault.add(ent("A"))
    clock.advance(hours=2)  # a própria troca (que salva) cria um snapshot com a senha antiga
    vault.change_master_password(PW, NEW_PW)
    ids = ids_of(vault)
    assert len(ids) == 2
    for i in ids:
        with pytest.raises(WrongPasswordError):
            open_copy(snap_file(vault, i), tmp_path, store, PW)
        open_copy(snap_file(vault, i), tmp_path, store, NEW_PW)


def test_restore_after_password_change_opens_with_new_password(vault, clock, path, store):
    vault.add(ent("A"))
    backup_id = vault.create_backup()
    vault.add(ent("B"))
    vault.change_master_password(PW, NEW_PW)
    vault.restore_backup(backup_id, NEW_PW)
    assert [e.service for e in Vault.open(path, NEW_PW, store).entries] == ["A"]
    with pytest.raises(WrongPasswordError):
        Vault.open(path, PW, store)
    with pytest.raises(WrongPasswordError):
        vault.restore_backup(backup_id, PW)


def test_restore_of_stale_snapshot_is_rekeyed_to_current_password(vault, clock, path, store):
    vault.add(ent("A"))
    backup_id = vault.create_backup()
    stale = snap_file(vault, backup_id).read_bytes()  # abre com a senha antiga
    vault.change_master_password(PW, NEW_PW)
    snap_file(vault, backup_id).write_bytes(stale)  # simula um snapshot que não foi atualizado
    vault.restore_backup(backup_id, NEW_PW)
    assert [e.service for e in Vault.open(path, NEW_PW, store).entries] == ["A"]


# ---------------- migração ----------------
def test_backup_after_migration(path, store):
    _create_v1(path, PW, FAST, entries=[ent("A"), ent("B")])
    v = Vault.open(path, PW, store)
    assert v.migrated
    (b,) = v.list_backups()
    assert b["entries"] == 2
    opened = Vault.open(snap_file(v, b["id"]), PW, store)
    assert sorted(e.service for e in opened.entries) == ["A", "B"]
    assert not (v.backups_dir / "20200101-000000.vault").exists()


# ---------------- Api ----------------
@pytest.fixture
def api(path, store):
    Vault.create(path, PW, store, kdf_params=FAST)
    a = Api(path, store=store, kdf_params=FAST)
    assert a.unlock(PW)["ok"]
    a._vault.clock = Clock()
    return a


def test_api_requires_unlocked(path, store):
    Vault.create(path, PW, store, kdf_params=FAST)
    a = Api(path, store=store, kdf_params=FAST)
    assert a.list_backups()["error"] == "locked"
    assert a.restore_backup("20200101-000000", PW)["error"] == "locked"


def test_api_list_and_restore(api, path):
    api.save_entry({"service": "A", "password": "x1"})
    api.save_entry({"service": "B", "password": "x2"})
    backup_id = api._vault.create_backup()
    api.save_entry({"service": "C", "password": "x3"})
    r = api.list_backups()
    assert r["ok"] and r["backups"][0]["id"] == backup_id and r["backups"][0]["entries"] == 2
    assert api.list_entries()["stats"]["total"] == 3
    res = api.restore_backup(backup_id, PW)
    assert res == {"ok": True, "entries": 2}
    assert sorted(e["service"] for e in api.list_entries()["entries"]) == ["A", "B"]
    # automático do 1º salvamento + o manual + o estado anterior à restauração
    backups = api.list_backups()["backups"]
    assert len(backups) == 3 and backups[0]["entries"] == 3


def test_api_restore_errors(api, path, tmp_path, store):
    api.save_entry({"service": "A", "password": "x1"})
    backup_id = api._vault.create_backup()
    wrong = api.restore_backup(backup_id, "senha-errada-99")
    assert wrong["ok"] is False and wrong["error"] == "wrong_password" and wrong["message"]
    assert api.restore_backup(backup_id, None)["error"] == "wrong_password"
    for bad in ("../x", "", None, 7, "20200101-000000"):
        r = api.restore_backup(bad, PW)
        assert r["ok"] is False and r["error"] == "not_found"
    (api._vault.backups_dir / "20200101-000000.vault").write_bytes(b"lixo")
    assert api.restore_backup("20200101-000000", PW)["error"] == "corrupted"
    other = Vault.create(tmp_path / "outro.vault", PW, store, kdf_params=FAST)
    (api._vault.backups_dir / "20200102-000000.vault").write_bytes(other.path.read_bytes())
    assert api.restore_backup("20200102-000000", PW)["error"] == "corrupted"
    assert api.list_entries()["stats"]["total"] == 1


def test_api_restore_save_failed(api, monkeypatch):
    api.save_entry({"service": "A", "password": "x1"})
    backup_id = api._vault.create_backup()

    def boom(self, data, keep_bak=True):
        raise OSError("disco cheio")

    monkeypatch.setattr(Vault, "_write", boom)
    assert api.restore_backup(backup_id, PW)["error"] == "save_failed"


def test_api_change_master_password_updates_backups(api, path, store, tmp_path):
    api.save_entry({"service": "A", "password": "x1"})
    api._vault.create_backup()
    api._vault.create_backup()
    assert api.change_master_password(PW, NEW_PW, NEW_PW) == {"ok": True}
    for b in api.list_backups()["backups"]:
        file = api._vault.backups_dir / f"{b['id']}.vault"
        open_copy(file, tmp_path, store, NEW_PW)
        with pytest.raises(WrongPasswordError):
            open_copy(file, tmp_path, store, PW)


def test_api_backup_responses_never_leak_secrets(api):
    api.save_entry({"service": "Segredo", "username": "quem@x.com", "password": "SenhaMuitoSecreta#1"})
    api._vault.create_backup()
    text = json.dumps(api.list_backups())
    assert "SenhaMuitoSecreta" not in text and "Segredo" not in text and "quem@x.com" not in text
