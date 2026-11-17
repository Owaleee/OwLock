import json
import os

import pytest

from owlock.app import config as cfg
from owlock.app.config import DesktopConfig, config_path_for, load_config, save_config, validate_config_data
from owlock.core.vault import DEFAULT_VAULT_PATH


def test_defaults():
    c = DesktopConfig()
    assert c.to_dict() == {
        "close_to_tray": True,
        "lock_on_minimize": False,
        "lock_on_session_lock": True,
        "quick_search_hotkey": True,
        "start_with_windows": False,
    }


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "nada.json") == DesktopConfig()


@pytest.mark.parametrize("content", ["", "{", "[]", "null", "42", '"x"'])
def test_invalid_file_gives_defaults(tmp_path, content):
    p = tmp_path / "config.json"
    p.write_text(content, encoding="utf-8")
    assert load_config(p) == DesktopConfig()


def test_binary_garbage_gives_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_bytes(b"\xff\xfe\x00\x01")
    assert load_config(p) == DesktopConfig()


def test_wrong_types_fall_back_per_field(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"close_to_tray": "sim", "lock_on_minimize": True, "quick_search_hotkey": 1, "extra": True}))
    c = load_config(p)
    assert c.close_to_tray is True  # padrão (valor inválido ignorado)
    assert c.lock_on_minimize is True
    assert c.quick_search_hotkey is True  # 1 não é bool


def test_roundtrip_and_no_temp_left(tmp_path):
    p = tmp_path / "sub" / "config.json"
    c = DesktopConfig(close_to_tray=False, lock_on_minimize=True, start_with_windows=True)
    save_config(p, c)
    assert load_config(p) == c
    assert [x.name for x in p.parent.iterdir()] == ["config.json"]


def test_only_known_keys_are_written(tmp_path):
    p = tmp_path / "config.json"
    save_config(p, DesktopConfig())
    assert set(json.loads(p.read_text())) == set(DesktopConfig().to_dict())


def test_save_is_atomic_when_write_fails(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    save_config(p, DesktopConfig(lock_on_minimize=True))

    def boom(src, dst):
        raise OSError("falha")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        save_config(p, DesktopConfig(lock_on_minimize=False))
    monkeypatch.undo()
    assert load_config(p).lock_on_minimize is True  # arquivo antigo intacto
    assert [x.name for x in tmp_path.iterdir()] == ["config.json"]  # temporário removido


def test_config_path_default_and_custom(tmp_path):
    assert config_path_for(DEFAULT_VAULT_PATH) == DEFAULT_VAULT_PATH.parent / "config.json"
    assert config_path_for(tmp_path / "meu.vault") == tmp_path / "owlock-config.json"


def test_validate_config_data():
    assert validate_config_data({"close_to_tray": False}) == {"close_to_tray": False}
    assert validate_config_data({}) == {}
    for bad in (None, [], "x", {"close_to_tray": "sim"}, {"close_to_tray": 1}, {"desconhecida": True}):
        assert validate_config_data(bad) is None


def test_module_has_no_vault_fields():
    names = {f for f in DesktopConfig.__dataclass_fields__}
    assert not any("service" in n or "password" in n or "entry" in n for n in names)
    assert cfg.CONFIG_NAME == "config.json"
