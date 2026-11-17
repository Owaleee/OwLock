"""Erros do núcleo do cofre."""


class OwLockError(Exception):
    """Erro base do cofre."""


class WrongPasswordError(OwLockError):
    """Senha mestra incorreta (ou arquivo alterado)."""


class VaultCorruptedError(OwLockError):
    """Arquivo do cofre inválido, corrompido ou de versão desconhecida."""


class VaultExistsError(OwLockError):
    """Já existe um cofre no caminho informado."""


class SecretKeyRequiredError(OwLockError):
    """O cofre é v2 e a Chave Secreta não está neste aparelho nem foi informada."""


class WrongSecretKeyError(OwLockError):
    """A Chave Secreta informada (ou guardada) não é a deste cofre."""


class InvalidSecretKeyError(OwLockError):
    """Texto da Chave Secreta inválido (tamanho, caracteres ou dígito de verificação)."""


class MigrationError(OwLockError):
    """Falha ao migrar um cofre v1 para v2; o arquivo original não foi alterado."""
