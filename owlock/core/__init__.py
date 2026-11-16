"""Núcleo do cofre (sem dependência de interface)."""
from .errors import OwLockError, VaultCorruptedError, VaultExistsError, WrongPasswordError
from .generator import generate_password
from .models import Entry
from .vault import DEFAULT_VAULT_PATH, MIN_MASTER_PASSWORD_LENGTH, Vault

__all__ = [
    "OwLockError",
    "DEFAULT_VAULT_PATH",
    "Entry",
    "MIN_MASTER_PASSWORD_LENGTH",
    "Vault",
    "VaultCorruptedError",
    "VaultExistsError",
    "WrongPasswordError",
    "generate_password",
]
