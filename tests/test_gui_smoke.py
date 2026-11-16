"""Teste de fumaça da interface: abre o cofre e lista as entradas."""

import os

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("sem DISPLAY", allow_module_level=True)

from owlock.core.models import Entry
from owlock.core.vault import Vault
from owlock.gui.app import OwLockApp, MainFrame, UnlockFrame

KDF = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}


def test_unlock_and_list(tmp_path):
    path = tmp_path / "t.vault"
    vault = Vault.create(path, "senha-forte-123", kdf_params=KDF)
    vault.add(Entry(service="GitHub", username="a@b.c", has_2fa=True, twofa_app="Authy"))
    vault.add(Entry(service="amazon"))

    app = OwLockApp(vault_path=path)
    try:
        app.update()
        assert isinstance(app.frame, UnlockFrame)
        app._unlock_sync("senha-forte-123")
        app.update()
        assert isinstance(app.frame, MainFrame)
        assert len(app.frame.list_frame.winfo_children()) == 2
        app.lock()
        assert app.vault is None
        assert isinstance(app.frame, UnlockFrame)
    finally:
        app.destroy()


def _pump(app, dialog, seconds=5.0):
    """Processa eventos até o diálogo fechar ou mostrar erro."""
    import time

    end = time.time() + seconds
    while time.time() < end:
        app.update()
        if not dialog.winfo_exists() or dialog.error_label.cget("text"):
            return
        time.sleep(0.02)


def test_change_master_password(tmp_path):
    from owlock.core.errors import WrongPasswordError
    from owlock.gui.app import ChangePasswordDialog

    path = tmp_path / "t.vault"
    Vault.create(path, "senha-antiga-1", kdf_params=KDF).add(Entry(service="Steam"))

    app = OwLockApp(vault_path=path)
    try:
        app._unlock_sync("senha-antiga-1")
        app.change_master_password()
        dialog = app._dialog
        assert isinstance(dialog, ChangePasswordDialog)

        for field, value in zip(dialog.fields, ("errada-123", "senha-nova-22", "senha-nova-22")):
            field.insert(0, value)
        dialog._submit()
        _pump(app, dialog)
        assert "incorreta" in dialog.error_label.cget("text")

        dialog.error_label.configure(text="")
        for field, value in zip(dialog.fields, ("senha-antiga-1", "senha-nova-22", "senha-nova-22")):
            field.insert(0, value)
        dialog._submit()
        _pump(app, dialog)
        assert app._dialog is None
    finally:
        app.destroy()

    assert Vault.open(path, "senha-nova-22").entries[0].service == "Steam"
    with pytest.raises(WrongPasswordError):
        Vault.open(path, "senha-antiga-1")
