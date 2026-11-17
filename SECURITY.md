# Segurança do OwLock

Este documento explica como o OwLock protege suas senhas, contra o que ele protege e, com a mesma clareza, contra o que ele **não** protege.

## Resumo

- O cofre é um único arquivo cifrado com **AES-256-GCM**.
- Abrir o cofre exige **duas coisas**: a **senha mestra** (que só você sabe) e a **Chave Secreta** (aleatória, guardada no seu computador).
- A senha mestra passa pelo **Argon2id** (64 MiB de memória, 3 passagens), o que torna cada tentativa de adivinhação lenta e cara.
- Nada é enviado pela rede: o aplicativo não tem servidor, conta na nuvem nem telemetria.

## Como as chaves são derivadas (cofre v2)

```
pw  = Argon2id(senha mestra, salt)                                   → 32 bytes
sk  = HKDF-SHA256(Chave Secreta, salt = id do cofre, "owlock-v2 secret key")
KEK = HKDF-SHA256(pw || sk, salt, "owlock-v2 kek")                   → chave que tranca a chave do cofre
```

- A **chave do cofre** (32 bytes aleatórios) cifra os dados e é guardada no arquivo **trancada pela KEK**.
- Trocar a senha mestra só refaz esse "cadeado" (novo salt e nova KEK): os dados não são recifrados e o backup `.bak` é atualizado para não continuar abrindo com a senha antiga.
- Cada conta é cifrada separadamente, com o próprio identificador autenticado (não dá para trocar o conteúdo de uma conta pelo de outra sem que o app perceba).
- O cabeçalho do arquivo (parâmetros do Argon2id, salt, identificadores) é autenticado: qualquer alteração faz a abertura falhar.

## A Chave Secreta

São 130 bits aleatórios, mostrados no formato `OW2-XXXXX-XXXXX-XXXXX-XXXXX-XXXXXX-XX` (os dois últimos caracteres detectam erros de digitação).

- Fica guardada no **Gerenciador de Credenciais do Windows** (ou no chaveiro do sistema no macOS/Linux; sem chaveiro disponível, num arquivo com permissão restrita na sua pasta de usuário).
- **Por que existe:** se o arquivo do cofre vazar (backup na nuvem, pendrive perdido), um atacante não consegue nem começar a adivinhar a senha mestra, porque também precisaria da Chave Secreta — e 130 bits aleatórios não se adivinham.
- **Kit de emergência:** na criação do cofre o app mostra a Chave Secreta e oferece salvar uma página para imprimir. Ela é necessária para abrir o cofre em outro computador ou depois de reinstalar o sistema. Guarde o Kit em local seguro e nunca o envie por mensagem.

## Na interface

- A lista de contas nunca recebe senhas: cada senha só é lida quando você clica em **Mostrar** ou **Copiar**.
- A cópia é feita pelo Python, e a área de transferência é limpa depois do prazo escolhido (só se ainda contiver o que o app copiou).
- O cofre bloqueia sozinho após o tempo escolhido sem uso; ao bloquear, o aplicativo descarta as chaves e os dados abertos (veja a limitação sobre memória abaixo).
- Textos vindos do cofre nunca são inseridos como HTML (proteção contra injeção de código); a página tem uma Content-Security-Policy restrita e não carrega nada da internet.
- O botão de abrir site aceita apenas endereços `http`/`https`, e os links da biblioteca usam o domínio oficial de cada serviço.

## Backups e área de trabalho

- **Backups com histórico** ficam na pasta `<cofre>.backups/`, também cifrados e protegidos pela Chave Secreta. Ao trocar a senha mestra, todos os backups são atualizados para a senha nova; um backup que não puder ser atualizado é apagado, para nenhum continuar abrindo com a senha antiga.
- **Bloquear ao travar o Windows:** o app verifica a cada 2 segundos se a tela de bloqueio está ativa. A tela de permissão de administrador (UAC) também conta como "travado", então o cofre pode bloquear quando ela aparece — escolha deliberada pelo lado seguro.
- **Preferências do aparelho** (bandeja, atalho, iniciar com o Windows) ficam em `config.json`, fora do cofre, porque precisam valer com o cofre bloqueado. Esse arquivo não contém nenhum dado do cofre.
- A **busca rápida** só mostra contas com o cofre aberto, e o bloqueio automático continua valendo com o app escondido na bandeja.

## O que o OwLock NÃO protege

- **Computador comprometido.** Um keylogger ou malware rodando com o seu usuário pode capturar a senha mestra ao ser digitada, ler a Chave Secreta guardada no sistema e ler os dados enquanto o cofre está aberto. Nenhum gerenciador local resolve isso.
- **Memória do processo.** Enquanto desbloqueado, os dados ficam na memória do aplicativo. O Python não permite apagar a memória de forma garantida.
- **Senha mestra fraca + Chave Secreta vazada juntas.** Se alguém tiver o arquivo **e** a Chave Secreta (por exemplo, uma foto do Kit), a proteção volta a depender só da força da senha mestra.
- **Perda das duas coisas.** Sem a senha mestra ou sem a Chave Secreta, o cofre não pode ser aberto — nem por você, nem pelo autor do projeto. Não existe recuperação.
- **Metadados do arquivo.** O arquivo revela a quantidade de contas (cada conta tem um identificador aleatório), a data de modificação e o tamanho aproximado. Nomes de serviços, logins, senhas, categorias e links ficam cifrados.
- **Remoção de contas por quem edita o arquivo.** Quem tiver acesso de escrita ao arquivo pode apagar uma conta inteira dele sem que isso seja detectado (não pode ler nem alterar o conteúdo). Mantenha backups.
- **Auditoria.** É um projeto pessoal, sem auditoria independente. Para uso crítico, considere também soluções auditadas, como Bitwarden ou KeePassXC.

## Cofres antigos (v1)

Cofres criados antes da v0.5 são convertidos automaticamente para o v2 na primeira abertura. Uma cópia do arquivo antigo é guardada ao lado (`.v1-backup`); ela ainda abre só com a senha mestra, então apague-a depois de guardar o Kit de emergência (o app oferece o botão).

## Relatar uma vulnerabilidade

Encontrou um problema de segurança? Por favor, não abra uma issue pública: use a aba **Security → Report a vulnerability** do repositório no GitHub para enviar um relato privado.
