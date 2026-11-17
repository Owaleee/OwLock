"""Store de Chave Secreta compartilhado pelos testes (ids de cofre são aleatórios, sem colisão)."""
from owlock.core import MemoryStore

STORE = MemoryStore()
