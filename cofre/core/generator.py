"""Gerador de senhas fortes."""
from __future__ import annotations

import secrets
import string

SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/"
MAX_LENGTH = 128


def generate_password(
    length: int = 20,
    upper: bool = True,
    lower: bool = True,
    digits: bool = True,
    symbols: bool = True,
) -> str:
    """Gera uma senha aleatória com ao menos um caractere de cada classe ativa."""
    classes = [
        chars
        for enabled, chars in (
            (upper, string.ascii_uppercase),
            (lower, string.ascii_lowercase),
            (digits, string.digits),
            (symbols, SYMBOLS),
        )
        if enabled
    ]
    if not classes:
        raise ValueError("Selecione ao menos um tipo de caractere.")
    if length < len(classes):
        raise ValueError(
            f"O tamanho deve ser ao menos {len(classes)} para os tipos escolhidos."
        )
    if length > MAX_LENGTH:
        raise ValueError(f"O tamanho máximo é {MAX_LENGTH}.")
    pool = "".join(classes)
    chars = [secrets.choice(c) for c in classes]
    chars += [secrets.choice(pool) for _ in range(length - len(classes))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
