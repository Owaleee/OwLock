import pytest

from cofre.core import generate_password
from cofre.core.generator import SYMBOLS
import string


def test_length_and_all_classes():
    for n in (4, 8, 20, 128):
        p = generate_password(n)
        assert len(p) == n
        assert any(c in string.ascii_uppercase for c in p)
        assert any(c in string.ascii_lowercase for c in p)
        assert any(c in string.digits for c in p)
        assert any(c in SYMBOLS for c in p)


def test_only_requested_classes():
    p = generate_password(50, upper=False, lower=False, digits=True, symbols=False)
    assert p.isdigit() and len(p) == 50
    p = generate_password(50, upper=True, lower=True, digits=False, symbols=False)
    assert p.isalpha()


def test_errors():
    with pytest.raises(ValueError):
        generate_password(10, False, False, False, False)
    with pytest.raises(ValueError):
        generate_password(3)
    with pytest.raises(ValueError):
        generate_password(129)


def test_no_repeats_in_200():
    assert len({generate_password() for _ in range(200)}) == 200
