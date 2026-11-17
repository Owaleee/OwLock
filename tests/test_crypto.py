import pytest
from cryptography.exceptions import InvalidTag

from owlock.core import crypto

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


# ---- v2: KEK ----
import hashlib  # noqa: E402
import hmac as _hmac  # noqa: E402

KEK_SALT = bytes(range(16))
KEK_SECRET = bytes(range(16)) + b"\x40"
KEK_VAULT_ID = bytes(range(16, 32))
KEK_PW = "senha-fixa-123"


def _kek(password=KEK_PW, salt=KEK_SALT, secret=KEK_SECRET, vault_id=KEK_VAULT_ID, **params):
    return crypto.derive_kek(password, salt, secret, vault_id, **(params or FAST))


def _ref_hkdf(ikm, salt, info, length=32):
    """HKDF-SHA256 (RFC 5869) escrito à mão, independente da biblioteca."""
    prk = _hmac.new(salt, ikm, hashlib.sha256).digest()
    out, block, i = b"", b"", 1
    while len(out) < length:
        block = _hmac.new(prk, block + info + bytes([i]), hashlib.sha256).digest()
        out += block
        i += 1
    return out[:length]


def test_hkdf_matches_reference_and_fixed_vector():
    assert crypto.hkdf(b"ikm", b"salt", b"info") == _ref_hkdf(b"ikm", b"salt", b"info")
    assert crypto.hkdf(b"ikm", b"salt", b"info").hex() == (
        "fe8f9615d2374c0d17f77d1aeaf408c2e75fe0466073d0def23c733e2f862dfd")


def test_kek_fixed_vector_locks_the_algorithm():
    assert _kek().hex() == "66b523af58baa9ad8400b43c3254d50f07c729a6385e57e07678868fcfc6f2dd"


def test_kek_matches_documented_construction():
    pw = crypto.derive_key(KEK_PW, KEK_SALT, **FAST)
    sk = _ref_hkdf(KEK_SECRET, KEK_VAULT_ID, b"owlock-v2 secret key")
    assert _kek() == _ref_hkdf(pw + sk, KEK_SALT, b"owlock-v2 kek")


def test_kek_depends_on_password_and_secret_key():
    base = _kek()
    assert len(base) == 32
    assert _kek(password="outra-senha-123") != base
    assert _kek(secret=bytes(range(1, 17)) + b"\x40") != base
    assert _kek(salt=bytes(range(1, 17))) != base
    assert _kek(vault_id=bytes(16)) != base
    assert _kek(time_cost=2, memory_cost=8192, parallelism=1) != base
