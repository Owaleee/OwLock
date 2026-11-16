"""Núcleo do cofre (sem dependência de interface)."""
from .errors import CofreError, VaultCorruptedError, VaultExistsError, WrongPasswordError
from .generator import generate_password
from .models import Entry
from .vault import DEFAULT_VAULT_PATH, MIN_MASTER_PASSWORD_LENGTH, Vault

__all__ = [
    "CofreError",
    "DEFAULT_VAULT_PATH",
    "Entry",
    "MIN_MASTER_PASSWORD_LENGTH",
    "Vault",
    "VaultCorruptedError",
    "VaultExistsError",
    "WrongPasswordError",
    "generate_password",
]
