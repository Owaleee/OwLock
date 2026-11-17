// Teste de fumaça ponta a ponta: interface + devserver, com Chrome headless.
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const BASE = process.env.OWLOCK_URL || 'http://127.0.0.1:8765';
const CHROME = process.env.CHROME_PATH || '/usr/bin/google-chrome';
const PASSWORD = process.env.OWLOCK_PASSWORD || 'senha-de-teste-123';
const SHOTS = process.env.OWLOCK_SHOTS || '/tmp/owlock-shots';
const TIMEOUT = 15000;

fs.mkdirSync(SHOTS, { recursive: true });

const problems = [];
let step = 0;
const shots = [];

function log(message) {
  step += 1;
  console.log(`ok ${step} - ${message}`);
}

function fail(message) {
  throw new Error(message);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function rowCount(page) {
  return page.$$eval('#entry-list .row', (rows) => rows.length);
}

async function waitRows(page, expected, what) {
  try {
    await page.waitForFunction(
      (n) => document.querySelectorAll('#entry-list .row').length === n,
      { timeout: TIMEOUT },
      expected,
    );
  } catch {
    fail(`${what}: esperava ${expected} contas, encontrei ${await rowCount(page)}`);
  }
}

async function shot(page, name) {
  await sleep(900); // deixa as animações terminarem
  const file = `${SHOTS}/${name}.png`;
  await page.screenshot({ path: file });
  shots.push(file);
}

async function clickRow(page, service) {
  const clicked = await page.evaluate((name) => {
    for (const row of document.querySelectorAll('#entry-list .row')) {
      if (row.querySelector('.row-name')?.textContent === name) {
        row.click();
        return true;
      }
    }
    return false;
  }, service);
  if (!clicked) fail(`conta "${service}" não está na lista`);
}

async function clickCategory(page, name) {
  const ok = await page.evaluate((wanted) => {
    for (const pill of document.querySelectorAll('#cat-strip .cat-pill')) {
      if (pill.querySelector('.cat-name')?.textContent === wanted) {
        pill.click();
        return true;
      }
    }
    return false;
  }, name);
  if (!ok) fail(`categoria "${name}" não está na faixa`);
}

async function rowNames(page) {
  return page.$$eval('#entry-list .row .row-name', (els) => els.map((el) => el.textContent).sort());
}

async function pillCounts(page) {
  return page.$$eval('#cat-strip .cat-pill', (pills) => Object.fromEntries(
    pills.map((p) => [p.querySelector('.cat-name')?.textContent || '+', p.querySelector('.cat-count')?.textContent ?? ''])));
}

async function chooseInForm(page, name) {
  const ok = await page.evaluate((wanted) => {
    for (const pill of document.querySelectorAll('#form-categories .cat-pill')) {
      if (pill.querySelector('.cat-name')?.textContent === wanted) {
        pill.click();
        return true;
      }
    }
    return false;
  }, name);
  if (!ok) fail(`categoria "${name}" não está no formulário`);
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu'],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    page.on('pageerror', (error) => problems.push(`erro de página: ${error.message}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') problems.push(`console: ${msg.text()}`);
    });
    page.on('request', (request) => {
      const url = request.url();
      if (!url.startsWith(BASE) && !url.startsWith('data:')) problems.push(`requisição externa: ${url}`);
    });
    page.setDefaultTimeout(TIMEOUT);

    // (a) desbloqueio
    await page.goto(BASE, { waitUntil: 'load' });
    await page.waitForSelector('#unlock-password');
    log('tela de desbloqueio apareceu');
    await shot(page, '01-desbloqueio');

    await page.type('#unlock-password', 'senha-errada-xyz');
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#unlock-error')?.textContent.length > 0);
    log('senha errada mostra erro');

    await page.click('#unlock-password', { clickCount: 3 });
    await page.type('#unlock-password', PASSWORD);
    await page.keyboard.press('Enter');
    await page.waitForSelector('#entry-list .row');
    log('cofre desbloqueado');

    // (b) 6 contas
    await waitRows(page, 6, 'lista inicial');
    log('6 contas na lista');
    const stats = await page.$eval('.stats-desktop', (el) => el.textContent);
    if (!stats.includes('6') || !/2 etapas/.test(stats)) fail(`cartões de resumo inesperados: ${stats}`);
    log('cartões de resumo visíveis');
    await shot(page, '02-principal');

    // ícones de marca na lista
    const iconInfo = await page.evaluate(() => {
      const out = {};
      for (const row of document.querySelectorAll('#entry-list .row')) {
        const name = row.querySelector('.row-name').textContent;
        out[name] = { src: row.querySelector('.acc-icon img')?.getAttribute('src') || null, mono: row.querySelector('.mono-badge')?.textContent || null };
      }
      return out;
    });
    if (iconInfo.Discord?.src !== 'icons/brands/discord.svg') fail(`Discord deveria mostrar o ícone da marca: ${JSON.stringify(iconInfo.Discord)}`);
    if (iconInfo['Epic Games']?.src || iconInfo['Epic Games']?.mono !== 'E') fail(`Epic Games (icon "none") deveria mostrar a letra: ${JSON.stringify(iconInfo['Epic Games'])}`);
    const brokenImages = await page.$$eval('#entry-list .acc-icon', (tiles) => tiles.filter((t) => t.classList.contains('broken')).length);
    if (brokenImages) fail('algum ícone de marca não carregou');
    log('lista mostra ícones de marca (Discord) e a letra quando o ícone é "none" (Epic Games)');
    await shot(page, '19-lista-icones');

    // (c) busca
    await page.type('#search', 'steam');
    await waitRows(page, 1, 'busca "steam"');
    log('busca "steam" retorna 1 conta');
    await page.click('#search', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    await waitRows(page, 6, 'busca limpa');

    await page.click('#tab-attention');
    await page.waitForFunction(() => document.querySelector('.segmented').dataset.index === '2');
    await waitRows(page, 1, 'aba Atenção');
    await page.click('#tab-all');
    await waitRows(page, 6, 'aba Todas');
    log('segmented control troca de aba (Atenção = 1 conta)');

    // categorias: faixa, filtro e combinação com a aba Atenção
    const counts = await pillCounts(page);
    if (!('Todas' in counts) || !('Jogos' in counts) || counts.Todas !== '6') fail(`faixa de categorias inesperada: ${JSON.stringify(counts)}`);
    log(`faixa de categorias com contadores ${JSON.stringify(counts)}`);
    // setas, arrastar e última categoria alcançável
    if (!(await page.$eval('#cat-strip', (el) => el.scrollWidth > el.clientWidth))) fail('a faixa deveria ter conteúdo escondido em 1280x800');
    await page.waitForSelector('#cat-next.is-on');
    await sleep(700); // deixa a rolagem inicial assentar
    if (await page.$('#cat-prev.is-on')) fail('seta esquerda não deveria aparecer no início');
    for (let i = 0; i < 10 && (await page.$('#cat-next.is-on')); i += 1) {
      await page.click('#cat-next');
      await sleep(500);
    }
    const lastVisible = await page.evaluate(() => {
      const strip = document.querySelector('#cat-strip').getBoundingClientRect();
      const last = document.querySelector('#cat-add').getBoundingClientRect();
      return last.right <= strip.right + 1 && last.left >= strip.left;
    });
    if (!lastVisible) fail('a última pílula (+) não ficou alcançável pela seta');
    await page.waitForSelector('#cat-prev.is-on');
    log('seta › leva até a última categoria; seta ‹ aparece');
    await shot(page, '15-faixa-setas');
    for (let i = 0; i < 10 && (await page.$('#cat-prev.is-on')); i += 1) {
      await page.click('#cat-prev');
      await sleep(500);
    }
    const box = await (await page.$('#cat-strip .cat-pill:nth-child(2)')).boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 - 40, box.y + box.height / 2, { steps: 4 });
    await page.mouse.move(box.x + box.width / 2 - 120, box.y + box.height / 2, { steps: 6 });
    await page.mouse.up();
    await sleep(300);
    const afterDrag = await page.evaluate(() => ({
      left: document.querySelector('#cat-strip').scrollLeft,
      all: document.querySelector('#cat-all').getAttribute('aria-pressed'),
      pressed: document.querySelectorAll('#cat-strip .cat-pill[aria-pressed="true"]').length,
    }));
    if (afterDrag.left <= 0 || afterDrag.all !== 'true' || afterDrag.pressed !== 1) fail(`arrastar a faixa deveria rolar sem clicar: ${JSON.stringify(afterDrag)}`);
    log('arrastar a faixa rola sem disparar clique');
    for (let i = 0; i < 10 && (await page.$('#cat-prev.is-on')); i += 1) {
      await page.click('#cat-prev');
      await sleep(500);
    }

    await clickCategory(page, 'Jogos');
    await waitRows(page, 3, 'categoria Jogos');
    const games = (await rowNames(page)).join(',');
    if (games !== 'Discord,Epic Games,Steam') fail(`contas de Jogos inesperadas: ${games}`);
    log('categoria Jogos filtra Steam/Discord/Epic');
    await shot(page, '12-faixa-categorias');
    await page.click('#tab-attention');
    await waitRows(page, 1, 'Jogos + Atenção');
    if ((await rowNames(page))[0] !== 'Discord') fail('Jogos + Atenção deveria mostrar só o Discord');
    log('Jogos + Atenção = Discord');
    await page.click('#tab-all');
    await clickCategory(page, 'Jogos');
    await waitRows(page, 6, 'categoria desmarcada');

    // (d) Discord com força fraca
    await clickRow(page, 'Discord');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Discord');
    const strength = await page.$eval('#strength-label', (el) => el.textContent);
    if (!/fraca/i.test(strength)) fail(`rótulo de força inesperado: "${strength}"`);
    log(`Discord mostra força fraca ("${strength}")`);

    // (e) mostrar senha
    const before = await page.$eval('#password-display', (el) => el.textContent);
    if (before.includes('discord2021')) fail('a senha apareceu no DOM antes de clicar em Mostrar');
    await page.click('#reveal-toggle');
    await page.waitForFunction(() => document.querySelector('#password-display')?.textContent === 'discord2021');
    log('Mostrar revela "discord2021" no DOM');
    await shot(page, '03-senha-revelada');
    await page.click('#reveal-toggle');
    await page.waitForFunction(() => !document.querySelector('#password-display').textContent.includes('discord2021'));
    log('Ocultar remove a senha do DOM');

    // copiar senha (anel de contagem)
    await page.click('#copy-password');
    // Sem área de transferência no sistema (ex.: servidor sem xclip) a Api devolve erro: a interface deve avisar.
    await page.waitForFunction(() => document.querySelector('#copy-password .ow-count')
      || [...document.querySelectorAll('.toast')].some((t) => /transfer/.test(t.textContent)));
    const ring = await page.$('#copy-password .ow-count');
    log(ring ? 'Copiar senha mostra o anel de contagem' : 'Copiar senha sem área de transferência mostra aviso (ambiente sem xclip)');
    await page.waitForSelector('.toast');
    await shot(page, '09-toast');

    // (f) nova conta
    await page.click('#new-entry');
    await page.waitForSelector('#form-service');
    const formCats = await page.evaluate(() => {
      const list = document.querySelector('#form-categories');
      const card = document.querySelector('.modal').getBoundingClientRect();
      const pills = [...list.querySelectorAll('.cat-pill')];
      const rows = new Set(pills.map((p) => Math.round(p.getBoundingClientRect().top)));
      return {
        count: pills.length, rows: rows.size, overflow: list.scrollWidth > list.clientWidth + 1,
        inside: pills.every((p) => { const r = p.getBoundingClientRect(); return r.left >= card.left && r.right <= card.right; }),
      };
    });
    if (formCats.count < 7 || formCats.overflow || !formCats.inside || formCats.rows < 2) fail(`categorias no formulário deveriam quebrar linha: ${JSON.stringify(formCats)}`);
    log(`formulário mostra as ${formCats.count} categorias em ${formCats.rows} linhas, sem rolagem`);
    await shot(page, '04-formulario');
    await page.type('#form-service', 'Conta E2E');
    await page.type('#form-username', 'e2e@exemplo.com');
    await page.click('#form-generate');
    await page.waitForFunction(() => document.querySelector('#form-password').value.length >= 8);
    await page.waitForFunction(() => document.querySelector('#form-strength')?.textContent.length > 0);
    await page.click('#form-2fa');
    await page.type('#form-2fa-app', 'Authy');
    await page.click('#form-submit');
    await page.waitForSelector('#form-service', { hidden: true });
    await waitRows(page, 7, 'depois de criar');
    log('conta criada: 7 contas na lista');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Conta E2E');
    log('conta nova aparece selecionada');

    // Esc fecha o modal
    await page.click('#edit-entry');
    await page.waitForSelector('#form-service');
    const editPlaceholder = await page.$eval('#form-password', (el) => el.placeholder);
    if (!/manter a senha atual/.test(editPlaceholder)) fail('placeholder da edição não encontrado');
    await page.keyboard.press('Escape');
    await page.waitForSelector('#form-service', { hidden: true });
    log('Esc fecha o formulário; edição mostra placeholder de senha');

    // exclusão
    await page.click('#delete-entry');
    await page.waitForSelector('#confirm-delete');
    const lead = await page.$eval('.modal .lead', (el) => el.textContent);
    if (!lead.includes('Conta E2E') || !lead.includes('não pode ser desfeita')) fail(`texto de exclusão inesperado: ${lead}`);
    await shot(page, '10-modal-exclusao');
    await page.click('#confirm-delete');
    await waitRows(page, 6, 'depois de excluir');
    log('exclusão pede confirmação e remove a conta (volta a 6)');

    // biblioteca no formulário: sugestões, link, ícone
    await page.click('#new-entry');
    await page.waitForSelector('#form-service');
    await page.type('#form-service', 'epic');
    await page.waitForSelector('#service-suggestions:not([hidden]) .suggest-item');
    const sugText = await page.$eval('#service-suggestions', (el) => el.textContent);
    if (!sugText.includes('Epic Games')) fail(`sugestão "Epic Games" não apareceu: ${sugText}`);
    const listbox = await page.evaluate(() => ({
      role: document.querySelector('#service-suggestions').getAttribute('role'),
      options: document.querySelectorAll('#service-suggestions [role="option"]').length,
      expanded: document.querySelector('#form-service').getAttribute('aria-expanded'),
      combo: document.querySelector('#form-service').getAttribute('role'),
    }));
    if (listbox.role !== 'listbox' || listbox.options < 1 || listbox.expanded !== 'true' || listbox.combo !== 'combobox') fail(`ARIA das sugestões inesperada: ${JSON.stringify(listbox)}`);
    await shot(page, '21-sugestoes');
    await page.click('#service-suggestions .suggest-item');
    await page.waitForFunction(() => document.querySelector('#form-url').value.includes('epicgames.com/id/login'));
    if ((await page.$eval('#form-service', (el) => el.value)) !== 'Epic Games') fail('o nome deveria virar "Epic Games"');
    if (await page.$eval('#form-url-note', (el) => el.hidden)) fail('a nota "Link preenchido pela biblioteca" deveria aparecer');
    log('digitar "epic" sugere Epic Games; escolher preenche o Site (epicgames.com/id/login) e mostra a nota');
    await page.type('#form-url', 'x');
    if (!(await page.$eval('#form-url-note', (el) => el.hidden))) fail('a nota deveria sumir quando o Site é editado');
    log('editar o Site esconde a nota');

    await page.click('#form-service', { clickCount: 3 });
    await page.type('#form-service', 'steam');
    await page.waitForSelector('#service-suggestions:not([hidden]) .suggest-item');
    await page.keyboard.press('ArrowDown');
    const active = await page.$eval('#form-service', (el) => el.getAttribute('aria-activedescendant'));
    if (active !== 'suggest-opt-0') fail(`aria-activedescendant inesperado: ${active}`);
    await page.keyboard.press('Escape');
    if (!(await page.$eval('#service-suggestions', (el) => el.hidden))) fail('Esc deveria fechar as sugestões');
    if (!(await page.$('#form-service'))) fail('Esc nas sugestões não deveria fechar o formulário');
    log('teclado: ↓ ativa a opção (aria-activedescendant) e Esc fecha só as sugestões');

    await page.click('#form-url', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    await page.click('#form-service', { clickCount: 3 });
    await page.type('#form-service', 'gov');
    await page.waitForSelector('#service-suggestions:not([hidden])');
    await page.click('#form-username');
    await page.waitForFunction(() => document.querySelector('#form-url').value.includes('sso.acesso.gov.br'));
    log('digitar "gov" e sair do campo preenche sso.acesso.gov.br (correspondência exata)');

    await page.click('#form-icon-pick');
    await page.waitForSelector('#brand-grid .brand-cell');
    await page.keyboard.press('Escape');
    await page.waitForSelector('#brand-grid', { hidden: true });
    if ((await page.$eval('#form-icon-auto', (el) => el.getAttribute('aria-checked'))) !== 'true') fail('cancelar a grade deveria manter "Automático"');
    log('grade de ícones: Esc volta ao formulário e mantém o modo anterior');
    await page.click('#form-icon-pick');
    await page.waitForSelector('#brand-grid .brand-cell');
    await page.type('#icon-search', 'git');
    await page.waitForSelector('#brand-github');
    await shot(page, '22-grade-icones');
    await page.click('#brand-github');
    await page.waitForSelector('#brand-grid', { hidden: true });
    await page.waitForFunction(() => document.querySelector('#form-icon-preview img')?.getAttribute('src') === 'icons/brands/github.svg');
    if (!(await page.$eval('#form-url', (el) => el.value.includes('sso.acesso.gov.br')))) fail('o que foi digitado no formulário deveria continuar lá');
    await page.type('#form-password', 'Abc#12345xyz-ok');
    await page.click('#form-submit');
    await page.waitForSelector('#form-service', { hidden: true });
    await page.waitForFunction(() => document.querySelector('.detail-head img')?.getAttribute('src') === 'icons/brands/github.svg');
    log('ícone escolhido na grade (GitHub) aparece na conta salva');
    await page.click('#delete-entry');
    await page.waitForSelector('#confirm-delete');
    await page.click('#confirm-delete');
    await waitRows(page, 6, 'depois de excluir a conta com ícone manual');

    // categorias: criar, usar, excluir
    await page.click('#nav-categories');
    await page.waitForSelector('#category-group');
    if ((await page.$$('#category-group .cat-row')).length < 7) fail('tela Categorias deveria listar as categorias do seed');
    log('tela Categorias pela barra lateral lista as categorias');
    await shot(page, '16-tela-categorias');
    await page.waitForSelector('#settings-new-category');
    await page.click('#settings-new-category');
    await page.waitForSelector('#cat-name');
    await page.type('#cat-name', 'Estudos');
    await page.click('#cat-color-blue');
    await page.click('#cat-icon-school');
    await page.waitForFunction(() => document.querySelector('#cat-counter').textContent === '7/24');
    await shot(page, '13-editor-categoria');
    await page.click('#cat-save');
    await page.waitForSelector('#cat-name', { hidden: true });
    await page.waitForFunction(() => [...document.querySelectorAll('#category-group .cat-row')].some((r) => r.textContent.includes('Estudos')));
    log('categoria "Estudos" criada pelo editor (Azul, escola)');
    await shot(page, '14-ajustes-categorias');

    await page.click('#nav-vault');
    await page.waitForSelector('#entry-list .row');
    await clickRow(page, 'Google');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Google');
    await page.click('#edit-entry');
    await page.waitForSelector('#form-categories');
    await chooseInForm(page, 'Estudos');
    await page.click('#form-submit');
    await page.waitForSelector('#form-service', { hidden: true });
    await page.waitForFunction(() => document.querySelector('#detail-category')?.textContent === 'Estudos');
    const afterMove = await pillCounts(page);
    if (afterMove.Estudos !== '1') fail(`contador de Estudos inesperado: ${JSON.stringify(afterMove)}`);
    log('conta Google movida para Estudos (pílula no detalhe, contador 1)');
    await page.click('#detail-category');
    await waitRows(page, 1, 'clique na pílula do detalhe');
    log('pílula do detalhe filtra por Estudos');
    await clickCategory(page, 'Estudos');
    await waitRows(page, 6, 'categoria desmarcada');

    await page.click('#nav-categories');
    await page.waitForSelector('#category-group');
    await page.evaluate(() => {
      for (const row of document.querySelectorAll('#category-group .cat-row')) if (row.textContent.includes('Estudos')) row.click();
    });
    await page.waitForSelector('#cat-delete');
    await page.click('#cat-delete');
    await page.waitForSelector('#confirm-delete-category');
    const catLead = await page.$eval('.modal .lead', (el) => el.textContent);
    if (!/ficará sem categoria|ficarão sem categoria/.test(catLead)) fail(`texto de exclusão de categoria inesperado: ${catLead}`);
    await page.click('#confirm-delete-category');
    await page.waitForFunction(() => ![...document.querySelectorAll('#category-group .cat-row')].some((r) => r.textContent.includes('Estudos')));
    await page.click('#nav-vault');
    await page.waitForSelector('#entry-list .row');
    await clickRow(page, 'Google');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Google');
    if (await page.$('#detail-category')) fail('a conta Google deveria ter ficado sem categoria');
    log('categoria excluída: a conta ficou sem categoria');

    // ajustes de tempo
    await page.click('#nav-settings');
    await page.waitForSelector('#set-lock-row');
    await page.click('#set-lock-row');
    await page.waitForSelector('#set-lock-opt-1');
    const recommended = await page.$eval('.pick-row .badge-rec', (el) => el.closest('.pick-row').textContent);
    if (!recommended.includes('5 minutos')) fail(`opção recomendada inesperada: ${recommended}`);
    await shot(page, '17-seletor-tempo');
    await page.click('#set-lock-opt-1');
    await page.waitForFunction(() => document.querySelector('#protection-hint')?.textContent.includes('1 minuto'));
    log('bloqueio automático trocado para 1 minuto; texto atualizado');
    await page.click('#nav-vault');
    await page.waitForFunction(() => /^Bloqueia em (1:00|0:5\d)$/.test(document.querySelector('#timer-text')?.textContent || ''));
    log(`contador usa o novo tempo (${await page.$eval('#timer-text', (el) => el.textContent)})`);
    await page.click('#nav-settings');
    await page.waitForSelector('#set-lock-row');
    await page.click('#set-lock-row');
    await page.click('#set-lock-opt-5');
    await page.waitForFunction(() => document.querySelector('#protection-hint')?.textContent.includes('5 minutos'));
    await page.click('#nav-vault');
    await page.waitForSelector('#entry-list .row');

    // site e histórico de senhas
    await page.click('#new-entry');
    await page.waitForSelector('#form-service');
    await page.type('#form-service', 'Site E2E');
    await page.type('#form-password', 'SenhaAntiga#2026');
    await page.type('#form-url', 'ftp://exemplo.com');
    await page.click('#form-submit');
    await page.waitForFunction(() => document.querySelector('#form-url-error')?.textContent.length > 0);
    log('URL inválida mostra erro no campo Site');
    await page.click('#form-url', { clickCount: 3 });
    await page.type('#form-url', 'github.com');
    await page.click('#form-submit');
    await page.waitForSelector('#form-service', { hidden: true });
    await page.waitForFunction(() => document.querySelector('#detail-site')?.textContent === 'github.com');
    log('detalhe mostra o site "github.com"');
    const [openResponse] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/api/open_url')),
      page.click('#open-site'),
    ]);
    const opened = await openResponse.json();
    if (!opened.ok && opened.error !== 'open_failed') fail(`open_url devolveu ${JSON.stringify(opened)}`);
    log(`Abrir site respondeu ${opened.ok ? 'ok' : opened.error}`);
    await page.waitForSelector('#history-empty');
    log('conta nova: "Esta senha nunca foi alterada."');

    await page.click('#edit-entry');
    await page.waitForSelector('#form-password');
    await page.type('#form-password', 'SenhaNova#2027');
    await page.click('#form-submit');
    await page.waitForSelector('#form-service', { hidden: true });
    await page.waitForSelector('#history-group .hist-row');
    const badge = await page.$eval('#history-badge', (el) => el.textContent);
    if (badge !== '1 versão anterior') fail(`selo de histórico inesperado: ${badge}`);
    await page.click('#hist-show-0');
    await page.waitForFunction(() => document.querySelector('#hist-pw-0')?.textContent === 'SenhaAntiga#2026');
    log('troca de senha gera 1 versão; Mostrar revela a senha antiga');
    await page.evaluate(() => document.querySelector('#history-group').scrollIntoView({ block: 'center' }));
    await shot(page, '18-detalhe-historico');

    await clickRow(page, 'Discord');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Discord');
    await page.waitForFunction(() => document.querySelectorAll('#history-group .hist-row').length === 2);
    if ((await page.evaluate(() => document.body.textContent)).includes('SenhaAntiga#2026')) fail('senha antiga ficou na tela ao trocar de conta');
    log('Discord do seed tem 2 versões; senha antiga some ao trocar de conta');

    await clickRow(page, 'Site E2E');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Site E2E');
    await page.click('#delete-entry');
    await page.waitForSelector('#confirm-delete');
    await page.click('#confirm-delete');
    await waitRows(page, 6, 'depois de excluir a conta de site');

    // conta sem site: link da biblioteca
    await clickRow(page, 'Netflix');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Netflix');
    await page.waitForSelector('#detail-site-source');
    const libSite = await page.$eval('#detail-site-row', (el) => el.textContent);
    if (!libSite.includes('da biblioteca') || !libSite.includes('netflix.com') || !libSite.includes('Abrir login')) fail(`linha Site da biblioteca inesperada: ${libSite}`);
    const [loginResponse] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/api/open_url')),
      page.click('#open-login'),
    ]);
    const loginOpened = await loginResponse.json();
    if (!loginOpened.ok && loginOpened.error !== 'open_failed') fail(`open_url (biblioteca) devolveu ${JSON.stringify(loginOpened)}`);
    log(`Netflix sem site mostra "da biblioteca" + Abrir login (respondeu ${loginOpened.ok ? 'ok' : loginOpened.error})`);
    await shot(page, '20-detalhe-biblioteca');

    // biblioteca de links nos Ajustes
    await page.click('#nav-settings');
    await page.waitForSelector('#settings-library');
    await page.click('#settings-library');
    await page.waitForSelector('#library-group .lib-row');
    const libCount = (await page.$$('#library-group .lib-row')).length;
    if (libCount < 60) fail(`a biblioteca deveria listar os serviços embutidos (achei ${libCount})`);
    const libBadges = await page.$$eval('#library-group .badge-pill', (els) => els.map((e) => e.textContent));
    if (!libBadges.includes('Personalizado')) fail('o serviço personalizado do seed deveria ter o selo "Personalizado"');
    log(`biblioteca lista ${libCount} serviços, com selo "Personalizado" no do seed`);
    await shot(page, '23-biblioteca');

    await page.type('#library-search', 'steam');
    await page.waitForFunction(() => {
      const rows = [...document.querySelectorAll('#library-group .lib-row')];
      return rows.length >= 1 && rows.length < 5 && rows.every((r) => /steam/i.test(r.textContent));
    });
    log('busca "steam" filtra a biblioteca');
    const steamRow = '#library-group .lib-row[data-name="Steam"]';
    await page.click(steamRow);
    await page.waitForSelector('#service-url');
    if (await page.$('#service-name')) fail('serviço embutido só deveria editar o link');
    if (!(await page.$eval('#service-reset', (el) => el.disabled))) fail('Restaurar deveria estar desabilitado antes de alterar');
    await shot(page, '24-editor-servico');
    await page.click('#service-url', { clickCount: 3 });
    await page.type('#service-url', 'ftp://invalido.exemplo');
    await page.click('#service-submit');
    await page.waitForFunction(() => document.querySelector('#service-url-error')?.textContent.length > 0);
    log('link inválido mostra o erro do back-end no campo');
    await page.click('#service-url', { clickCount: 3 });
    await page.type('#service-url', 'steam.exemplo.com/entrar');
    await page.click('#service-submit');
    await page.waitForSelector('#service-url', { hidden: true });
    await page.waitForFunction(() => document.querySelector('#library-group .lib-row[data-name="Steam"]')?.textContent.includes('Alterado'));
    log('link alterado: selo "Alterado" aparece');
    await page.click(steamRow);
    await page.waitForSelector('#service-reset:not([disabled])');
    await page.click('#service-reset');
    await page.waitForSelector('#service-url', { hidden: true });
    await page.waitForFunction(() => !document.querySelector('#library-group .lib-row[data-name="Steam"]')?.textContent.includes('Alterado'));
    log('"Restaurar link padrão" remove o selo');

    await page.click('#library-search', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    await page.click('#library-add');
    await page.waitForSelector('#service-name');
    await page.type('#service-name', 'Meu Servidor');
    await page.type('#service-aliases', 'meu srv, painel');
    await page.type('#service-url', 'painel.exemplo.com');
    await shot(page, '25-editor-personalizado');
    await page.click('#service-submit');
    await page.waitForSelector('#service-name', { hidden: true });
    await page.type('#library-search', 'meu servidor');
    await page.waitForFunction(() => {
      const row = document.querySelector('#library-group .lib-row[data-name="Meu Servidor"]');
      return row && row.textContent.includes('Personalizado');
    });
    log('serviço personalizado "Meu Servidor" adicionado');

    await page.click('#nav-vault');
    await page.waitForSelector('#new-entry');
    await page.click('#new-entry');
    await page.waitForSelector('#form-service');
    await page.type('#form-service', 'meu servidor');
    await page.click('#form-username');
    await page.waitForFunction(() => document.querySelector('#form-url').value.includes('painel.exemplo.com'));
    log('"meu servidor" no formulário preenche o link do serviço personalizado');
    await page.keyboard.press('Escape');
    await page.waitForSelector('#form-service', { hidden: true });

    await page.click('#nav-settings');
    await page.waitForSelector('#settings-library');
    await page.click('#settings-library');
    await page.waitForSelector('#library-search');
    await page.type('#library-search', 'meu servidor');
    await page.waitForFunction(() => {
      const rows = document.querySelectorAll('#library-group .lib-row');
      return rows.length === 1 && rows[0].dataset.name === 'Meu Servidor';
    });
    await page.click('#library-group .lib-row[data-name="Meu Servidor"]');
    await page.waitForSelector('#service-delete');
    await page.click('#service-delete');
    await page.waitForSelector('#confirm-delete-service');
    await page.click('#confirm-delete-service');
    await page.waitForFunction(() => !document.querySelector('#library-group .lib-row[data-name="Meu Servidor"]'));
    log('serviço personalizado excluído com confirmação');
    await page.click('#library-back');
    await page.waitForSelector('#set-current');
    await page.click('#nav-vault');
    await page.waitForSelector('#entry-list .row');

    // (g) gerador, ajustes, celular
    await page.click('#nav-generator');
    await page.waitForFunction(() => document.querySelector('#gen-output')?.textContent.length >= 20);
    const first = await page.$eval('#gen-output', (el) => el.textContent);
    await page.click('#gen-again');
    await page.waitForFunction((old) => document.querySelector('#gen-output').textContent !== old, {}, first);
    log('gerador gera senhas diferentes');
    await shot(page, '05-gerador');

    await page.click('#nav-settings');
    await page.waitForSelector('#set-current');
    await page.waitForSelector('#vault-path');
    await shot(page, '06-ajustes');

    await page.click('#nav-vault');
    await page.waitForSelector('#entry-list .row');
    await page.setViewport({ width: 390, height: 844, isMobile: true, deviceScaleFactor: 2 });
    await page.waitForSelector('#entry-list .row'); // o modo celular recarrega a página
    await shot(page, '07-celular-lista');
    const stripScrolls = await page.$eval('#cat-strip', (el) => el.scrollWidth > el.clientWidth);
    if (!stripScrolls) fail('a faixa de categorias deveria rolar no celular');
    log('celular: faixa de categorias rolável');
    await clickRow(page, 'Google');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Google');
    await shot(page, '08-celular-detalhe');
    await page.click('#back');
    await page.waitForSelector('#new-entry');
    log('layout de celular: lista, detalhe e voltar');
    await page.click('#new-entry');
    await page.waitForSelector('#form-service');
    await shot(page, '11-celular-sheet');
    await page.keyboard.press('Escape');
    await page.waitForSelector('#form-service', { hidden: true });
    log('celular: formulário abre como sheet e Esc fecha');
    await page.click('#nav-settings');
    await page.waitForSelector('#settings-library');
    await page.click('#settings-library');
    await page.waitForSelector('#library-group .lib-row');
    await shot(page, '26-celular-biblioteca');
    await page.click('#nav-vault');
    await page.waitForSelector('#new-entry');
    await page.setViewport({ width: 1280, height: 800, isMobile: false, deviceScaleFactor: 1 });
    await page.waitForSelector('#nav-lock');

    // bloqueio
    await page.click('#nav-lock');
    await page.waitForSelector('#unlock-password');
    const leftovers = await page.evaluate(() => document.body.textContent.includes('discord2021') || !!document.querySelector('#entry-list'));
    if (leftovers) fail('restos do cofre no DOM depois de bloquear');
    log('Bloquear volta ao desbloqueio e limpa a tela');

    if (problems.length) fail(`problemas no navegador:\n  ${problems.join('\n  ')}`);
    log('nenhum erro de console e nenhuma requisição externa');
  } catch (error) {
    const pages = await browser.pages();
    await pages[pages.length - 1]?.screenshot({ path: `${SHOTS}/falha.png` }).catch(() => {});
    throw error;
  } finally {
    await browser.close();
  }
}

try {
  await main();
  console.log('\nScreenshots:');
  for (const file of shots) console.log(`  ${file}`);
  console.log('\nSMOKE OK');
} catch (error) {
  console.error(`\nFALHOU: ${error.message}`);
  if (problems.length) console.error(`Problemas observados:\n  ${problems.join('\n  ')}`);
  process.exit(1);
}
