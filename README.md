<p align="center"><img src="docs/logo.png" width="128" alt="Ícone do OwLock"></p>

# OwLock

[![Testes](https://github.com/Owaleee/OwLock/actions/workflows/ci.yml/badge.svg)](https://github.com/Owaleee/OwLock/actions/workflows/ci.yml)
[![Versão](https://img.shields.io/github/v/release/Owaleee/OwLock?label=vers%C3%A3o)](https://github.com/Owaleee/OwLock/releases/latest)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)

Gerenciador de senhas local, offline e de código aberto, escrito em Python, com interface em HTML, CSS e JavaScript numa janela nativa.

O OwLock guarda suas contas em um único arquivo criptografado, protegido por uma senha mestra. Nenhum dado sai do seu computador e o aplicativo não usa a rede.

**[Baixar a versão mais recente](https://github.com/Owaleee/OwLock/releases/latest)** · [Roadmap](ROADMAP.md)

## Funcionalidades

- Cofre cifrado com senha mestra.
- Interface escura, com animações, em janela nativa.
- Layout que se adapta a telas pequenas.
- Resumo do cofre: total de contas, quantas têm 2FA e quantas precisam de atenção.
- Para cada conta: serviço, login ou e-mail, senha, se possui 2FA e qual aplicativo autenticador é usado, além de notas.
- Medidor de força em cada senha e filtro **Atenção**, para ver as contas com senhas fracas ou razoáveis.
- Senha revelada só sob demanda, pelo botão **Mostrar**.
- Busca que não diferencia maiúsculas, minúsculas nem acentos, em serviço, login, aplicativo de 2FA e notas.
- Gerador de senhas fortes, com tamanho e tipos de caractere escolhidos por você.
- Troca da senha mestra, que recifra o cofre com um novo salt.
- Categorias com cor e ícone, filtro por categoria e tela própria para criar e editar.
- Histórico de senhas: data de criação da conta e cada senha anterior com a data da troca (até 20 versões), com opção de mostrar ou copiar.
- Site da conta, com botão para abrir no navegador padrão.
- Biblioteca de links com 67 serviços (Google, Steam, Epic Games, Discord, Netflix, Nubank, gov.br...): ao digitar o nome, o app sugere o serviço e preenche o link de login oficial. Os links podem ser alterados e novos serviços adicionados nos Ajustes.
- Ícones das plataformas no estilo de ícone de app, embutidos no programa (sem baixar nada da internet), com opção de escolher outro ícone ou usar a letra.
- Copiar login ou senha para a área de transferência, com contagem visual e limpeza automática (10 a 90 segundos; recomendado: 30).
- Bloqueio automático após um tempo sem uso (1 a 30 minutos; recomendado: 5).
- Backup automático (`.bak`) da versão anterior do arquivo e gravação atômica, que evita corromper o cofre se o programa for interrompido durante um salvamento.

## Download (Windows)

Baixe o `OwLock.exe` na página de [Releases](https://github.com/Owaleee/OwLock/releases) e abra. Não precisa instalar Python nem nada.

O app usa o Microsoft Edge WebView2, que já vem instalado no Windows 10 e 11 atualizados.

Como o executável não tem assinatura digital, o Windows SmartScreen pode mostrar um aviso na primeira vez: clique em **Mais informações** e depois em **Executar assim mesmo**. Se quiser conferir a integridade do download, compare o hash SHA-256 do arquivo com o `OwLock.exe.sha256` publicado na mesma release (`Get-FileHash OwLock.exe` no PowerShell).

## Executar a partir do código-fonte

### Windows

1. Instale o Python 3.10 ou superior pelo site [python.org](https://www.python.org/downloads/). No instalador, marque a opção **Add to PATH**.
2. Abra o terminal (PowerShell ou Prompt de Comando) e execute:

```bash
git clone https://github.com/Owaleee/OwLock.git
cd OwLock
python -m venv .venv
.venv\Scripts\activate
pip install -e .
owlock
```

### Linux e macOS

Requer Python 3.10 ou superior.

```bash
git clone https://github.com/Owaleee/OwLock.git
cd OwLock
python -m venv .venv
source .venv/bin/activate
pip install -e .
owlock
```

No Linux, o pywebview precisa de um backend gráfico. Depois do `pip install -e .`, instale o backend Qt com `pip install "pywebview[qt]"` (ou o backend GTK, se preferir).

Também é possível executar com `python -m owlock`.

### Escolhendo o arquivo do cofre

Por padrão, o cofre fica na pasta `.owlock` dentro da pasta do seu usuário, no arquivo `owlock.vault`. Para usar outro arquivo, informe o caminho com a opção `--vault`:

```bash
owlock --vault CAMINHO/do/meu-cofre.vault
```

## Segurança

Para abrir o cofre são necessárias **duas coisas**: a **senha mestra** e a **Chave Secreta**, uma chave aleatória de 130 bits guardada no seu computador (Gerenciador de Credenciais do Windows). O modelo de ameaças completo está no [SECURITY.md](SECURITY.md).

- **Derivação:** a senha mestra passa pelo Argon2id (3 iterações, 64 MiB, paralelismo 4, salt aleatório de 16 bytes) e é combinada com a Chave Secreta via HKDF-SHA256. O resultado tranca a chave do cofre.
- **Cifragem:** AES-256-GCM. Os metadados e cada conta são cifrados separadamente, ligados ao identificador do cofre e da conta; o cabeçalho é autenticado.
- **Arquivo vazado não basta:** sem a Chave Secreta não dá nem para começar a adivinhar a senha mestra.
- **Kit de emergência:** a Chave Secreta é mostrada na criação do cofre, com uma página para salvar e imprimir. Ela é necessária para abrir o cofre em outro computador.
- **Troca de senha instantânea:** só a "tranca" da chave do cofre é refeita, e o `.bak` é atualizado para não abrir com a senha antiga.
- **Sem rede:** o OwLock não envia nem recebe dados.

### Interface

A interface roda numa janela do pywebview, e estas regras protegem os dados que ela exibe:

- **Senhas fora da listagem:** a lista de contas nunca recebe senhas. A senha só chega à interface ao clicar em **Mostrar** (`reveal_password`) ou no formulário de edição.
- **Cópia pelo Python:** a cópia é feita pelo Python, que limpa a área de transferência após o prazo escolhido (30 segundos por padrão), somente se ela ainda contiver o texto copiado.
- **Sem `innerHTML` com dados:** textos do usuário são sempre gravados com `textContent`, o que evita XSS, já que um ataque desse tipo daria acesso ao cofre.
- **Content-Security-Policy restrita:** a política permite apenas recursos locais (`default-src 'self'`), fontes locais e nenhuma requisição para a internet. Scripts inline continuam proibidos. A exceção é `'unsafe-eval'` em `script-src`, exigida pelo pywebview, que cria as funções da ponte (`window.pywebview.api`) com `new Function`; por isso a defesa contra XSS depende de não usar `innerHTML` com dados.
- **Bloqueio feito no Python:** a Api bloqueia o cofre sozinha após o tempo escolhido sem atividade (5 minutos por padrão). A interface apenas mostra a contagem.

### Limitações

Este é um projeto pessoal e precisa ser usado com consciência dessas limitações:

- **Não existe recuperação.** Sem a senha mestra ou sem a Chave Secreta (guarde o Kit de emergência), os dados do cofre são perdidos.
- **Computador comprometido:** se o sistema estiver infectado por keylogger ou malware, nenhum gerenciador local oferece proteção suficiente.
- **Dados na memória:** enquanto o cofre estiver desbloqueado, os dados ficam na memória do processo.
- **Metadados:** o arquivo revela a quantidade de contas, mas não os nomes, logins, senhas, categorias ou links.
- **Sem auditoria independente:** o código não passou por auditoria de segurança externa. Para uso crítico, considere também soluções auditadas, como [Bitwarden](https://bitwarden.com/) ou [KeePassXC](https://keepassxc.org/).

### Recomendação

Faça cópias do arquivo `.vault` em outro local, como um pendrive ou um serviço de nuvem: sem a Chave Secreta ele não pode ser atacado. Guarde o Kit de emergência separado do arquivo.

## Formato do arquivo

O cofre é um JSON versionado (formato v2; cofres v1 são convertidos automaticamente na primeira abertura, com cópia `.v1-backup`):

```json
{
  "format": "owlock-vault", "version": 2, "vault_id": "<uuid>",
  "kdf": {"name": "argon2id", "salt": "<b64>", "time_cost": 3, "memory_cost": 65536, "parallelism": 4},
  "secret_key": {"id": "<16 hex>"},
  "cipher": {"name": "aes-256-gcm"},
  "key":     {"nonce": "<b64>", "ciphertext": "<b64>"},
  "meta":    {"nonce": "<b64>", "ciphertext": "<b64>"},
  "entries": [{"id": "<uuid>", "nonce": "<b64>", "ciphertext": "<b64>"}]
}
```

`key` é a chave do cofre trancada pela senha mestra + Chave Secreta; `meta` guarda categorias, ajustes e serviços personalizados; cada item de `entries` é uma conta cifrada separadamente, o que prepara a sincronização com o celular.

## Arquitetura

```
owlock/
  __main__.py      # `owlock` ou `python -m owlock`: lê --vault e abre o aplicativo
  core/            # sem dependência de interface; reaproveitável em outras interfaces
    strength.py    # força da senha (0 a 4), sem dependências
    models.py      # Entry, Category (dataclasses), cores e ícones das categorias
    catalog.py     # biblioteca de serviços: links de login, apelidos e ícones
    data/          # services.json (67 serviços) e brand_icons.json
    crypto.py      # Argon2id, HKDF e AES-256-GCM
    secret_key.py  # Chave Secreta: geração, formato OW2-…, verificação
    keystore.py    # onde a Chave Secreta fica guardada (chaveiro do sistema ou arquivo protegido)
    vault.py       # Vault: criar, abrir, CRUD, salvar (escrita atômica), trocar senha mestra
    generator.py   # gerador de senhas com `secrets`
    errors.py      # WrongPasswordError, VaultCorruptedError, VaultExistsError
    (vault.py também guarda categorias, ajustes, histórico e serviços personalizados)
  app/
    api.py         # Api: única ponte entre a interface e o núcleo
    main.py        # abre a janela pywebview com a Api
    devserver.py   # SÓ desenvolvimento: serve a interface no navegador (127.0.0.1) com a mesma Api via HTTP
  web/             # index.html, styles.css, app.js, bridge.js, fonts/, img/, icons/brands/
packaging/         # executável (PyInstaller), ícone do app e script dos ícones de marcas
tests/             # pytest: núcleo, Api, servidor de desenvolvimento e teste ponta a ponta (e2e)
.github/workflows/ # CI (Linux e Windows) e geração do OwLock.exe nas releases
```

O núcleo (`owlock/core`) não depende da interface. Isso permite reaproveitar a lógica de cofre em outras interfaces, como uma API ou um aplicativo móvel. A interface (HTML, CSS e JavaScript) só conversa com o núcleo pela classe `Api`, em `owlock/app/api.py`. O servidor de desenvolvimento usa essa mesma classe, então a interface se comporta igual no navegador e na janela nativa.

## Testes

Para instalar as dependências de desenvolvimento e executar os testes:

```bash
pip install -e ".[dev]"
pytest
```

O GitHub Actions executa a suíte no Linux e no Windows a cada push para a `main` e em pull requests.

### Teste ponta a ponta da interface

O teste de fumaça abre a interface no Chrome (headless) contra o servidor de desenvolvimento e confere o fluxo principal: desbloquear, listar, buscar, mostrar senha, criar e excluir conta, gerador, ajustes e layout de celular. As capturas de tela são salvas em `/tmp/owlock-shots/`.

```bash
# 1. dependências (uma vez)
cd tests/e2e && npm i

# 2. servidor de desenvolvimento com cofre de teste (na raiz do projeto)
cd ../..
rm -f /tmp/owlock-e2e.vault
python -m owlock.app.devserver --vault /tmp/owlock-e2e.vault --seed --port 8765 &

# 3. teste
cd tests/e2e && node smoke.mjs
```

Variáveis opcionais: `OWLOCK_URL`, `CHROME_PATH` (padrão `/usr/bin/google-chrome`) e `OWLOCK_SHOTS`. O teste sai com código diferente de 0 se algo não aparecer. Encerre o servidor depois (`kill %1`).

O servidor de desenvolvimento é só para desenvolvimento: ele escuta apenas em `127.0.0.1`, cria um cofre de teste com `--seed` e não deve ser usado com dados reais.

## Gerar o executável

```bash
pip install "pyinstaller>=6"
pyinstaller --noconfirm --onefile --windowed --name OwLock \
  --add-data "owlock/web:owlock/web" --collect-all webview --paths . \
  packaging/run_owlock.py
```

No Windows, o `--add-data` usa `;` como separador: `--add-data "owlock/web;owlock/web"`, como no workflow de release.

O arquivo fica em `dist/`. Para publicar uma nova versão, crie uma release no GitHub (aba **Releases** > **Draft a new release**, com uma tag como `v0.2.0`): o workflow gera o `OwLock.exe` no Windows e o anexa à release automaticamente.

## Roteiro

Versões entregues e próximos passos estão no [ROADMAP.md](ROADMAP.md). Em resumo:

- **v0.6:** ícone na bandeja do Windows com busca rápida e atalho global, senhas repetidas e antigas, bloqueio ao minimizar, backups com histórico, favoritas.
- **v0.7:** atalhos de teclado, importar/exportar CSV, códigos 2FA opcionais.
- **v0.8:** extensão de navegador para preencher login e senha.
- **v1.0:** aplicativo de celular com pareamento por QR code e sincronização.

## Créditos

Ícones de marcas do projeto [Simple Icons](https://simpleicons.org) (CC0 1.0). As marcas pertencem aos seus respectivos donos e são usadas apenas para identificar cada serviço. Para atualizar os ícones, veja `packaging/build_brand_icons.py`.

## Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).
