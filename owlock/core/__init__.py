"""Núcleo do cofre (sem dependência de interface)."""
from .catalog import Catalog, Service, normalize
from .errors import OwLockError, VaultCorruptedError, VaultExistsError, WrongPasswordError
from .generator import generate_password
from .models import (
    AUTO_LOCK_OPTIONS,
    CATEGORY_COLORS,
    CATEGORY_ICONS,
    CLIPBOARD_OPTIONS,
    Category,
    Entry,
    Settings,
)
from .vault import DEFAULT_VAULT_PATH, MIN_MASTER_PASSWORD_LENGTH, Vault

__all__ = [
    "Catalog",
    "Service",
    "normalize",
    "AUTO_LOCK_OPTIONS",
    "CLIPBOARD_OPTIONS",
    "Settings",
    "OwLockError",
    "CATEGORY_COLORS",
    "CATEGORY_ICONS",
    "Category",
    "DEFAULT_VAULT_PATH",
    "Entry",
    "MIN_MASTER_PASSWORD_LENGTH",
    "Vault",
    "VaultCorruptedError",
    "VaultExistsError",
    "WrongPasswordError",
    "generate_password",
]
