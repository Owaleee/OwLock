"""Núcleo do cofre (sem dependência de interface)."""
from .catalog import Catalog, Service, normalize
from .errors import (
    InvalidSecretKeyError,
    MigrationError,
    OwLockError,
    SecretKeyRequiredError,
    VaultCorruptedError,
    VaultExistsError,
    WrongPasswordError,
    WrongSecretKeyError,
)
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
from .keystore import FileStore, KeyringStore, MemoryStore, SecretKeyStore, default_store
from .secret_key import format_secret_key, generate_secret_key, parse_secret_key, secret_key_id
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
    "FileStore",
    "InvalidSecretKeyError",
    "KeyringStore",
    "MemoryStore",
    "MigrationError",
    "SecretKeyRequiredError",
    "SecretKeyStore",
    "WrongSecretKeyError",
    "default_store",
    "format_secret_key",
    "generate_secret_key",
    "parse_secret_key",
    "secret_key_id",
    "VaultCorruptedError",
    "VaultExistsError",
    "WrongPasswordError",
    "generate_password",
]
