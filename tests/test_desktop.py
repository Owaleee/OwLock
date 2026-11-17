import sys
import threading

import pytest

from owlock.app.api import Api
from owlock.app.api_desktop import DesktopApiMixin
from owlock.app.config import DesktopConfig, config_path_for, load_config
from owlock.app.desktop import DesktopController, NullAutostart, NullHotkey, NullSessionWatcher, NullTray
from owlock.app.desktop import autostart as autostart_mod
from owlock.app.desktop import hotkey as hotkey_mod
from owlock.app.desktop import session as session_mod
from owlock.app.desktop import tray as tray_mod
from owlock.app.desktop.controller import LOCKED_JS
from owlock.core import Entry, Vault
from tests._store import STORE

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
PW = "senha-mestra-1"
WIN = sys.platform == "win32"
only_windows = pytest.mark.skipif(not WIN, reason="depende do Windows")


# ---------- falsos ----------
class Events:
    def __init__(self):
        self.items = []

    def __iadd__(self, fn):
        self.items.append(fn)
        return self

    def fire(self):
        return [fn() for fn in self.items]


class EventSet:
    def __init__(self):
        self.closing = Events()
        self.minimized = Events()


class FakeWindow:
    def __init__(self, name, log):
        self.name, self.log = name, log
        self.events = EventSet()
        self.js = []
        self.width, self.height = 560, 420

    def show(self):
        self.log.append(f"{self.name}.show")

    def hide(self):
        self.log.append(f"{self.name}.hide")

    def restore(self):
        self.log.append(f"{self.name}.restore")

    def destroy(self):
        self.log.append(f"{self.name}.destroy")

    def evaluate_js(self, js):
        self.js.append(js)

    def move(self, x, y):
        self.log.append(f"{self.name}.move")


class FakeApi:
    def __init__(self, log, unlocked=True):
        self.log, self.unlocked = log, unlocked

    def status(self):
        return {"unlocked": self.unlocked}

    def lock(self):
        self.unlocked = False
        self.log.append("api.lock")
        return {"ok": True}

    def shutdown(self):
        self.log.append("api.shutdown")
        return {"ok": True}

    def generate_and_copy(self):
        self.log.append("api.generate")
        return {"ok": True}


class FakeTray:
    available = True

    def __init__(self, handlers, log):
        self.h, self.log = handlers, log
        self.locked_calls = []

    def start(self):
        self.log.append("tray.start")

    def stop(self):
        self.log.append("tray.stop")

    def set_locked(self, locked):
        self.locked_calls.append(locked)

    def refresh(self):
        self.log.append("tray.refresh")


class FakeHotkey:
    supported = True

    def __init__(self, cb, log, ok=True):
        self.cb, self.log, self.ok, self.available = cb, log, ok, False

    def start(self):
        self.log.append("hotkey.start")
        self.available = self.ok
        return self.ok

    def stop(self):
        self.log.append("hotkey.stop")
        self.available = False


class FakeSession:
    def __init__(self, cb, log):
        self.cb, self.log = cb, log

    def start(self):
        self.log.append("session.start")

    def stop(self):
        self.log.append("session.stop")


class FakeAutostart:
    def __init__(self, log):
        self.log, self.on = log, False

    def is_enabled(self):
        return self.on

    def enable(self):
        self.on = True
        self.log.append("autostart.enable")

    def disable(self):
        self.on = False
        self.log.append("autostart.disable")


class Rig:
    def __init__(self, tmp_path, unlocked=True, config=None, hotkey_ok=True, tray=True):
        self.log = []
        self.api = FakeApi(self.log, unlocked)
        self.main = FakeWindow("main", self.log)
        self.quick = FakeWindow("quick", self.log)
        self.autostart = FakeAutostart(self.log)
        self.config_path = tmp_path / "config.json"
        made = {}

        def tray_factory(h):
            made["tray"] = FakeTray(h, self.log) if tray else NullTray()
            return made["tray"]

        def hotkey_factory(cb):
            made["hotkey"] = FakeHotkey(cb, self.log, hotkey_ok)
            return made["hotkey"]

        def session_factory(cb):
            made["session"] = FakeSession(cb, self.log)
            return made["session"]

        self.ctl = DesktopController(
            self.api, self.main, self.quick, config or DesktopConfig(), self.config_path,
            tray_factory, hotkey_factory, session_factory, self.autostart,
            center=lambda w: self.log.append("quick.center"),
        )
        self.made = made

    def start(self, **kw):
        self.ctl.start(**kw)
        return self


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path).start()


# ---------- controller ----------
def test_start_wires_everything(rig):
    assert rig.log[:3] == ["tray.start", "hotkey.start", "session.start"]
    assert len(rig.main.events.closing.items) == 1 and len(rig.main.events.minimized.items) == 1
    assert len(rig.quick.events.closing.items) == 1


def test_start_hidden_hides_main(tmp_path):
    r = Rig(tmp_path).start(hidden=True)
    assert "main.hide" in r.log


def test_start_hidden_without_tray_keeps_window(tmp_path):
    r = Rig(tmp_path, tray=False).start(hidden=True)
    assert "main.hide" not in r.log


def test_hotkey_disabled_in_config_is_not_started(tmp_path):
    r = Rig(tmp_path, config=DesktopConfig(quick_search_hotkey=False)).start()
    assert "hotkey.start" not in r.log


def test_hotkey_locked_shows_main(tmp_path):
    r = Rig(tmp_path, unlocked=False).start()
    r.made["hotkey"].cb()
    assert "main.show" in r.log and "main.restore" in r.log
    assert "quick.show" not in r.log


def test_hotkey_unlocked_shows_quick_centered(rig):
    rig.made["hotkey"].cb()
    assert "quick.show" in rig.log and "quick.center" in rig.log
    assert "main.show" not in rig.log


def test_tray_handlers(rig):
    h = rig.made["tray"].h
    h.on_quick()
    assert "quick.show" in rig.log
    h.on_open()
    assert "main.show" in rig.log
    h.on_generate()
    assert "api.generate" in rig.log
    assert h.is_locked() is False
    h.on_lock()
    assert h.is_locked() is True


def test_session_lock_locks_and_notifies(rig):
    rig.made["session"].cb()
    assert "api.lock" in rig.log
    assert LOCKED_JS in rig.main.js and "locked" in LOCKED_JS
    assert LOCKED_JS in rig.quick.js
    assert rig.made["tray"].locked_calls == [True]


def test_session_lock_ignored_when_option_off(tmp_path):
    r = Rig(tmp_path, config=DesktopConfig(lock_on_session_lock=False)).start()
    r.made["session"].cb()
    assert "api.lock" not in r.log


def test_minimize_locks_only_with_option(tmp_path):
    r = Rig(tmp_path).start()
    r.main.events.minimized.fire()
    assert "api.lock" not in r.log
    r2 = Rig(tmp_path, config=DesktopConfig(lock_on_minimize=True)).start()
    r2.main.events.minimized.fire()
    assert "api.lock" in r2.log and LOCKED_JS in r2.main.js


def test_closing_with_close_to_tray_hides_and_cancels(rig):
    assert rig.main.events.closing.fire() == [False]
    assert "main.hide" in rig.log


def test_closing_without_close_to_tray_allows(tmp_path):
    r = Rig(tmp_path, config=DesktopConfig(close_to_tray=False)).start()
    assert r.main.events.closing.fire() == [None]
    assert "main.hide" not in r.log


def test_closing_without_tray_allows(tmp_path):
    r = Rig(tmp_path, tray=False).start()
    assert r.main.events.closing.fire() == [None]


def test_quick_closing_hides_and_cancels(rig):
    assert rig.quick.events.closing.fire() == [False]
    assert "quick.hide" in rig.log


def test_quit_order_and_idempotent(rig):
    rig.log.clear()
    rig.ctl.quit()
    assert rig.log == ["hotkey.stop", "session.stop", "api.shutdown", "tray.stop", "quick.destroy", "main.destroy"]
    rig.ctl.quit()
    assert len(rig.log) == 6
    # depois de sair, fechar não é mais cancelado
    assert rig.main.events.closing.fire() == [None]
    assert rig.quick.events.closing.fire() == [None]


def test_quit_continues_when_a_step_fails(rig):
    def boom():
        raise RuntimeError("x")

    rig.api.shutdown = boom
    rig.log.clear()
    rig.ctl.quit()
    assert "tray.stop" in rig.log and "main.destroy" in rig.log


def test_toggle_autostart_calls_autostart_and_saves(rig):
    rig.made["tray"].h.on_toggle_autostart()
    assert "autostart.enable" in rig.log and rig.autostart.on
    assert rig.ctl.config.start_with_windows is True
    assert load_config(rig.config_path).start_with_windows is True
    assert rig.made["tray"].h.is_autostart() is True
    rig.made["tray"].h.on_toggle_autostart()
    assert "autostart.disable" in rig.log and not rig.autostart.on


def test_start_mirrors_registry_into_config(tmp_path):
    r = Rig(tmp_path)
    r.autostart.on = True
    r.start()
    assert r.ctl.config.start_with_windows is True


def test_update_config_toggles_hotkey(rig):
    rig.log.clear()
    rig.ctl.update_config({"quick_search_hotkey": False})
    assert rig.log == ["hotkey.stop"]
    assert rig.ctl.hotkey_available is True  # suportado, só desligado
    rig.ctl.update_config({"quick_search_hotkey": True})
    assert rig.log == ["hotkey.stop", "hotkey.start"]


def test_hotkey_failure_is_reported(tmp_path):
    r = Rig(tmp_path, hotkey_ok=False).start()
    assert r.ctl.hotkey_available is False
    assert r.ctl.info()["hotkey_available"] is False


def test_show_main_with_entry_selects_when_unlocked(rig):
    rig.ctl.show_main("abc")
    assert any("select" in j and '"abc"' in j for j in rig.main.js)


def test_show_main_with_entry_does_not_select_when_locked(tmp_path):
    r = Rig(tmp_path, unlocked=False).start()
    r.ctl.show_main("abc")
    assert r.main.js == []


def test_sync_tray_follows_lock_state(rig):
    rig.ctl.sync_tray()
    rig.api.unlocked = False
    rig.ctl.sync_tray()
    rig.ctl.sync_tray()
    assert rig.made["tray"].locked_calls == [False, True]


# ---------- mixin ----------
class FakeClipboard:
    def __init__(self):
        self.text = ""

    def copy(self, t):
        self.text = t

    def paste(self):
        return self.text


class FakeTimer:
    created = []

    def __init__(self, interval, fn):
        self.interval, self.fn, self.daemon = interval, fn, False
        FakeTimer.created.append(self)

    def start(self):
        pass

    def cancel(self):
        pass


_A = Api  # a Api já inclui o DesktopApiMixin
assert issubclass(Api, DesktopApiMixin)


@pytest.fixture
def mixin_api(tmp_path):
    FakeTimer.created = []
    path = tmp_path / "cofre.vault"
    v = Vault.create(path, PW, STORE, kdf_params=FAST)
    v.add(Entry("Alfa", "u@x.com", "T7#qLm9!vRz2@kWp"))
    clip = FakeClipboard()
    a = _A(path, clipboard=clip, timer_factory=FakeTimer, store=STORE)
    a.clip = clip
    return a


def test_generate_and_copy_locked(mixin_api):
    r = mixin_api.generate_and_copy()
    assert r["ok"] is True and r["clear_in"] == 30
    assert set(r) == {"ok", "clear_in", "strength"}
    assert len(mixin_api.clip.text) == 20
    assert mixin_api.clip.text not in repr(r)
    assert FakeTimer.created[-1].interval == 30


def test_generate_and_copy_unlocked_uses_vault_setting(mixin_api):
    assert mixin_api.unlock(PW)["ok"]
    expected = mixin_api._clear_after
    r = mixin_api.generate_and_copy()
    assert r["ok"] is True and r["clear_in"] == expected
    assert len(mixin_api.clip.text) == 20 and mixin_api.clip.text not in repr(r)
    assert 0 <= r["strength"]["score"] <= 4
    assert mixin_api.status()["unlocked"] is True


def test_generate_and_copy_clears_clipboard_on_timer(mixin_api):
    mixin_api.generate_and_copy()
    FakeTimer.created[-1].fn()
    assert mixin_api.clip.text == ""


def test_generate_and_copy_clipboard_failure(mixin_api):
    def bad(_):
        raise RuntimeError("x")

    mixin_api._clipboard.copy = bad
    r = mixin_api.generate_and_copy()
    assert r["ok"] is False and r["error"] == "clipboard_failed"


def test_get_desktop_config_without_controller(mixin_api):
    r = mixin_api.get_desktop_config()
    assert r["ok"] is True
    assert r["config"] == DesktopConfig().to_dict()
    assert r["platform"] == ("windows" if WIN else "other")
    assert r["tray_available"] is False and r["hotkey_available"] is False


@pytest.mark.parametrize(
    "bad", [None, "x", [], {"close_to_tray": "sim"}, {"close_to_tray": 1}, {"nova": True}]
)
def test_save_desktop_config_validates(mixin_api, bad):
    r = mixin_api.save_desktop_config(bad)
    assert r["ok"] is False and r["error"] == "invalid_config" and r["message"]
    assert not config_path_for(mixin_api._path).exists()


def test_save_desktop_config_without_controller_persists(mixin_api):
    r = mixin_api.save_desktop_config({"lock_on_minimize": True})
    assert r == {"ok": True, "config": {**DesktopConfig().to_dict(), "lock_on_minimize": True}}
    assert load_config(config_path_for(mixin_api._path)).lock_on_minimize is True
    assert mixin_api.get_desktop_config()["config"]["lock_on_minimize"] is True


def test_save_desktop_config_applies_via_controller(mixin_api, tmp_path):
    r = Rig(tmp_path).start()
    mixin_api._attach_desktop(r.ctl)
    out = mixin_api.save_desktop_config({"start_with_windows": True, "quick_search_hotkey": False})
    assert out["ok"] is True and out["config"]["start_with_windows"] is True
    assert "autostart.enable" in r.log and "hotkey.stop" in r.log
    assert load_config(r.config_path).quick_search_hotkey is False
    got = mixin_api.get_desktop_config()
    assert got["config"] == out["config"] and got["tray_available"] is True and got["hotkey_available"] is True
    assert mixin_api.status()["unlocked"] is False  # não exigiu cofre aberto


def test_quick_methods_without_controller(mixin_api):
    assert mixin_api.quick_hide() == {"ok": True}
    assert mixin_api.quick_open_main() == {"ok": True}
    assert mixin_api.quick_open_main("id") == {"ok": True}


def test_quick_methods_with_controller(mixin_api, tmp_path):
    r = Rig(tmp_path).start()
    mixin_api._attach_desktop(r.ctl)
    assert mixin_api.quick_hide() == {"ok": True}
    assert "quick.hide" in r.log
    assert mixin_api.quick_open_main() == {"ok": True}
    assert "main.show" in r.log
    mixin_api.quick_open_main(123)  # tipo inválido: só abre
    assert r.main.js == []


# ---------- módulos nulos / fábricas fora do Windows ----------
def test_null_implementations():
    assert NullTray().available is False
    h = NullHotkey()
    assert h.available is False and h.supported is False and h.start() is False
    NullSessionWatcher().start()
    a = NullAutostart()
    assert a.is_enabled() is False
    a.enable()
    a.disable()


@pytest.mark.skipif(WIN, reason="fora do Windows")
def test_factories_are_null_off_windows():
    assert isinstance(tray_mod.create_tray(None), NullTray)
    assert isinstance(hotkey_mod.create_hotkey(lambda: None), NullHotkey)
    assert isinstance(session_mod.create_session_watcher(lambda: None), NullSessionWatcher)
    assert isinstance(autostart_mod.create_autostart(), NullAutostart)
    assert session_mod.is_session_locked() is False


def test_autostart_command_is_quoted(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\OwLock\OwLock.exe")
    assert autostart_mod.build_command() == '"C:\\Program Files\\OwLock\\OwLock.exe" --tray'
    assert autostart_mod.build_command(tmp_path / "c.vault").endswith(f'--tray --vault "{tmp_path / "c.vault"}"')
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    cmd = autostart_mod.build_command()
    assert cmd.startswith('"') and cmd.endswith("-m owlock --tray")


def test_locked_variant_grays_green_led():
    pytest.importorskip("PIL")  # Pillow vem com o pystray, que só é instalado no Windows
    from PIL import Image

    img = Image.new("RGBA", (2, 1))
    img.putpixel((0, 0), (20, 220, 150, 255))
    img.putpixel((1, 0), (200, 200, 205, 255))
    out = tray_mod.locked_variant(img)
    r, g, b, _ = out.getpixel((0, 0))
    assert abs(r - g) < 3 and abs(g - b) < 3
    assert out.getpixel((1, 0)) == (200, 200, 205, 255)


def test_session_watcher_fires_only_on_transition():
    states = iter([False, False, True, True, False, True])
    fired = threading.Event()
    calls = []

    def probe():
        try:
            return next(states)
        except StopIteration:
            return False

    def cb():
        calls.append(1)
        if len(calls) == 2:
            fired.set()

    w = session_mod.PollingSessionWatcher(cb, probe=probe, interval=0.01)
    w.start()
    assert fired.wait(3)
    w.stop()
    assert len(calls) == 2  # F,F,T(1),T,F,T(2)


def test_session_watcher_probe_failure_counts_as_locked():
    def probe():
        raise OSError

    assert session_mod.PollingSessionWatcher(lambda: None, probe=probe)._safe_probe() is True


# ---------- Windows real ----------
@only_windows
def test_windows_autostart_real_registry():
    import winreg

    key = r"Software\OwLockTest"
    a = autostart_mod.WindowsAutostart('"C:\\x\\OwLock.exe" --tray', key=key, value_name="OwLock")
    try:
        a.disable()  # ignora "não existe"
        assert a.is_enabled() is False
        a.enable()
        assert a.is_enabled() is True
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            assert winreg.QueryValueEx(k, "OwLock")[0] == '"C:\\x\\OwLock.exe" --tray'
        a.disable()
        assert a.is_enabled() is False
        a.disable()
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except OSError:
            pass


@only_windows
def test_windows_hotkey_register_and_stop():
    hk = hotkey_mod.WindowsHotkey(
        lambda: None, modifiers=hotkey_mod.MOD_CONTROL | hotkey_mod.MOD_ALT | hotkey_mod.MOD_SHIFT, vk=0x7B  # F12
    )
    if not hk.start():
        hk.stop()
        pytest.skip("RegisterHotKey indisponível nesta sessão (executor sem área de trabalho interativa)")
    try:
        assert hk.available is True
        # o mesmo atalho não pode ser registrado duas vezes
        hk2 = hotkey_mod.WindowsHotkey(
            lambda: None, modifiers=hotkey_mod.MOD_CONTROL | hotkey_mod.MOD_ALT | hotkey_mod.MOD_SHIFT, vk=0x7B
        )
        assert hk2.start() is False
        hk2.stop()
    finally:
        hk.stop()
    assert hk.available is False
    # depois do stop o atalho volta a ficar livre
    hk3 = hotkey_mod.WindowsHotkey(
        lambda: None, modifiers=hotkey_mod.MOD_CONTROL | hotkey_mod.MOD_ALT | hotkey_mod.MOD_SHIFT, vk=0x7B
    )
    try:
        assert hk3.start() is True
    finally:
        hk3.stop()


@only_windows
def test_windows_session_probe_returns_bool():
    # o executor do CI pode rodar sem área de trabalho interativa, então só conferimos que a sondagem
    # chama o Windows de verdade, libera o handle e devolve um booleano sem erro
    assert isinstance(session_mod.is_session_locked(), bool)
