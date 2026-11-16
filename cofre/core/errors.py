"""Erros do núcleo do cofre."""


class CofreError(Exception):
    """Erro base do cofre."""


class WrongPasswordError(CofreError):
    """Senha mestra incorreta (ou arquivo alterado)."""


class VaultCorruptedError(CofreError):
    """Arquivo do cofre inválido, corrompido ou de versão desconhecida."""


class VaultExistsError(CofreError):
    """Já existe um cofre no caminho informado."""
