# OwLock

[![Testes](https://github.com/Owaleee/OwLock/actions/workflows/ci.yml/badge.svg)](https://github.com/Owaleee/OwLock/actions/workflows/ci.yml)

Gerenciador de senhas local, offline e de código aberto, escrito em Python.

O OwLock guarda suas contas em um único arquivo criptografado, protegido por uma senha mestra. Nenhum dado sai do seu computador e o aplicativo não usa a rede.

## Funcionalidades

- Cofre cifrado com senha mestra.
- Para cada conta: serviço, login ou e-mail, senha, se possui 2FA e qual aplicativo autenticador é usado, além de notas.
- Busca que não diferencia maiúsculas, minúsculas nem acentos, em serviço, login, aplicativo de 2FA e notas.
- Gerador de senhas fortes.
- Troca da senha mestra, que recifra o cofre com um novo salt.
- Copiar senha para a área de transferência, com limpeza automática após 30 segundos.
- Bloqueio automático após 5 minutos sem uso.
- Backup automático (`.bak`) da versão anterior do arquivo e gravação atômica, que evita corromper o cofre se o programa for interrompido durante um salvamento.

## Download (Windows)

Baixe o `OwLock.exe` na página de [Releases](https://github.com/Owaleee/OwLock/releases) e abra. Não precisa instalar Python nem nada.

Como o executável não tem assinatura digital, o Windows SmartScreen pode mostrar um aviso na primeira vez: clique em **Mais informações** e depois em **Executar assim mesmo**. Se quiser conferir a integridade do download, compare o hash SHA-256 do arquivo com o `OwLock.exe.sha256` publicado na mesma release (`Get-FileHash OwLock.exe` no PowerShell).

## Executar a partir do código-fonte

### Windows

1. Instale o Python 3.10 ou superior pelo site [python.org](https://www.python.org/downloads/). No instalador, marque a opção **Add to PATH** e mantenha o componente **tcl/tk** selecionado, pois a interface gráfica depende dele.
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

Também é possível executar com `python -m owlock`.

### Escolhendo o arquivo do cofre

Por padrão, o cofre fica na pasta `.owlock` dentro da pasta do seu usuário, no arquivo `owlock.vault`. Para usar outro arquivo, informe o caminho com a opção `--vault`:

```bash
owlock --vault CAMINHO/do/meu-cofre.vault
```

## Segurança

O OwLock foi projetado para que o conteúdo do arquivo do cofre só possa ser lido com a senha mestra.

- **Derivação da chave:** a senha mestra é transformada em uma chave de 256 bits pelo algoritmo Argon2id, configurado com 3 iterações, 64 MiB de memória e paralelismo 4. Cada cofre usa um salt aleatório de 16 bytes. Esse processo torna ataques de força bruta muito mais caros.
- **Cifragem:** o conteúdo inteiro do cofre é cifrado com AES-256-GCM. Um nonce novo é gerado a cada gravação.
- **Integridade:** o cabeçalho do arquivo (parâmetros de derivação e algoritmos) é usado como dado autenticado. Se alguém alterar esses parâmetros no arquivo, a abertura falha.
- **Sem rede:** o OwLock não envia nem recebe dados. Tudo acontece localmente.
- **Cofre em bloco único:** como o arquivo é cifrado inteiro, ele não revela quantas contas existem nem os nomes dos serviços.

### Limitações

Este é um projeto pessoal e precisa ser usado com consciência dessas limitações:

- **A senha mestra não pode ser recuperada.** Se você a esquecer, os dados do cofre são perdidos.
- **Computador comprometido:** se o sistema estiver infectado por keylogger ou malware, nenhum gerenciador local oferece proteção suficiente.
- **Dados na memória:** enquanto o cofre estiver desbloqueado, os dados ficam na memória do processo.
- **Arquivo `.bak`:** é a versão anterior do cofre, também cifrada. Depois de trocar a senha mestra, o `.bak` continua abrindo com a senha antiga até o próximo salvamento.
- **Sem auditoria independente:** o código não passou por auditoria de segurança externa. Para uso crítico, considere também soluções auditadas, como [Bitwarden](https://bitwarden.com/) ou [KeePassXC](https://keepassxc.org/).

### Recomendação

Faça cópias do arquivo `.vault` em outro local, como um pendrive ou um serviço de nuvem. Ele está cifrado, então pode ser guardado com segurança fora do computador.

## Formato do arquivo

O cofre é salvo em JSON, com número de versão. A estrutura é esta:

```json
{
  "format": "owlock-vault",
  "version": 1,
  "kdf": {"name": "argon2id", "salt": "<b64>", "time_cost": 3, "memory_cost": 65536, "parallelism": 4},
  "cipher": {"name": "aes-256-gcm", "nonce": "<b64 12 bytes>"},
  "ciphertext": "<b64>"
}
```

O formato é versionado de propósito, para permitir que um aplicativo de celular leia o mesmo arquivo no futuro.

## Arquitetura

```
owlock/
  core/            # sem dependência de interface; reaproveitável numa API futura
    models.py      # Entry (dataclass)
    crypto.py      # derivação de chave (Argon2id) + AES-256-GCM
    vault.py       # Vault: criar, abrir, CRUD, salvar (escrita atômica), trocar senha mestra
    generator.py   # gerador de senhas com `secrets`
    errors.py      # WrongPasswordError, VaultCorruptedError, VaultExistsError
  gui/
    app.py         # CustomTkinter: desbloqueio, lista, formulários, troca de senha mestra
  __main__.py      # `python -m owlock`
packaging/         # ponto de entrada do executável (PyInstaller)
tests/             # pytest: núcleo e teste de fumaça da interface
.github/workflows/ # CI (Linux e Windows) e geração do OwLock.exe nas releases
```

O núcleo (`owlock/core`) não depende da interface gráfica. Isso permite reaproveitar a lógica de cofre em outras interfaces, como uma API ou um aplicativo móvel.

## Testes

Para instalar as dependências de desenvolvimento e executar os testes:

```bash
pip install -e ".[dev]"
pytest
```

Os testes da interface precisam de uma tela; no Linux sem ambiente gráfico, rode com `xvfb-run -a pytest`. O GitHub Actions executa a suíte no Linux e no Windows a cada push.

## Gerar o executável

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name OwLock --collect-data customtkinter --paths . packaging/run_owlock.py
```

O arquivo fica em `dist/`. Para publicar uma nova versão, crie uma release no GitHub (aba **Releases** > **Draft a new release**, com uma tag como `v0.2.0`): o workflow gera o `OwLock.exe` no Windows e o anexa à release automaticamente.

## Roteiro

Próximos passos previstos:

- Aplicativo de celular que lê o mesmo arquivo de cofre.
- Sincronização entre dispositivos.
- Geração de códigos TOTP.
- Importação e exportação em CSV.
- Interface com visual mais moderno.

## Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).
