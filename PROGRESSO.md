# OwLock — gerenciador de senhas local

## Objetivo
App desktop local, de código aberto, onde o usuário guarda contas (serviço, login/e-mail, senha,
se tem 2FA e qual app autenticador, notas) num arquivo criptografado protegido por uma senha mestra.

## Fora de escopo (por enquanto)
- Sincronização com celular (o formato do arquivo já é pensado para isso: ver "Formato do cofre").
- Gerar códigos TOTP, importar/exportar de outros gerenciadores, CLI.

## Critério de pronto do MVP
1. Criar um cofre com senha mestra, adicionar uma conta, fechar o app, reabrir com a senha certa e ver a conta.
2. Senha mestra errada é recusada sem travar nem corromper nada.
3. Editar, excluir, buscar, copiar senha (área de transferência limpa sozinha) e gerar senha forte.
4. O arquivo no disco não contém nenhum texto legível das contas.

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
    app.py         # CustomTkinter: telas de desbloqueio, lista, formulário
  __main__.py      # `python -m owlock`
tests/             # pytest do núcleo
```

## Contrato do núcleo (a interface depende só disto)
```python
# owlock/core/models.py
@dataclass
class Entry:
    service: str            # obrigatório, ex.: "Google"
    username: str = ""      # login ou e-mail
    password: str = ""
    has_2fa: bool = False
    twofa_app: str = ""     # ex.: "Google Authenticator"
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = <ISO 8601 UTC agora>
    updated_at: str = <ISO 8601 UTC agora>
    def to_dict(self) -> dict; @classmethod from_dict(cls, d) -> Entry

# owlock/core/vault.py
class Vault:
    path: Path
    entries: list[Entry]                     # leitura; ordenar fica a cargo de quem exibe
    @classmethod create(cls, path, master_password: str) -> "Vault"   # VaultExistsError se já existir; salva na hora
    @classmethod open(cls, path, master_password: str) -> "Vault"     # WrongPasswordError / VaultCorruptedError / FileNotFoundError
    def add(self, entry: Entry) -> Entry                               # salva
    def update(self, entry: Entry) -> Entry                            # pelo id; KeyError se não existir; atualiza updated_at; salva
    def delete(self, entry_id: str) -> None                            # KeyError se não existir; salva
    def search(self, text: str) -> list[Entry]                         # sem diferenciar maiúsc./acentos simples, em service/username/twofa_app/notes
    def change_master_password(self, current: str, new: str) -> None   # WrongPasswordError se current errada; novo salt; salva
    def save(self) -> None

# owlock/core/generator.py
def generate_password(length=20, upper=True, lower=True, digits=True, symbols=True) -> str

DEFAULT_VAULT_PATH = Path.home() / ".owlock" / "owlock.vault"   (em vault.py)
MIN_MASTER_PASSWORD_LENGTH = 8                                  (em vault.py; create/change_master_password levantam ValueError abaixo disso)
```

## Formato do cofre (arquivo JSON, versionado)
```json
{
  "format": "owlock-vault",
  "version": 1,
  "kdf": {"name": "argon2id", "salt": "<b64>", "time_cost": 3, "memory_cost": 65536, "parallelism": 4},
  "cipher": {"name": "aes-256-gcm", "nonce": "<b64 12 bytes>"},
  "ciphertext": "<b64>"
}
```
- Texto claro cifrado = JSON `{"entries": [Entry.to_dict(), ...]}` em UTF-8.
- AAD do GCM = bytes canônicos do cabeçalho (tudo menos `ciphertext` e `cipher.nonce`), para que alterar parâmetros no arquivo seja detectado.
- Nonce novo (os.urandom(12)) a cada salvamento. Salt novo só ao criar e ao trocar a senha mestra.
- Escrita atômica: grava em `<arquivo>.tmp`, fsync, `os.replace`. Antes de substituir, o arquivo anterior vira `<arquivo>.bak`.
- Senha errada e arquivo adulterado são indistinguíveis no GCM (InvalidTag) → WrongPasswordError com mensagem
  "Senha mestra incorreta ou arquivo alterado". JSON inválido/campos faltando/versão desconhecida → VaultCorruptedError.

## Decisões
- Python: bibliotecas de criptografia auditadas (`cryptography`, `argon2-cffi`), fácil de quem baixar rodar.
- Argon2id com 64 MiB: resistente a força bruta com GPU; parâmetros ficam gravados no arquivo para poderem subir no futuro.
- Cofre inteiro cifrado num bloco: simples e sem vazar quantidade de campos/nomes de serviço.
- Python 3.12 para desenvolvimento e para o executável (os testes rodam em 3.10+).

## Status
- [x] Fatia 1: núcleo + testes (35 testes; rollback em memória quando a gravação falha)
- [x] Fatia 2: interface (desbloqueio, lista, busca, formulário, cópia com limpeza em 30 s, bloqueio em 5 min)
- [x] Fatia 3: README + LICENSE

- [x] Troca de senha mestra na interface
- [x] Executável Windows (PyInstaller) gerado pelo GitHub Actions a cada tag vX.Y.Z
- [x] CI: testes no Linux e no Windows
- [x] Testado manualmente no Windows 11 (criar, adicionar, copiar, editar, excluir, bloquear/desbloquear)

## Próximos passos
- Modernizar o visual da interface.
- App de celular lendo o mesmo formato de cofre.

## Fase 2 — Interface nova (web dentro de janela nativa)

Motivo: o CustomTkinter não faz degradê, desfoque nem animações suaves. A interface passa a ser HTML/CSS/JS
numa janela nativa (pywebview; no Windows usa o WebView2 do Edge). O núcleo (`owlock/core`) não muda.
O mesmo front-end poderá ser reaproveitado no app de celular.

### Estrutura
```
owlock/
  core/strength.py   # força da senha (0 a 4), sem dependências
  app/api.py         # Api: única ponte entre a interface e o núcleo
  app/main.py        # abre a janela pywebview com a Api
  app/devserver.py   # SÓ desenvolvimento: serve a interface no navegador (127.0.0.1) com a mesma Api via HTTP
  web/               # index.html, styles.css, app.js, bridge.js, fonts/
```

### Regras de segurança da interface
- A interface nunca recebe senhas na listagem; só em `reveal_password` (ao clicar em Mostrar) e no formulário de edição.
- Copiar acontece no Python (`copy_field`); a área de transferência é limpa em 30 s se ainda tiver o mesmo texto.
- Nada de `innerHTML` com dados do usuário: textos sempre via `textContent` (evita XSS, que daria acesso ao cofre).
- Content-Security-Policy restrita (`default-src 'self'`), fontes locais, nenhuma requisição para a internet.
  Exceção necessária: `script-src` inclui `'unsafe-eval'` porque o pywebview cria as funções da ponte (`window.pywebview.api`)
  com `new Function`. Scripts inline continuam proibidos, e a defesa contra XSS é não usar `innerHTML` com dados.
- Bloqueio automático: a Api bloqueia sozinha após 5 min sem chamadas de atividade; a interface mostra a contagem.

### Contrato da Api (`owlock/app/api.py`)
Toda resposta é um dict JSON: sucesso `{"ok": true, ...}`; erro `{"ok": false, "error": "<código>", "message": "<texto pt-BR>"}`.
Métodos que exigem cofre aberto devolvem `error: "locked"` quando bloqueado (inclusive por inatividade).

```
Api(vault_path: Path, auto_lock_seconds=300, clipboard=None, clock=time.monotonic, clear_after=30)
  clipboard: objeto com copy(text) e paste() -> str (padrão: pyperclip); injetável nos testes.

status() -> {ok, exists, unlocked, vault_path, auto_lock_seconds, seconds_left}   # não conta como atividade
create_vault(password, confirm) -> ok | password_too_short | mismatch | exists
unlock(password) -> ok | wrong_password | corrupted (message cita o caminho do .bak) | not_found
lock() -> ok
touch() -> {ok, seconds_left}                       # registra atividade
list_entries(query="", filter="all") -> {ok, entries: [EntrySummary], stats: {total, with_2fa, attention}}
    filter: "all" | "2fa" | "attention" (attention = strength.score <= 2); ordenado por service (casefold)
    EntrySummary = {id, service, username, has_2fa, twofa_app, notes, created_at, updated_at,
                    password_length, strength: {score, label}}            # SEM a senha
get_entry(id) -> {ok, entry: EntrySummary} | not_found
reveal_password(id) -> {ok, password} | not_found
copy_field(id, field) -> {ok, clear_in: 30} | not_found | invalid_field     # field: "username" | "password"
save_entry(data) -> {ok, entry: EntrySummary} | service_required | not_found | save_failed
    data = {id?: str, service, username, password?: str|None, has_2fa, twofa_app, notes}
    sem id = nova conta; com id = edição; em edição, password ausente/None mantém a senha atual
delete_entry(id) -> ok | not_found | save_failed
generate_password(length=20, upper=True, lower=True, digits=True, symbols=True) -> {ok, password, strength} | invalid_options
check_strength(password) -> {ok, score, label}                            # não exige cofre aberto
change_master_password(current, new, confirm) -> ok | wrong_password | password_too_short | mismatch | same_password
copy_text(text) -> {ok, clear_in: 30} | invalid_text       # cópia avulsa (gerador), mesma limpeza automática
shutdown() -> ok                                    # limpa a área de transferência se ainda tiver algo copiado pelo app; bloqueia
```

### Força da senha (`owlock/core/strength.py`)
`password_strength(password: str) -> dict {score: 0..4, label}`; rótulos: 0 "Muito fraca", 1 "Fraca", 2 "Razoável", 3 "Boa", 4 "Forte".
Heurística simples: comprimento, variedade de tipos de caractere, penalidade para sequências (123, abc, qwerty),
anos (19xx/20xx), repetição e uma lista curta de senhas comuns.
