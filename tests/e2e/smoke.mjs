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

    // (f) nova conta
    await page.click('#new-entry');
    await page.waitForSelector('#form-service');
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
    await page.click('#confirm-delete');
    await waitRows(page, 6, 'depois de excluir');
    log('exclusão pede confirmação e remove a conta (volta a 6)');

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
    await clickRow(page, 'Google');
    await page.waitForFunction(() => document.querySelector('#detail-name')?.textContent === 'Google');
    await shot(page, '08-celular-detalhe');
    await page.click('#back');
    await page.waitForSelector('#new-entry');
    log('layout de celular: lista, detalhe e voltar');
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
