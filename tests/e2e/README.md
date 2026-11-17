# Teste de fumaça da interface

Abre a interface no Chrome (headless) contra o servidor de desenvolvimento e confere o fluxo principal:
desbloquear, listar, buscar, mostrar senha, criar/excluir conta, gerador, ajustes e layout de celular.
Salva screenshots em `/tmp/owlock-shots/`.

## Como rodar

```bash
# 1. dependências (uma vez)
cd tests/e2e && npm i

# 2. servidor de desenvolvimento com cofre de teste (na raiz do projeto)
cd ../..
rm -rf /tmp/owlock-e2e.vault* /tmp/owlock-e2e2.vault*
python -m owlock.app.devserver --vault /tmp/owlock-e2e.vault --seed --port 8765 &
# segundo cenário: cofre criado do zero (tela do Kit de emergência e "novo computador")
python -m owlock.app.devserver --vault /tmp/owlock-e2e2.vault --port 8766 &

# 3. teste
cd tests/e2e && node smoke.mjs
```

Variáveis opcionais: `OWLOCK_URL`, `OWLOCK_URL2`, `OWLOCK_KEYS2`, `CHROME_PATH` (padrão `/usr/bin/google-chrome`), `OWLOCK_SHOTS`.
O teste sai com código diferente de 0 se algo não aparecer. Encerre os servidores depois (`kill %1 %2`).
