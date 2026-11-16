import pytest

from owlock.core import Entry


def test_defaults_and_roundtrip():
    e = Entry(service="Google", username="a@b.c", password="x", has_2fa=True,
              twofa_app="Authy", notes="n")
    assert len(e.id) == 32
    assert e.created_at.endswith("+00:00")
    assert Entry.from_dict(e.to_dict()) == e


def test_from_dict_ignores_unknown_keys():
    e = Entry.from_dict({"service": "X", "id": "1", "futuro": 42})
    assert e.service == "X" and e.id == "1"
    assert not hasattr(e, "futuro")


@pytest.mark.parametrize("d", [{"id": "1"}, {"service": "X"}])
def test_from_dict_requires_service_and_id(d):
    with pytest.raises(ValueError):
        Entry.from_dict(d)
