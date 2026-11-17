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
