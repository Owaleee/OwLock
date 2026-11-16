import pytest
from cryptography.exceptions import InvalidTag

from cofre.core import crypto

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}


def test_derive_key_deterministic_and_32_bytes():
    salt = b"s" * 16
    k1 = crypto.derive_key("senha", salt, **FAST)
    assert len(k1) == 32
    assert k1 == crypto.derive_key("senha", salt, **FAST)
    assert k1 != crypto.derive_key("outra", salt, **FAST)
    assert k1 != crypto.derive_key("senha", b"t" * 16, **FAST)


def test_encrypt_decrypt_roundtrip_and_fresh_nonce():
    key = b"k" * 32
    n1, c1 = crypto.encrypt(key, b"segredo", b"aad")
    n2, _ = crypto.encrypt(key, b"segredo", b"aad")
    assert len(n1) == 12 and n1 != n2
    assert crypto.decrypt(key, n1, c1, b"aad") == b"segredo"


def test_decrypt_fails_with_wrong_aad_key_or_tamper():
    key = b"k" * 32
    n, c = crypto.encrypt(key, b"segredo", b"aad")
    with pytest.raises(InvalidTag):
        crypto.decrypt(key, n, c, b"outro")
    with pytest.raises(InvalidTag):
        crypto.decrypt(b"x" * 32, n, c, b"aad")
    with pytest.raises(InvalidTag):
        crypto.decrypt(key, n, bytes([c[0] ^ 1]) + c[1:], b"aad")


def test_new_salt_and_defaults():
    assert len(crypto.new_salt()) == 16
    assert crypto.new_salt() != crypto.new_salt()
    assert crypto.DEFAULT_KDF_PARAMS == {
        "time_cost": 3, "memory_cost": 65536, "parallelism": 4,
    }
