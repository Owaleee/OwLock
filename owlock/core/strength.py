"""Força da senha (0 a 4), heurística simples e determinística."""
from __future__ import annotations

import math
import re
import unicodedata

LABELS = ("Muito fraca", "Fraca", "Razoável", "Boa", "Forte")

_COMMON = {
    "123456", "1234567", "12345678", "123456789", "1234567890", "12345", "1234",
    "password", "senha", "senha123", "qwerty", "qwerty123", "abc123", "admin",
    "admin123", "letmein", "welcome", "iloveyou", "111111", "000000", "123123",
    "654321", "654321", "dragon", "master", "monkey", "football", "futebol",
    "flamengo", "corinthians", "brasil", "mudar123", "minhasenha", "senha1234",
    "pass", "passw0rd", "p@ssw0rd", "1q2w3e4r", "qazwsx", "discord", "steam",
}
_KEYBOARD = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890", "qazwsx", "1q2w3e")
_WORDS = ("password", "senha", "qwerty", "admin", "welcome", "letmein", "login")
_YEAR = re.compile(r"(?:19|20)\d{2}")


def _classes(password: str) -> int:
    lower = any(c.islower() for c in password)
    upper = any(c.isupper() for c in password)
    digit = any(c.isdigit() for c in password)
    other = any(not c.isalnum() for c in password) or any(
        c.isalpha() and ord(c) > 127 for c in password
    )
    return lower + upper + digit + other


def _pool(password: str) -> int:
    size = 0
    if any(c.islower() and ord(c) < 128 for c in password):
        size += 26
    if any(c.isupper() and ord(c) < 128 for c in password):
        size += 26
    if any(c.isdigit() for c in password):
        size += 10
    if any(not c.isalnum() for c in password):
        size += 33
    if any(c.isalpha() and ord(c) > 127 for c in password):
        size += 30
    return max(size, 1)


def _penalty(password: str) -> int:
    """Quantidade de caracteres que não contam por serem previsíveis."""
    low = password.casefold()
    n = len(low)
    marked = [False] * n

    def mark(start: int, end: int) -> None:
        # o primeiro caractere do trecho continua valendo
        for i in range(start + 1, end):
            marked[i] = True

    # repetição (aaa, 1111)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and low[j + 1] == low[i]:
            j += 1
        if j - i >= 2:
            mark(i, j + 1)
        i = j + 1
    # sequências crescentes ou decrescentes (123, abc, cba)
    for step in (1, -1):
        i = 0
        while i < n - 1:
            j = i
            while j + 1 < n and ord(low[j + 1]) - ord(low[j]) == step and low[j].isalnum():
                j += 1
            if j - i >= 2:
                mark(i, j + 1)
            i = max(j, i + 1)
    # sequências de teclado e palavras comuns
    for chunk in _KEYBOARD:
        for size in range(len(chunk), 3, -1):
            for s in range(len(chunk) - size + 1):
                part = chunk[s:s + size]
                k = low.find(part)
                while k != -1:
                    mark(k, k + size)
                    k = low.find(part, k + 1)
    for word in _WORDS:
        k = low.find(word)
        while k != -1:
            mark(k, k + len(word))
            k = low.find(word, k + 1)
    # anos
    for m in _YEAR.finditer(low):
        mark(m.start(), m.end())
    return sum(marked)


def _is_common(password: str) -> bool:
    low = password.casefold()
    if low in _COMMON:
        return True
    base = low.rstrip("0123456789!@#$%&*.?_-")
    return bool(base) and base in _COMMON and len(low) - len(base) <= 4


def _score(password: str) -> int:
    if not password or _is_common(password):
        return 0
    length = len(password)
    effective = max(0, length - _penalty(password))
    # caracteres repetidos em excesso valem menos
    effective = min(effective, len(set(password.casefold())) + 2)
    bits = effective * math.log2(_pool(password))
    if bits < 28:
        score = 0
    elif bits < 36:
        score = 1
    elif bits < 50:
        score = 2
    elif bits < 64:
        score = 3
    else:
        score = 4
    if length < 8:
        score = min(score, 1)
    elif length < 12:
        score = min(score, 3)
    if _classes(password) == 1:
        score = min(score, 2 if length >= 14 else 1)
    if _is_common_base(password):
        score = min(score, 1)
    return score


def _is_common_base(password: str) -> bool:
    low = password.casefold()
    base = low.rstrip("0123456789!@#$%&*.?_-")
    return base in _COMMON and base != low


def password_strength(password: str) -> dict[str, int | str]:
    """Devolve {score: 0..4, label}. Nunca lança exceção."""
    try:
        text = unicodedata.normalize("NFC", str(password))
        score = _score(text)
    except Exception:  # noqa: BLE001 - a heurística nunca deve derrubar a interface
        score = 0
    return {"score": score, "label": LABELS[score]}
