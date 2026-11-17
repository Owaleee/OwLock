"""Uma única instância por cofre (com um kernel32 falso, roda em qualquer sistema)."""
import threading
from pathlib import Path

from owlock.app.desktop.single import ERROR_ALREADY_EXISTS, SingleInstance, instance_key


class FakeKernel:
    """Simula mutex e evento nomeados compartilhados entre "processos" (instâncias)."""

    def __init__(self):
        self.objects = {}
        self.last = 0
        self.lock = threading.Lock()

    def get_last_error(self):
        return self.last

    def CreateMutexW(self, _attrs, _owner, name):
        self.last = ERROR_ALREADY_EXISTS if name in self.objects else 0
        self.objects.setdefault(name, "mutex")
        return name

    def CreateEventW(self, _attrs, _manual, _state, name):
        self.objects[name] = threading.Event()
        return name

    def OpenEventW(self, _access, _inherit, name):
        return name if isinstance(self.objects.get(name), threading.Event) else None

    def SetEvent(self, name):
        self.objects[name].set()
        return 1

    def WaitForSingleObject(self, name, _timeout):
        event = self.objects[name]
        event.wait()
        event.clear()  # evento de reset automático
        return 0

    def CloseHandle(self, _h):
        return 1


def test_key_is_stable_and_hides_path(tmp_path):
    a = instance_key(tmp_path / "Cofre.vault")
    assert a == instance_key(tmp_path / "cofre.vault")
    assert a != instance_key(tmp_path / "outro.vault")
    assert a.startswith("OwLock-") and "Cofre" not in a


def test_second_instance_signals_first():
    kernel = FakeKernel()
    first = SingleInstance("OwLock-x", kernel=kernel, enabled=True)
    assert first.acquire()
    shown = threading.Event()
    first.listen(shown.set)
    second = SingleInstance("OwLock-x", kernel=kernel, enabled=True)
    assert not second.acquire()
    assert second.notify_existing()
    assert shown.wait(2)
    other = SingleInstance("OwLock-y", kernel=kernel, enabled=True)
    assert other.acquire()  # outro cofre: pode abrir junto


def test_disabled_outside_windows_and_on_errors():
    off = SingleInstance("OwLock-z", enabled=False)
    assert off.acquire() and not off.notify_existing() and off.listen(lambda: None) is None

    class Broken:
        def __getattr__(self, name):
            raise OSError("sem kernel32")

    broken = SingleInstance("OwLock-z", kernel=Broken(), enabled=True)
    assert broken.acquire()  # sem proteção, abre normalmente
    assert not broken.notify_existing()
