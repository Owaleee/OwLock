# Roadmap do OwLock

O OwLock é um gerenciador de senhas local, offline e de código aberto. Este documento mostra o que já foi entregue e o que vem a seguir, em ordem de prioridade.

## Entregue

| Versão | Destaques |
|---|---|
| **v0.1.0** | Cofre cifrado (Argon2id + AES-256-GCM), contas com 2FA, busca, gerador de senhas, cópia com limpeza automática, bloqueio automático, troca da senha mestra |
| **v0.2.0** | Interface nova (HTML/CSS/JS em janela nativa) com visual inspirado no iOS, LEDs de status e logo própria |
| **v0.3.0** | Categorias, histórico de senhas, site da conta, tempos de bloqueio e de limpeza configuráveis |
| **v0.4.0** | Biblioteca de links com 67 serviços, sugestões ao digitar, ícones das plataformas embutidos e serviços personalizados |
| **v0.5.0** | Cofre v2 com Chave Secreta, chave do cofre separada, cada conta cifrada separadamente, Kit de emergência, migração automática e SECURITY.md |
| **v0.6.0** | Ícone na bandeja do Windows, busca rápida com atalho global (Ctrl+Shift+Espaço), iniciar com o Windows, bloquear ao minimizar e ao travar o Windows, senhas repetidas e antigas, favoritas e backups com histórico |
| **v0.7.0** | Importar CSV do Chrome, Edge, Google, Bitwarden e Firefox (com prévia, contas repetidas e opção de apagar o CSV), exportar com confirmação da senha mestra, atalhos de teclado e links de login revisados |
| **v1.0.0** | Instalador para Windows (menu Iniciar, desinstalador, atualização), uma única instância por cofre, revisão final e documentação |

## Próximas versões

### v1.1 — Códigos 2FA
- **Códigos 2FA (TOTP)** opcionais, com aviso sobre guardar senha e 2FA no mesmo lugar.
- Leitura do QR code do 2FA a partir de uma imagem.

### v1.2 — Extensão de navegador
- Extensão para Chrome e Edge que conversa com o app pelo *native messaging* do navegador, sem servidor e sem rede.
- Sugere as contas do site aberto e preenche login e senha **só quando o domínio confere** com o salvo (proteção contra páginas falsas).

### v2.0 — Celular
- App Android (e depois iOS) reaproveitando a mesma interface e o cofre v2.
- **Pareamento por QR code:** a Chave Secreta passa do computador para o celular sem passar pela internet.
- **Sincronização** pela pasta na nuvem escolhida pelo usuário (Google Drive, OneDrive), juntando as edições conta por conta.
- Depois: API própria opcional, que guarda apenas dados cifrados.

## Em paralelo (qualidade e distribuição)
- Teste ponta a ponta da interface rodando no GitHub Actions e selo de cobertura de testes.
- Página do projeto no GitHub Pages, com imagens e demonstração.
- Executável com assinatura digital (remove o aviso do SmartScreen); depende da compra de um certificado.
