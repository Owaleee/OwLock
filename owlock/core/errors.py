"""Erros do núcleo do cofre."""


class OwLockError(Exception):
    """Erro base do cofre."""


class WrongPasswordError(OwLockError):
    """Senha mestra incorreta (ou arquivo alterado)."""


class VaultCorruptedError(OwLockError):
    """Arquivo do cofre inválido, corrompido ou de versão desconhecida."""


class VaultExistsError(OwLockError):
    """Já existe um cofre no caminho informado."""
