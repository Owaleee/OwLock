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

## Próximas versões

### v0.6 — Saúde das senhas e proteção
- Aviso de **senhas repetidas** em mais de uma conta (no filtro "Atenção").
- Aviso de **senhas antigas**, sem troca há mais de um ano.
- **Bloquear ao minimizar** e **ao travar o Windows** (opções nos Ajustes).
- **Backups com histórico:** últimas versões cifradas do cofre, com "Restaurar backup".
- **Favoritas** no topo da lista.

### v0.7 — Produtividade
- **Atalhos de teclado:** Ctrl+F buscar, Ctrl+N nova conta, Ctrl+L bloquear, Ctrl+Shift+C copiar senha.
- **Importar CSV** do Chrome, Edge, Bitwarden e do gerenciador de senhas do Google; **exportar** com confirmação da senha mestra.
- **Códigos 2FA (TOTP)** opcionais, com aviso sobre guardar senha e 2FA no mesmo lugar.
- Links de login revisados para bancos e lojas (hoje alguns apontam para a página inicial).

### v0.8 — Extensão de navegador
- Extensão para Chrome e Edge que conversa com o app pelo *native messaging* do navegador, sem servidor e sem rede.
- Sugere as contas do site aberto e preenche login e senha **só quando o domínio confere** com o salvo (proteção contra páginas falsas).

### v1.0 — Celular
- App Android (e depois iOS) reaproveitando a mesma interface e o cofre v2.
- **Pareamento por QR code:** a Chave Secreta passa do computador para o celular sem passar pela internet.
- **Sincronização** pela pasta na nuvem escolhida pelo usuário (Google Drive, OneDrive), juntando as edições conta por conta.
- Depois: API própria opcional, que guarda apenas dados cifrados.

## Em paralelo (qualidade e distribuição)
- Teste ponta a ponta da interface rodando no GitHub Actions e selo de cobertura de testes.
- Página do projeto no GitHub Pages, com imagens e demonstração.
- Executável com assinatura digital (remove o aviso do SmartScreen) e instalador com atalho no menu Iniciar.
