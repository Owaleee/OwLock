import base64
import hashlib
import re

import pytest

from owlock.core import InvalidSecretKeyError
from owlock.core.secret_key import (
    format_secret_key, generate_secret_key, parse_secret_key, secret_key_id,
)

FIXED = bytes(range(16)) + b"\x40"
FIXED_TEXT = "OW2-AAAQE-AYEAU-DAOCA-JBIFQ-YDIOB5-5O"
PATTERN = re.compile(r"^OW2(-[A-Z2-7]{5}){4}-[A-Z2-7]{6}-[A-Z2-7]{2}$")


def test_format_pattern_and_fixed_vector():
    assert PATTERN.match(format_secret_key(generate_secret_key()))
    assert format_secret_key(FIXED) == FIXED_TEXT


def test_check_digits_are_sha256_prefix_in_base32():
    text = format_secret_key(FIXED)
    body = "".join(text.split("-")[1:6])
    assert len(body) == 26
    expected = base64.b32encode(hashlib.sha256(body.encode()).digest())[:2].decode()
    assert text.split("-")[-1] == expected


def test_roundtrip_and_130_bits():
    for _ in range(50):
        raw = generate_secret_key()
        assert len(raw) == 17 and raw[-1] & 0x3F == 0
        assert parse_secret_key(format_secret_key(raw)) == raw


def test_lenient_input():
    assert parse_secret_key(FIXED_TEXT.lower()) == FIXED
    assert parse_secret_key(FIXED_TEXT.replace("-", " ")) == FIXED
    assert parse_secret_key(FIXED_TEXT.replace("-", "")) == FIXED
    assert parse_secret_key("  " + FIXED_TEXT.replace("OW2-", "") + "\n") == FIXED
    assert parse_secret_key(FIXED_TEXT.replace("-", "").lower()) == FIXED


def test_body_starting_with_prefix_chars_is_not_mistaken_for_prefix():
    # corpo que começa com "OW2" (O=14, W=22, 2=26 -> 01110 10110 11010): o tamanho decide se há prefixo
    raw = bytes([0b01110101, 0b10110100]) + bytes(15)
    text = format_secret_key(raw)
    assert text.split("-")[1].startswith("OW2")
    assert parse_secret_key(text) == raw
    assert parse_secret_key(text.replace("OW2-", "", 1)) == raw


def test_look_alike_substitutions():
    mutated = FIXED_TEXT.replace("O", "0", 1).replace("B", "8", 1)
    assert mutated != FIXED_TEXT
    assert parse_secret_key(mutated) == FIXED
    raw = bytes([0x40]) + bytes(16)  # corpo começa com "I" (índice 8)
    text = format_secret_key(raw)
    assert "I" in text.split("-")[1]
    assert parse_secret_key(text.replace("I", "1")) == raw


def test_wrong_check_digit_and_wrong_length():
    parts = FIXED_TEXT.split("-")
    flipped = "A" if parts[-1][0] != "A" else "B"
    bad = "-".join(parts[:-1] + [flipped + parts[-1][1]])
    for text in (bad, FIXED_TEXT[:-1], FIXED_TEXT + "A", "", "   ", "OW2", "OW2-AAAAA",
                 FIXED_TEXT.replace("A", "9", 1), FIXED_TEXT.replace("A", "!", 1)):
        with pytest.raises(InvalidSecretKeyError) as exc:
            parse_secret_key(text)
        assert str(exc.value) == "Chave Secreta inválida: confira os caracteres."
    with pytest.raises(InvalidSecretKeyError):
        parse_secret_key(None)  # type: ignore[arg-type]


def test_any_single_char_change_is_detected():
    body = FIXED_TEXT.split("-")
    compact = "".join(body[1:])
    undetected = 0
    for i in range(len(compact)):
        ch = "A" if compact[i] != "A" else "C"
        text = compact[:i] + ch + compact[i + 1:]
        try:
            parse_secret_key(text)
            undetected += 1
        except InvalidSecretKeyError:
            pass
    # 10 bits de verificação: uma troca isolada quase sempre é pega (colisão ~ 1/1024)
    assert undetected <= 1


def test_swap_of_adjacent_chars_detected():
    parts = FIXED_TEXT.split("-")
    compact = "".join(parts[1:])
    i = next(i for i in range(26) if compact[i] != compact[i + 1])
    swapped = compact[:i] + compact[i + 1] + compact[i] + compact[i + 2:]
    with pytest.raises(InvalidSecretKeyError):
        parse_secret_key(swapped)


def test_thousand_keys_are_unique():
    keys = {format_secret_key(generate_secret_key()) for _ in range(1000)}
    assert len(keys) == 1000


def test_format_rejects_bad_bytes():
    for bad in (b"", b"x" * 16, b"x" * 17, b"\x00" * 18):
        with pytest.raises(InvalidSecretKeyError):
            format_secret_key(bad)


def test_key_id_depends_on_key_and_vault_and_is_16_hex():
    vid = bytes(range(16, 32))
    kid = secret_key_id(FIXED, vid)
    assert kid == "47224e19535f3e80" and re.match(r"^[0-9a-f]{16}$", kid)
    other = bytes(range(1, 17)) + b"\x40"
    assert secret_key_id(other, vid) != kid
    assert secret_key_id(FIXED, bytes(16)) != kid
