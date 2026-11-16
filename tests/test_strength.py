import pytest

from owlock.core import generate_password
from owlock.core.strength import LABELS, password_strength


def score(p):
    return password_strength(p)["score"]


def test_empty_and_common():
    assert score("") == 0
    assert score("123456") == 0


def test_weak_examples():
    assert score("senha123") <= 1
    assert score("discord2021") <= 2


def test_medium_and_strong_examples():
    assert score("Nf!93kdPq") in (2, 3)
    assert score("Gx4!nP8s#Qd1") in (3, 4)
    assert score("T7#qLm9!vRz2@kWp") == 4


def test_generated_password_is_strong():
    for _ in range(200):
        assert score(generate_password(20)) == 4


def test_penalties():
    assert score("aaaaaaaaaaaaaaaa") <= 1
    assert score("abcdefghijkl") <= 1
    assert score("qwertyuiop") <= 1


def test_label_matches_score():
    for p in ("", "abc", "Nf!93kdPq", "T7#qLm9!vRz2@kWp"):
        r = password_strength(p)
        assert r["label"] == LABELS[r["score"]]


def test_deterministic():
    assert password_strength("Nf!93kdPq") == password_strength("Nf!93kdPq")


@pytest.mark.parametrize(
    "p",
    ["çãõ-ñandú", "密码密码密码密码密码", "😀😀😀😀😀😀😀😀", "\x00\x01", "a" * 5000, "é" * 3, "\ud800"],
)
def test_never_raises_on_unicode(p):
    r = password_strength(p)
    assert 0 <= r["score"] <= 4
