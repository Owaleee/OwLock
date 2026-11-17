# OwLock — gerenciador de senhas local

## Objetivo
App desktop local, de código aberto, onde o usuário guarda contas (serviço, login/e-mail, senha,
se tem 2FA e qual app autenticador, notas) num arquivo criptografado protegido por uma senha mestra.

## Fora de escopo (por enquanto)
- Sincronização com celular (o formato do arquivo já é pensado para isso: ver "Formato do cofre").
- Gerar códigos TOTP, CLI.

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

- [x] Interface nova em HTML/CSS/JS (pywebview), visual estilo iOS e logo própria
- [x] Categorias (Fase 3)
- [x] Tempos configuráveis, histórico de senhas, site da conta, tela de categorias (Fase 4)
- [x] Biblioteca de serviços com links e ícones das plataformas (Fase 5)

## Próximos passos
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

## Fase 3 — Categorias

Objetivo: organizar as contas em categorias (Pessoal, Jogos, Trabalho...), com cor e ícone, filtrar por elas e gerenciá-las.

### Núcleo
- `models.py`: `Category` (dataclass): `name: str`, `color: str` (chave da paleta), `icon: str` (chave da lista de ícones),
  `id: str = uuid4().hex`; `to_dict()` / `from_dict()` (ignora chaves desconhecidas; exige `id` e `name`).
  `Entry` ganha `category_id: str = ""` ("" = sem categoria). Cofres antigos continuam abrindo (from_dict já ignora/assume padrão).
- Paleta (`CATEGORY_COLORS`, chave → hex): mint #9FE3D3, blue #7AB8FF, violet #B69CFF, pink #FF8FB8, amber #FFB347,
  coral #FF7A6B, lime #B8E986, gray #A1A6B4.
- Ícones (`CATEGORY_ICONS`): user, briefcase, gamepad, chat, card, play, home, cart, school, code, heart, star.
- Texto claro do cofre passa a ser `{"entries": [...], "categories": [...]}`. O formato do arquivo continua `version: 1`
  (a mudança é só dentro do conteúdo cifrado, e é compatível).
- Ao abrir um cofre cujo conteúdo NÃO tem a chave `"categories"` (cofres criados antes desta fase), e ao criar um cofre novo,
  o cofre recebe as categorias padrão: Pessoal (mint, user), Trabalho (blue, briefcase), Jogos (violet, gamepad),
  Redes sociais (pink, chat), Financeiro (amber, card), Streaming (coral, play). Se a chave existir (mesmo vazia), nada é criado.
- `Vault`: `categories: list[Category]`; `add_category(c)`, `update_category(c)` (KeyError se não existir),
  `delete_category(id)` (KeyError; as contas dessa categoria ficam com `category_id = ""`; tudo num único save),
  com o mesmo rollback em memória das outras operações se o save falhar.

### Api (acréscimos)
```
list_categories() -> {ok, categories: [CategorySummary]}          # na ordem salva
    CategorySummary = {id, name, color, color_hex, icon, count}    # count = contas nessa categoria
save_category(data) -> {ok, category: CategorySummary} | name_required | name_too_long (> 24) | name_exists (casefold)
                       | invalid_color | invalid_icon | too_many (> 30) | not_found | save_failed
    data = {id?, name, color, icon}; sem id = nova; com id = edição
delete_category(id) -> {ok, moved: <n contas que ficaram sem categoria>} | not_found | save_failed
list_entries(query="", filter="all", category="") -> ... (igual) + category: "" = todas, "none" = sem categoria, senão o id
    | invalid_category (id inexistente)
    stats ganha "uncategorized": n
EntrySummary ganha: category_id, category: CategorySummary-sem-count | null
save_entry(data): data ganha category_id ("" ou id existente; inexistente → invalid_category)
category_options() -> {ok, colors: [{key, hex}], icons: [key]}   # não exige cofre aberto
```

### Interface
- Faixa de categorias na coluna da lista, abaixo da busca e acima do segmented control: pílulas de vidro roláveis na
  horizontal ("Todas" primeiro, depois cada categoria com ícone na cor dela, nome e contador; "Sem categoria" só aparece se houver
  contas sem categoria; no fim, uma pílula "+" para criar). A selecionada fica preenchida com a cor da categoria em tom suave e um halo.
  Combina com os filtros Todas/Com 2FA/Atenção (os dois filtros valem juntos).
- Linha da lista: o monograma ganha um degradê sutil na cor da categoria.
- Detalhe: uma pílula com ícone + nome da categoria abaixo do nome do serviço.
- Formulário de conta: seletor de categoria em pílulas (com "Nenhuma").
- Ajustes > Categorias (lista agrupada estilo iOS): ícone colorido, nome, contador, toque para editar; botão "Nova categoria".
- Editor de categoria (modal/sheet): nome, grade de 8 cores (bolinhas com halo na selecionada), grade de 12 ícones,
  pré-visualização ao vivo da pílula; excluir (vermelho) com confirmação dizendo quantas contas ficarão sem categoria.

## Ideias futuras (registradas)

### Ícones das plataformas (pedido do Alexandre, para depois das categorias)
Mostrar o símbolo de cada serviço (Discord, Epic Games, GitHub, Steam, Google...) no lugar da letra.
- Ícones EMBUTIDOS no app (sem buscar na internet): buscar favicon online revelaria quais sites a pessoa usa e quebraria a
  regra de nenhuma requisição externa. Base sugerida: Simple Icons (SVGs de marcas, licença CC0 para os arquivos; as marcas
  continuam sendo dos donos, e o uso é só para identificar o serviço).
- Associação pelo nome do serviço (normalizado: sem acentos/maiúsculas/espaços, com apelidos: "epic" → Epic Games) e,
  no futuro, pelo domínio da URL da conta.
- Desenhado em branco ou na cor oficial da marca sobre o ladrilho grafite; sem correspondência, continua o monograma com a cor da categoria.
- Opção de escolher o ícone manualmente no formulário da conta.

## Fase 4 — Ajustes de tempo, histórico de senhas, site da conta e correções

Pedidos do Alexandre após testar no Windows:
1. A faixa de categorias do formulário não rola além de "Jogos" no Windows (mouse sem rolagem horizontal).
2. Ícone "Categorias" na barra lateral, abrindo uma tela própria para criar/editar categorias (cores, ícones).
3. Escolher o tempo do bloqueio automático e da limpeza da área de transferência, com a opção recomendada marcada.
4. Versionamento: histórico das senhas de cada conta (quando foi criada e cada troca).
5. Botão para abrir o site da conta. (Preencher login/senha no site fica para a próxima versão: exige extensão de navegador.)

### Núcleo
- `Entry` ganha `url: str = ""` e `password_history: list[dict]` (padrão vazio), cada item `{"password": str, "changed_at": ISO}`
  = a senha ANTIGA e quando deixou de valer. Mais recente primeiro. Máximo 20 itens (descarta os mais antigos).
  `Entry.to_dict/from_dict` incluem os dois campos; cofres antigos abrem com padrões.
- O histórico é preenchido no `Vault.update` quando a senha muda (compara com a senha salva; senha igual não gera versão).
- `Settings` (dataclass) no conteúdo cifrado: `auto_lock_minutes: int = 5`, `clipboard_clear_seconds: int = 30`.
  `AUTO_LOCK_OPTIONS = (1, 2, 5, 10, 15, 30)` (recomendado 5) e `CLIPBOARD_OPTIONS = (10, 20, 30, 45, 60, 90)` (recomendado 30).
  Texto claro: `{"entries": [...], "categories": [...], "settings": {...}}`; sem a chave → padrões; valor fora das opções → padrão.
  `Vault.settings` e `Vault.update_settings(settings)` (salva, com rollback em memória se falhar).

### Api (acréscimos e mudanças)
```
get_settings() -> {ok, settings: {auto_lock_minutes, clipboard_clear_seconds},
                   options: {auto_lock_minutes: [{value, label, recommended}], clipboard_clear_seconds: [...]}}
    labels: "1 minuto", "5 minutos", "30 segundos", "1 minuto e 30 segundos"...
save_settings(data) -> {ok, settings} | invalid_auto_lock | invalid_clipboard | save_failed
    Ao abrir o cofre e ao salvar, a Api passa a usar esses valores (auto-lock em segundos = minutos*60; clear_after).
    status() devolve auto_lock_seconds e clipboard_clear_seconds atuais.
EntrySummary ganha: url, history_count (nunca as senhas antigas)
save_entry(data): data ganha url ("" ou http(s)://...; sem esquema, prefixa https://; outro esquema → invalid_url; máx. 2048)
get_password_history(id) -> {ok, created_at, history: [{index, changed_at, length, strength: {score,label}}]} | not_found
reveal_history_password(id, index) -> {ok, password} | not_found | invalid_index
copy_history_password(id, index) -> {ok, clear_in} | not_found | invalid_index      (mesma limpeza condicional)
open_url(id) -> {ok} | not_found | no_url | invalid_url | open_failed
    Abre a URL salva da conta no navegador padrão (webbrowser.open), só http/https. Recebe o id, nunca uma URL vinda da interface.
    Abridor injetável nos testes.
```

### Interface
- Barra lateral: novo item "Categorias" (entre Cofre e Gerador) → tela Categorias (lista agrupada com ícone, nome, contador,
  editar; "Nova categoria"). Ajustes mantém um atalho para ela, mas a gestão principal fica na tela própria.
- Faixa de categorias (lista e formulário): setas ‹ › que aparecem quando há mais conteúdo, roda vertical do mouse rola na
  horizontal, e arrastar com o mouse rola. No FORMULÁRIO, as pílulas quebram linha (flex-wrap) — nada escondido.
- Ajustes > Proteção automática: duas linhas com seletor (pílulas ou menu iOS) das opções; a recomendada mostra o selo "Recomendado".
  O texto explicativo usa os valores escolhidos. O contador "Bloqueia em" e o anel da cópia usam os tempos escolhidos.
- Formulário: campo "Site" (URL). Detalhe: linha "Site" com o domínio e botão "Abrir site" (chama open_url).
- Detalhe: seção "Histórico de senhas" (lista agrupada): "Criada em <data>", e cada versão "Senha anterior · alterada em <data>"
  com LED de força, botões Mostrar (revela só aquela, some ao trocar de conta/bloquear) e Copiar. Se vazio: "Esta senha nunca foi alterada."

## Fase 5 — Biblioteca de serviços (links de login + ícones das plataformas)

Pedido do Alexandre: ícones das plataformas e uma biblioteca com os links de login mais usados; ao digitar o nome da
plataforma, o app preenche o link; uma área nos Ajustes para alterar links e adicionar novos.

### Dados embutidos (já prontos, não editar à mão)
- `owlock/core/data/services.json`: 67 serviços `{key, name, aliases, login_url, icon}` (icon = slug do ícone ou "" sem ícone).
  Links sempre no domínio oficial (protege contra páginas falsas).
- `owlock/core/data/brand_icons.json`: `{slug: {title, hex}}` (cor oficial da marca).
- `owlock/web/icons/brands/<slug>.svg`: desenho BRANCO (Simple Icons, CC0). Gerados por `packaging/build_brand_icons.py`.

### Núcleo — `owlock/core/catalog.py` (sem dependências; lê os JSON com importlib.resources ou caminho relativo ao módulo)
- `normalize(text)`: casefold, sem acentos, só [a-z0-9] (remove espaços e pontuação). "Epic Games" → "epicgames"; "gov.br" → "govbr".
- `Service` (dataclass): key, name, aliases, login_url, default_url, icon, color (hex da marca ou ""), builtin (bool), customized (bool).
- `Catalog(custom_services, url_overrides)`: `all()` (embutidos com overrides aplicados + personalizados, ordem alfabética),
  `get(key)`, `match(name) -> Service|None` (igualdade de normalize com nome ou apelido; personalizados têm prioridade),
  `suggest(text, limit=6)` (prefixo do nome/apelido normalizado; depois "contém"; sem repetidos), `icons()` (lista de {slug, title}).
- Conteúdo cifrado do cofre ganha `"services": {"custom": [...], "overrides": {key: url}}`; sem a chave → vazio.
  Personalizado: `{key: "custom-<uuid>", name, aliases: [str], login_url, icon: "" ou slug existente}`.
  `Vault.services` (dict) e `Vault.update_services(custom, overrides)` com rollback como os outros.
- `Entry` ganha `icon: str = ""` — "" = automático (pelo nome via catálogo), "none" = letra, ou um slug existente.

### Api (acréscimos e mudanças)
```
lookup_service(name) -> {ok, match: ServiceSummary|null, suggestions: [ServiceSummary]}         # exige cofre aberto
    ServiceSummary = {key, name, aliases, login_url, default_url, icon, icon_url, color, builtin, customized}
    icon_url = "icons/brands/<slug>.svg" ou null; color = hex da marca ou null
list_services(query="") -> {ok, services: [ServiceSummary]}
save_service(data) -> {ok, service} | name_required | name_too_long (>40) | name_exists | invalid_url | invalid_icon | too_many (>200) | not_found | save_failed
    data = {key?, name, aliases: [str] (máx 10, cada até 40), login_url, icon}
    sem key = novo personalizado; key embutida = só altera o link (override; nome/apelidos/ícone ignorados);
    key personalizada = edita tudo. URL validada como em save_entry (só http/https).
reset_service(key) -> {ok, service} | not_found        # embutido: remove o override
delete_service(key) -> {ok} | not_found | builtin_service   # só personalizados
brand_icons() -> {ok, icons: [{slug, title, icon_url, color}]}   # não exige cofre aberto
EntrySummary ganha: icon (valor salvo), icon_url, icon_color, service_key (serviço reconhecido ou null)
    resolução: icon "none" → sem ícone; slug → esse ícone; "" → ícone do serviço reconhecido pelo nome (se tiver)
save_entry(data): data ganha icon ("" | "none" | slug existente; senão invalid_icon)
open_url(id): se a conta não tem url, usa o login_url do serviço reconhecido (resposta inclui "source": "entry"|"library");
    sem nenhum dos dois → no_url.
```

### Interface
- Ícone da conta (lista, detalhe, formulário): ladrilho arredondado no estilo de ícone de app do iPhone, com o fundo na cor
  da marca (se a cor for muito escura, usar grafite #2A2B31 com borda hairline) e o desenho branco (img src=icon_url).
  Sem ícone → letra com o degradê da categoria (como hoje).
- Formulário: ao digitar o Serviço, lista de sugestões (ícone + nome + domínio) estilo iOS abaixo do campo, navegável por
  teclado (↑ ↓ Enter Esc). Escolher uma sugestão (ou correspondência exata ao sair do campo) preenche o nome e o Site
  SE o Site estiver vazio ou ainda for o link preenchido automaticamente; mostra a nota "Link preenchido pela biblioteca".
  Campo "Ícone": Automático / Letra / Escolher… (grade pesquisável com os ícones de brand_icons).
- Detalhe: se a conta não tem site mas o serviço é reconhecido, a linha Site mostra o domínio da biblioteca com o rótulo
  "da biblioteca" e o botão "Abrir login".
- Ajustes > "Biblioteca de links" (e acesso pela tela Categorias? não — só Ajustes): busca, lista agrupada (ícone, nome,
  domínio, selo "Personalizado" ou "Alterado"), toque abre editor: embutido = editar link + "Restaurar link padrão";
  personalizado = nome, apelidos (separados por vírgula), link, ícone (Automático/Letra/grade) + Excluir (vermelho, confirmação).
  Botão "Adicionar serviço".

## Fase 6 — v0.5: cofre v2 com Chave Secreta

### Objetivo e modelo de ameaça
Proteger o cofre quando o ARQUIVO sai do computador (nuvem, pendrive, backup vazado): sem a Chave Secreta, que fica
guardada no aparelho (Gerenciador de Credenciais do Windows / Keychain / Secret Service), não dá nem para tentar adivinhar a
senha mestra por força bruta. Não protege contra malware no próprio computador (fora do escopo, documentado no SECURITY.md).

### Chave Secreta
- 130 bits aleatórios (`secrets.token_bytes`), codificados em base32 RFC 4648 (A-Z, 2-7) → 26 caracteres de corpo
  + 2 caracteres de verificação (os 2 primeiros caracteres base32 de SHA-256(corpo ASCII)).
- Exibição: `OW2-XXXXX-XXXXX-XXXXX-XXXXX-XXXXXX-XX` (corpo em grupos 5-5-5-5-6, verificação no fim).
- `parse_secret_key(text)`: aceita minúsculas, espaços e hífens, prefixo opcional `OW2`; troca `0→O`, `1→I`, `8→B`;
  valida tamanho e verificação → `InvalidSecretKeyError("Chave Secreta inválida: confira os caracteres.")`. Devolve os 16+ bytes do corpo
  decodificado (base32 de 26 caracteres → use o padding correto; guarde os 130 bits como bytes do decode).
- `secret_key_id(secret_bytes, vault_id)` = HMAC-SHA256(chave=secret_bytes, msg=b"owlock-v2-key-id|"+vault_id)[:8] em hex — fica no cabeçalho
  para diferenciar "Chave Secreta errada" de "senha errada".

### Derivação (owlock/core/crypto.py)
```
pw  = Argon2id(senha, salt, time_cost, memory_cost, parallelism) → 32 bytes   (como hoje)
sk  = HKDF-SHA256(ikm=secret_bytes, salt=vault_id_bytes, info=b"owlock-v2 secret key", length=32)
KEK = HKDF-SHA256(ikm=pw || sk,     salt=salt,           info=b"owlock-v2 kek",        length=32)
```
(HKDF de `cryptography.hazmat.primitives.kdf.hkdf`.) Chave do cofre (vault key) = 32 bytes aleatórios, criada uma vez.

### Arquivo v2 (JSON)
```json
{
  "format": "owlock-vault", "version": 2, "vault_id": "<uuid4 hex>",
  "kdf": {"name": "argon2id", "salt": "<b64>", "time_cost": 3, "memory_cost": 65536, "parallelism": 4},
  "secret_key": {"id": "<16 hex>"},
  "cipher": {"name": "aes-256-gcm"},
  "key":     {"nonce": "<b64>", "ciphertext": "<b64>"},
  "meta":    {"nonce": "<b64>", "ciphertext": "<b64>"},
  "entries": [{"id": "<uuid hex>", "nonce": "<b64>", "ciphertext": "<b64>"}]
}
```
- `key` = AES-GCM(KEK, vault_key), AAD = JSON canônico (sort_keys, separators compactos) de
  {format, version, vault_id, kdf, secret_key, cipher}. Trocar a senha muda salt → só `key` é refeito.
- `meta` = AES-GCM(vault_key, JSON {"categories", "settings", "services"}), AAD = b"owlock-v2|" + vault_id + b"|meta".
- cada entrada = AES-GCM(vault_key, JSON Entry.to_dict()), AAD = b"owlock-v2|" + vault_id + b"|entry|" + id;
  o id dentro do JSON decifrado tem de ser igual ao id externo (senão corrompido). Ids externos não podem repetir.
- Nonce novo para tudo que for cifrado em cada save (simples e seguro; otimização fica para depois).
- Mesmas proteções de hoje: limites dos parâmetros kdf antes de derivar, escrita atômica, `.bak`, chmod 600, rollback em memória.
- Revela no arquivo só a QUANTIDADE de contas (ids aleatórios) — documentar no SECURITY.md.

### Guarda da Chave Secreta (owlock/core/keystore.py)
- Interface `SecretKeyStore`: `get(vault_id) -> bytes|None`, `set(vault_id, secret_bytes)`, `delete(vault_id)`, `description -> str`.
- `KeyringStore` (dependência nova `keyring>=25`): serviço "OwLock", usuário = vault_id, valor = Chave formatada.
  Se o keyring não tiver backend utilizável (ex.: `keyring.backends.fail.Keyring`, ou exceção), cai para
- `FileStore`: `~/.owlock/keys/<vault_id>.key`, permissão 600, escrita atômica. description em português
  ("Gerenciador de Credenciais do Windows", "Chaveiro do sistema", "arquivo protegido na sua pasta de usuário").
- `MemoryStore` para testes. `default_store()` escolhe Keyring ou File.

### Vault (API do núcleo)
- `Vault.create(path, password, store, kdf_params=None)` → cria v2 com Chave Secreta nova (guarda no store ANTES de gravar o arquivo);
  `vault.secret_key_formatted` disponível logo após criar/migrar (para o Kit), depois só via `reveal_secret_key(password)`.
- `Vault.open(path, password, store, secret_key: str|None = None)`:
  v2: Chave = parse(secret_key) se informada, senão store.get(vault_id); nenhuma → `SecretKeyRequiredError`;
  id não confere → `WrongSecretKeyError`; InvalidTag na `key` → `WrongPasswordError`; InvalidTag em meta/entrada → `VaultCorruptedError`.
  Se a chave veio informada e funcionou → store.set.
  v1: abre com o código atual (mantido como `_open_v1`) e MIGRA: gera Chave e vault key, `store.set` primeiro, copia o arquivo
  original para `<arquivo>.v1-backup` (shutil.copy2, sem sobrescrever se já existir: acrescente sufixo numérico), grava v2 atômico.
  Se store.set ou a gravação falhar → nada muda no arquivo original, erro `MigrationError`. Depois da migração `vault.migrated = True`
  e `vault.v1_backup_path` aponta para a cópia.
- `peek(path) -> {version, vault_id, secret_key_id}` (lê só o cabeçalho, sem senha; v1 devolve version 1).
- `change_master_password(current, new)`: novo salt, nova KEK, só refaz `key`; após salvar, sobrescreve o `.bak` com o arquivo novo
  (o backup não pode continuar abrindo com a senha antiga).
- `reveal_secret_key(password) -> str`: confere a senha (deriva e compara a KEK com compare_digest) e devolve a Chave formatada.
- Todo o resto (entradas, categorias, ajustes, serviços, histórico) igual por fora.

### Api
```
status() ganha: app_version, format_version (1|2|null), secret_key_required (bool: v2 e store sem a chave), key_storage (descrição)
unlock(password, secret_key=None) → ok + {migrated: bool, v1_backup_path?} | wrong_password | wrong_secret_key | secret_key_required
                                      | invalid_secret_key | migration_failed | corrupted | not_found
create_vault(password, confirm) → ok + {secret_key: "<formatada>"}  (só nesta resposta, para mostrar o Kit)
emergency_kit(password) → {ok, secret_key, vault_id, vault_path, key_storage} | wrong_password      (exige cofre aberto)
save_emergency_kit(password) → {ok, path} | wrong_password | cancelled | save_failed
    abre diálogo "Salvar como" (callable injetável `save_dialog(default_name) -> str|None`; no app real usa
    window.create_file_dialog(webview.SAVE_DIALOG)) e grava um HTML autossuficiente para imprimir (sem recursos externos,
    valores com html.escape): logo em texto, título "Kit de emergência do OwLock", data, Chave Secreta em fonte mono grande,
    campo em branco "Senha mestra: ______" para preencher à mão, caminho do cofre, instruções de recuperação e aviso para
    guardar em local seguro e nunca enviar por mensagem.
delete_v1_backup() → {ok} | not_found       (apaga só o caminho registrado na migração desta sessão)
```
- `app_version` vem de `owlock.__version__` = "0.5.0" (atualize também pyproject.toml).

### Interface
- Desbloqueio: se `secret_key_required`, mostra também o campo "Chave Secreta" (placeholder OW2-…, aceita colar),
  com explicação curta: "Este cofre foi criado em outro computador. Digite a Chave Secreta do seu Kit de emergência."
- Criação: depois de criar, tela "Seu Kit de emergência" (obrigatória de passar): mostra a Chave, botões "Salvar Kit" e
  "Copiar chave", e a confirmação "Guardei meu Kit em local seguro" (interruptor) que libera o botão "Continuar".
- Migração: mesma tela, com o texto "Seu cofre foi atualizado para o formato v2" e, abaixo, a cópia do cofre antigo com o botão
  "Apagar cópia antiga" (confirmação; avisa que ela ainda abre só com a senha).
- Ajustes > "Chave Secreta e Kit de emergência": onde a chave está guardada (key_storage), botão "Ver Kit de emergência"
  (pede a senha mestra num sheet) e "Salvar Kit". Versão do app no rodapé dos Ajustes.

## Fase 7 — v0.6: sempre à mão (bandeja), saúde das senhas, backups e favoritas

### 1. Preferências do aparelho (não sensíveis) — `owlock/app/config.py`
Algumas opções precisam valer com o cofre BLOQUEADO, então não podem ficar dentro do cofre cifrado.
Arquivo `~/.owlock/config.json` (ao lado do cofre padrão; para `--vault` custom, `<pasta do cofre>/owlock-config.json`),
escrita atômica, valores inválidos → padrão, nunca guarda nada do cofre (nem nomes de contas).
```
DesktopConfig: close_to_tray=True, lock_on_minimize=False, lock_on_session_lock=True,
               quick_search_hotkey=True, start_with_windows=False (espelho do registro; o registro é a fonte da verdade)
```

### 2. Integração com o Windows — `owlock/app/desktop/` (cada módulo com implementação nula fora do Windows)
- `tray.py`: ícone na bandeja com pystray (dependência `pystray>=0.19; sys_platform == "win32"`; no Linux/macOS sem bandeja).
  Ícone: owlock/web/img/owlock-icon.png; variante "bloqueado" com o LED da fechadura apagado (cinza) gerada em memória com Pillow
  (pystray já depende de Pillow). Título: "OwLock — aberto" / "OwLock — bloqueado".
  Menu: Abrir OwLock (padrão, clique duplo) · Busca rápida (Ctrl+Shift+Espaço) · Gerar senha e copiar · Bloquear agora
  (desabilitado se bloqueado) · ─ · Iniciar com o Windows (marcável) · ─ · Sair.
- `hotkey.py`: atalho global Ctrl+Shift+Space via ctypes `RegisterHotKey` numa thread própria com laço de mensagens
  (`GetMessageW`); `stop()` posta WM_QUIT na thread (`PostThreadMessageW`) e chama `UnregisterHotKey`. Se o registro falhar
  (atalho em uso por outro programa), registra o erro e segue sem atalho (status exposto: hotkey_available).
- `session.py`: detector de "Windows travado" por sondagem a cada 2 s: `OpenInputDesktop` + `GetUserObjectInformationW(UOI_NAME)`;
  nome diferente de "Default" (ou falha ao abrir) = travado. Na transição destravado→travado chama o callback. Thread daemon.
- `autostart.py`: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, valor "OwLock" = `"<exe>" --tray` (só quando empacotado,
  `sys.frozen`; rodando do código-fonte: `"<pythonw>" -m owlock --tray`). `is_enabled()`, `enable()`, `disable()` com winreg.
- Tudo isso orquestrado por `owlock/app/desktop/controller.py` (`DesktopController`), que recebe a Api, a janela principal,
  a janela de busca rápida e funções injetáveis — testável sem Windows com objetos falsos.

### 3. Janelas e ciclo de vida (`main.py`)
- `owlock --tray`: inicia escondido na bandeja (usado pela inicialização com o Windows).
- Janela principal: com close_to_tray, fechar (evento `closing`) esconde a janela e devolve False (cancela o fechamento);
  só "Sair" (menu da bandeja) encerra de verdade (api.shutdown, para threads, remove o ícone). Sem bandeja (fora do Windows), fechar encerra.
- Minimizar (evento `minimized`) com lock_on_minimize → api.lock() e a interface recebe o evento de bloqueio.
- Windows travado com lock_on_session_lock → api.lock().
- Busca rápida: segunda janela pywebview criada escondida no início, 560x420, sem redimensionar, sempre por cima, carregando
  `index.html#quick` com a MESMA Api. Atalho/menu: se o cofre está bloqueado → mostra a janela principal no desbloqueio;
  senão → mostra a busca rápida centralizada e com foco. Esc ou perder o foco → esconde.
- Avisar a interface de mudanças vindas de fora (bloqueio pela bandeja/sessão): `window.evaluate_js("window.owlockEvent && owlockEvent('locked')")`.
- "Gerar senha e copiar": gera 20 caracteres e copia com a mesma limpeza automática (não exige cofre aberto; prazo = 30 s se bloqueado).

### 4. Saúde das senhas (Api, sem mudar o formato)
- `reused`: a senha atual é igual (comparação em memória) à de outra conta. `stale`: sem troca há mais de 365 dias
  (data = changed_at mais recente do histórico, senão created_at).
- EntrySummary ganha `reused: bool`, `reused_count: int` (quantas OUTRAS contas usam a mesma senha), `stale: bool`, `favorite: bool`.
- `attention` (filtro e stats) passa a incluir: score ≤ 2 OU reused OU stale. stats ganha `reused` e `stale` (contas).
- Nunca expor qual é a senha repetida, só a contagem e (em get_entry) `reused_with: [{id, service}]`.

### 5. Favoritas
- `Entry.favorite: bool = False` (no fim da dataclass). `toggle_favorite(id) -> {ok, favorite}`.
- list_entries: favoritas primeiro (depois ordem por serviço). Filtro novo `"favorites"`.

### 6. Backups com histórico (núcleo)
- Pasta `<cofre>.backups/` (permissão 700). Snapshot = cópia do arquivo v2 atual, nome `AAAAMMDD-HHMMSS.vault` (UTC).
- Cria snapshot: no save se o último tiver mais de 1 hora (antes de gravar o novo); sempre antes de restaurar; sempre após migrar.
  Mantém os 20 mais recentes.
- Troca de senha mestra: TODOS os snapshots são atualizados para a nova senha (troca só `kdf.salt` e o bloco `key`, porque a
  chave do cofre é a mesma e as entradas não dependem do salt) — snapshot inválido/de outro cofre é ignorado e reportado.
  Assim nenhum backup continua abrindo com a senha antiga.
- `Vault.list_backups() -> [{id, created_at, size, entries}]` (entries = tamanho da lista `entries` do JSON, sem decifrar).
- `Vault.restore_backup(id, password)`: confere a senha, valida que o snapshot é do mesmo cofre (vault_id) e abre com a chave em
  memória; snapshot do estado atual antes; substitui o arquivo atomicamente; recarrega em memória.
- Api: `list_backups()`, `restore_backup(id, password)` → ok | wrong_password | not_found | corrupted | save_failed.

### 7. Api — desktop
```
get_desktop_config() -> {ok, config, platform: "windows"|"other", tray_available, hotkey_available}   # não exige cofre aberto
save_desktop_config(data) -> {ok, config}   # aplica na hora (autostart liga/desliga o registro)
quick_hide() -> {ok}                         # a janela de busca rápida se esconde (chamado pela própria interface)
quick_open_main(id?) -> {ok}                 # mostra a janela principal (opcional: selecionando a conta)
generate_and_copy() -> {ok, clear_in, strength}  # para a bandeja e para a busca rápida
```
Esses métodos chamam callbacks registrados pelo DesktopController (`api.attach_desktop(controller)`); sem controller (devserver/testes)
quick_hide/quick_open_main devolvem ok sem efeito.

### 8. Interface
- Lista: estrela (favorita) na linha e no detalhe (toggle com animação de mola); filtro "Favoritas" no segmented (Todas · Favoritas · Com 2FA · Atenção).
- Saúde: no detalhe, avisos em pílulas: vermelho "Repetida em N contas" (lista os serviços em get_entry.reused_with, clicáveis),
  âmbar "Sem troca há mais de 1 ano". LED da linha considera reused/stale. Cartão de resumo "precisa de atenção" usa o novo total;
  tooltip/legenda com o detalhamento (fracas, repetidas, antigas).
- Ajustes > "Backups": lista agrupada (data por extenso, nº de contas), "Restaurar" com sheet pedindo a senha e aviso
  "O estado atual também vira um backup antes da restauração."
- Ajustes > "Área de trabalho" (só se platform == "windows"): interruptores Manter na bandeja ao fechar · Bloquear ao minimizar ·
  Bloquear ao travar o Windows · Atalho Ctrl+Shift+Espaço para busca rápida (mostra aviso se hotkey_available=false) · Iniciar com o Windows.
- Rota `#quick` (busca rápida): layout compacto 560x420 sem barra lateral: campo de busca grande com foco, lista de até 8 resultados
  (ícone, serviço, login; favoritas primeiro), ↑ ↓ para navegar, Enter = copiar senha, Ctrl+Enter = copiar login, ações visíveis por linha
  (Copiar login, Copiar senha, Abrir site), toast compacto; Esc chama quick_hide; após copiar a senha, esconde em 600 ms.
  Se bloqueado (locked), mostra mensagem curta e botão "Abrir OwLock" (quick_open_main).
- `window.owlockEvent(nome)`: 'locked' leva à tela de desbloqueio (janela principal) ou à mensagem de bloqueado (#quick).
