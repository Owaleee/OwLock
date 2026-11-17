"""Chave Secreta: 130 bits aleatórios, exibidos em base32 com dígito de verificação.

Formato de exibição: ``OW2-XXXXX-XXXXX-XXXXX-XXXXX-XXXXXX-XX`` (corpo de 26
caracteres em grupos 5-5-5-5-6 e 2 caracteres de verificação no fim).

Representação em bytes: 17 bytes em que só os 130 primeiros bits são usados
(os 6 bits finais são sempre zero). Assim a ida e volta texto <-> bytes é exata.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from .errors import InvalidSecretKeyError

PREFIX = "OW2"
BODY_LENGTH = 26  # 26 * 5 = 130 bits
CHECK_LENGTH = 2
SECRET_BYTES_LENGTH = 17  # 130 bits cabem em 17 bytes (6 bits finais = 0)
_GROUPS = (5, 5, 5, 5, 6)
_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
_SUBSTITUTIONS = str.maketrans({"0": "O", "1": "I", "8": "B"})
_INVALID_MESSAGE = "Chave Secreta inválida: confira os caracteres."


def _check_digits(body: str) -> str:
    digest = hashlib.sha256(body.encode("ascii")).digest()
    return base64.b32encode(digest)[:CHECK_LENGTH].decode("ascii")


def _body_of(secret_bytes: bytes) -> str:
    return base64.b32encode(secret_bytes).decode("ascii")[:BODY_LENGTH]


def generate_secret_key() -> bytes:
    """Gera uma Chave Secreta nova (17 bytes; só 130 bits são aleatórios)."""
    raw = bytearray(secrets.token_bytes(SECRET_BYTES_LENGTH))
    raw[-1] &= 0xC0  # mantém só os 2 primeiros bits do último byte (130 bits no total)
    return bytes(raw)


def _validate_secret_bytes(secret_bytes: bytes) -> None:
    if (
        not isinstance(secret_bytes, (bytes, bytearray))
        or len(secret_bytes) != SECRET_BYTES_LENGTH
        or secret_bytes[-1] & 0x3F
    ):
        raise InvalidSecretKeyError(_INVALID_MESSAGE)


def format_secret_key(secret_bytes: bytes) -> str:
    """Formata os bytes da Chave Secreta para exibição."""
    _validate_secret_bytes(secret_bytes)
    body = _body_of(bytes(secret_bytes))
    groups: list[str] = []
    pos = 0
    for size in _GROUPS:
        groups.append(body[pos:pos + size])
        pos += size
    return "-".join([PREFIX, *groups, _check_digits(body)])


def parse_secret_key(text: str) -> bytes:
    """Lê a Chave Secreta digitada (tolerante) e devolve os 17 bytes.

    Aceita minúsculas, espaços e hífens, prefixo ``OW2`` opcional e troca
    0->O, 1->I, 8->B. Levanta InvalidSecretKeyError se algo não confere.
    """
    if not isinstance(text, str) or len(text) > 200:
        raise InvalidSecretKeyError(_INVALID_MESSAGE)
    cleaned = "".join(ch for ch in text if not ch.isspace() and ch != "-")
    cleaned = cleaned.upper().translate(_SUBSTITUTIONS)
    full = BODY_LENGTH + CHECK_LENGTH
    # O corpo pode começar com "OW2" por acaso: o tamanho decide se há prefixo.
    if len(cleaned) == full + len(PREFIX) and cleaned.startswith(PREFIX):
        cleaned = cleaned[len(PREFIX):]
    if len(cleaned) != full or not all(ch in _ALPHABET for ch in cleaned):
        raise InvalidSecretKeyError(_INVALID_MESSAGE)
    body, check = cleaned[:BODY_LENGTH], cleaned[BODY_LENGTH:]
    if not hmac.compare_digest(check.encode("ascii"), _check_digits(body).encode("ascii")):
        raise InvalidSecretKeyError(_INVALID_MESSAGE)
    # 26 caracteres + 2 de enchimento "A" = 28 caracteres = 17 bytes (6 bits finais zero)
    padded = body + "AA" + "===="
    return base64.b32decode(padded)


def secret_key_id(secret_bytes: bytes, vault_id: bytes) -> str:
    """Identificador (16 hex) da Chave Secreta para este cofre; vault_id em bytes (16)."""
    mac = hmac.new(bytes(secret_bytes), b"owlock-v2-key-id|" + vault_id, hashlib.sha256)
    return mac.digest()[:8].hex()
