"""Derivação de chave (Argon2id) e cifra autenticada (AES-256-GCM)."""
from __future__ import annotations

import os

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_LENGTH = 32
SALT_LENGTH = 16
NONCE_LENGTH = 12
DEFAULT_KDF_PARAMS: dict[str, int] = {
    "time_cost": 3,
    "memory_cost": 65536,
    "parallelism": 4,
}


def new_salt() -> bytes:
    """Gera um salt aleatório de 16 bytes."""
    return os.urandom(SALT_LENGTH)


def derive_key(
    password: str, salt: bytes, time_cost: int, memory_cost: int, parallelism: int
) -> bytes:
    """Deriva uma chave de 32 bytes da senha com Argon2id."""
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=KEY_LENGTH,
        type=Type.ID,
    )


def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = KEY_LENGTH) -> bytes:
    """HKDF-SHA256."""
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def derive_kek(
    password: str,
    salt: bytes,
    secret_bytes: bytes,
    vault_id: bytes,
    time_cost: int,
    memory_cost: int,
    parallelism: int,
) -> bytes:
    """Deriva a KEK do cofre v2 a partir da senha mestra E da Chave Secreta.

    pw  = Argon2id(senha, salt, ...)
    sk  = HKDF(ikm=secret_bytes, salt=vault_id, info="owlock-v2 secret key")
    KEK = HKDF(ikm=pw || sk,     salt=salt,     info="owlock-v2 kek")
    `vault_id` são os 16 bytes do identificador do cofre.
    """
    pw = derive_key(password, salt, time_cost, memory_cost, parallelism)
    sk = hkdf(bytes(secret_bytes), vault_id, b"owlock-v2 secret key")
    return hkdf(pw + sk, salt, b"owlock-v2 kek")


def encrypt(key: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
    """Cifra com AES-256-GCM; devolve (nonce, ciphertext)."""
    nonce = os.urandom(NONCE_LENGTH)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Decifra; levanta cryptography.exceptions.InvalidTag se falhar."""
    return AESGCM(key).decrypt(nonce, ciphertext, aad)
