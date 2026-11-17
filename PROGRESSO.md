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
