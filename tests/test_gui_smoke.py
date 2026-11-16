"""Teste de fumaça da interface: abre o cofre e lista as entradas."""

import os

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("sem DISPLAY", allow_module_level=True)

from cofre.core.models import Entry
from cofre.core.vault import Vault
from cofre.gui.app import CofreApp, MainFrame, UnlockFrame

KDF = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}


def test_unlock_and_list(tmp_path):
    path = tmp_path / "t.vault"
    vault = Vault.create(path, "senha-forte-123", kdf_params=KDF)
    vault.add(Entry(service="GitHub", username="a@b.c", has_2fa=True, twofa_app="Authy"))
    vault.add(Entry(service="amazon"))

    app = CofreApp(vault_path=path)
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
