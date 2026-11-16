import { call } from './bridge.js';

/* ======================================================================
   Utilidades de DOM (nunca usam innerHTML: textos entram via textContent)
   ====================================================================== */

const SVG_NS = 'http://www.w3.org/2000/svg';

const ICONS = {
  lock: [['rect', { x: 4, y: 11, width: 16, height: 10, rx: 3 }], ['path', { d: 'M8 11V7a4 4 0 0 1 8 0v4' }]],
  vault: [['rect', { x: 3, y: 4, width: 18, height: 16, rx: 4 }], ['circle', { cx: 12, cy: 12, r: 3 }], ['path', { d: 'M12 9V7M12 17v-2' }]],
  generator: [['path', { d: 'M4 4v6h6' }], ['path', { d: 'M20 20v-6h-6' }], ['path', { d: 'M20 10a8 8 0 0 0-14.5-3.5L4 10M4 14a8 8 0 0 0 14.5 3.5L20 14' }]],
  sliders: [['path', { d: 'M4 7h10M18 7h2M4 17h4M12 17h8' }], ['circle', { cx: 16, cy: 7, r: 2 }], ['circle', { cx: 10, cy: 17, r: 2 }]],
  search: [['circle', { cx: 11, cy: 11, r: 7 }], ['path', { d: 'M20 20l-3.5-3.5' }]],
  plus: [['path', { d: 'M12 5v14M5 12h14' }]],
  copy: [['rect', { x: 8, y: 8, width: 12, height: 12, rx: 3 }], ['path', { d: 'M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2' }]],
  back: [['path', { d: 'M15 6l-6 6 6 6' }]],
  close: [['path', { d: 'M6 6l12 12M18 6L6 18' }]],
  chevron: [['path', { d: 'M9 6l6 6-6 6' }]],
  none: [['circle', { cx: 12, cy: 12, r: 8 }], ['path', { d: 'M6.3 17.7L17.7 6.3' }]],
  user: [['circle', { cx: 12, cy: 8, r: 4 }], ['path', { d: 'M4 21a8 8 0 0 1 16 0' }]],
  briefcase: [['rect', { x: 3, y: 7, width: 18, height: 13, rx: 3 }], ['path', { d: 'M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18' }]],
  gamepad: [['path', { d: 'M6 8h12a4 4 0 0 1 4 4v2a3 3 0 0 1-5.2 2L15 14H9l-1.8 2A3 3 0 0 1 2 14v-2a4 4 0 0 1 4-4z' }], ['path', { d: 'M7 11v3M5.5 12.5h3M16 11h.01M18 13h.01' }]],
  chat: [['path', { d: 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.5A8 8 0 1 1 21 12z' }]],
  card: [['rect', { x: 2, y: 5, width: 20, height: 14, rx: 3 }], ['path', { d: 'M2 10h20M6 15h4' }]],
  play: [['circle', { cx: 12, cy: 12, r: 9 }], ['path', { d: 'M10 8.5l5 3.5-5 3.5z' }]],
  home: [['path', { d: 'M3 11l9-8 9 8' }], ['path', { d: 'M5 10v10h5v-6h4v6h5V10' }]],
  cart: [['circle', { cx: 9, cy: 20, r: 1.5 }], ['circle', { cx: 18, cy: 20, r: 1.5 }], ['path', { d: 'M2 3h3l2.7 12.4a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 7H6' }]],
  school: [['path', { d: 'M2 9l10-5 10 5-10 5z' }], ['path', { d: 'M6 11.5V16c0 1.5 3 3 6 3s6-1.5 6-3v-4.5' }]],
  code: [['path', { d: 'M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16' }]],
  heart: [['path', { d: 'M12 20s-8-4.6-8-10a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.4-8 10-8 10z' }]],
  star: [['path', { d: 'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z' }]],
};

const COLOR_NAMES = { mint: 'Menta', blue: 'Azul', violet: 'Violeta', pink: 'Rosa', amber: 'Âmbar', coral: 'Coral', lime: 'Lima', gray: 'Cinza' };
const ICON_NAMES = {
  user: 'Pessoa', briefcase: 'Maleta', gamepad: 'Controle', chat: 'Conversa', card: 'Cartão', play: 'Reprodução',
  home: 'Casa', cart: 'Carrinho', school: 'Escola', code: 'Código', heart: 'Coração', star: 'Estrela',
};
const MAX_CATEGORY_NAME = 24;

function svg(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}

function icon(name, size = 18, strokeWidth = 2) {
  const el = svg('svg', {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    'stroke-width': strokeWidth, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true',
  });
  for (const [tag, attrs] of ICONS[name] || ICONS.star) el.append(svg(tag, attrs));
  return el;
}

function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'value') el.value = value;
    else if (key === 'checked') el.checked = true;
    else el.setAttribute(key, value === true ? '' : value);
  }
  el.append(...children.flat().filter((child) => child != null && child !== false));
  return el;
}

function logoImg(className, size) {
  return h('img', { class: className, src: 'img/owlock-icon.png', alt: 'OwLock', width: String(size), height: String(size) });
}

function led(color = 'mint') {
  return h('span', { class: `led ${color}`, 'aria-hidden': 'true' });
}

/* Cor de status pela força: 0-1 vermelho, 2 âmbar, 3-4 menta. */
function strengthTone(score) {
  if (score <= 1) return 'red';
  return score === 2 ? 'amber' : 'mint';
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function setDelay(el, ms) {
  el.style.setProperty('animation-delay', `${ms}ms`);
}

/* ======================================================================
   Estado (tudo em memória; nada vai para localStorage/sessionStorage)
   ====================================================================== */

const root = document.getElementById('app');
const modalRoot = document.getElementById('modal-root');
const toastRoot = document.getElementById('toasts');

const EMPTY_STATS = { total: 0, with_2fa: 0, attention: 0 };
const TOUCH_EVERY_MS = 20000;
const REVEAL_AUTOHIDE_MS = 30000;

const state = {
  unlocked: false,
  status: null,
  view: 'vault',
  screen: 'list',
  filter: 'all',
  query: '',
  entries: [],
  stats: { ...EMPTY_STATS },
  selected: null,
  revealed: null, // { id, text }
  copied: null, // { id, until, seconds, startedAt }
  deadline: 0,
  lastTouch: 0,
  loadSeq: 0,
  categories: [],
  categoryFilter: '', // '' = todas, 'none' = sem categoria, ou id
  options: { colors: [], icons: [] },
  gen: null,
};

let ui = {}; // referências de DOM da tela principal
let tickTimer = null;
let revealTimer = null;
let copyTimer = null;

function wipeState() {
  clearInterval(tickTimer);
  clearTimeout(revealTimer);
  clearTimeout(copyTimer);
  Object.assign(state, {
    unlocked: false, view: 'vault', screen: 'list', filter: 'all', query: '', entries: [],
    stats: { ...EMPTY_STATS }, selected: null, revealed: null, copied: null, gen: null, deadline: 0,
    categories: [], categoryFilter: '',
  });
  ui = {};
  root.replaceChildren();
}

/* ======================================================================
   Avisos e utilidades de texto
   ====================================================================== */

function toast(message, kind = 'ok') {
  const el = h('div', { class: 'toast' }, led(kind === 'warn' ? 'red' : 'mint'), h('span', { text: message }));
  toastRoot.append(el);
  setTimeout(() => el.classList.add('leaving'), 2500);
  setTimeout(() => el.remove(), 2800);
}

function apiMessage(result, fallback = 'Algo deu errado. Tente novamente.') {
  return (result && result.message) || fallback;
}

function plural(n, one, many) {
  return n === 1 ? one : many;
}

function timeAgo(iso) {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '';
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return 'agora mesmo';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `há ${minutes} ${plural(minutes, 'minuto', 'minutos')}`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours} ${plural(hours, 'hora', 'horas')}`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `há ${days} ${plural(days, 'dia', 'dias')}`;
  if (days < 30) {
    const weeks = Math.floor(days / 7);
    return `há ${weeks} ${plural(weeks, 'semana', 'semanas')}`;
  }
  if (days < 365) {
    const months = Math.floor(days / 30);
    return `há ${months} ${plural(months, 'mês', 'meses')}`;
  }
  const years = Math.floor(days / 365);
  return `há ${years} ${plural(years, 'ano', 'anos')}`;
}

function formatClock(totalSeconds) {
  const s = Math.max(0, totalSeconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

const STRENGTH_PCT = [8, 22, 48, 74, 100];
const STRENGTH_HINT = ['', ' — troque esta senha', ' — dá para melhorar', '', ''];

function strengthClass(score) {
  return `s${Math.min(4, Math.max(0, score))}`;
}

/* Medidor de força reutilizável (barra + rótulo). */
function createMeter(id) {
  const fill = h('div', { class: 'meter-fill' });
  const label = h('span', { class: 'meter-label', ...(id ? { id } : {}) });
  const el = h('div', { class: 'meter' }, h('div', { class: 'meter-track' }, fill), label);
  return {
    el,
    set(score, text) {
      const s = Math.min(4, Math.max(0, score));
      el.className = `meter ${strengthClass(s)}`;
      fill.style.setProperty('width', `${STRENGTH_PCT[s]}%`);
      label.textContent = text;
    },
    clear(text = '') {
      el.className = 'meter';
      fill.style.setProperty('width', '0%');
      label.textContent = text;
    },
  };
}

/* ======================================================================
   Modais (foco preso, Esc fecha)
   ====================================================================== */

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
let activeModal = null;

function openModal(card, { dismissOnBackdrop = false } = {}) {
  closeModal();
  const opener = document.activeElement;
  card.setAttribute('role', 'dialog');
  card.setAttribute('aria-modal', 'true');
  card.prepend(h('div', { class: 'grabber', 'aria-hidden': 'true' }));
  const backdrop = h('div', { class: 'backdrop' }, card);
  if (dismissOnBackdrop) {
    backdrop.addEventListener('mousedown', (event) => {
      if (event.target === backdrop) closeModal();
    });
  }
  modalRoot.append(backdrop);
  root.setAttribute('inert', '');
  activeModal = { backdrop, card, opener };
  const first = card.querySelector('[data-autofocus]') || card.querySelector(FOCUSABLE);
  first?.focus();
}

function closeModal() {
  if (!activeModal) return;
  const { backdrop, opener } = activeModal;
  activeModal = null;
  backdrop.remove();
  root.removeAttribute('inert');
  if (opener && opener.isConnected) opener.focus();
}

document.addEventListener('keydown', (event) => {
  if (!activeModal) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    closeModal();
    return;
  }
  if (event.key !== 'Tab') return;
  const items = [...activeModal.card.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && (document.activeElement === first || !activeModal.card.contains(document.activeElement))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (document.activeElement === last || !activeModal.card.contains(document.activeElement))) {
    event.preventDefault();
    first.focus();
  }
});

/* ======================================================================
   Entrada: criação do cofre e desbloqueio
   ====================================================================== */

function passwordField({ id, label, autofocus = false, placeholder = '' }) {
  const input = h('input', {
    class: 'input', id, type: 'password', autocomplete: 'off', spellcheck: 'false',
    ...(placeholder ? { placeholder } : {}), ...(autofocus ? { 'data-autofocus': '' } : {}),
  });
  return { input, el: h('div', { class: 'field' }, h('label', { for: id, text: label }), input) };
}

function authHead(title, subtitle) {
  return h('div', { class: 'auth-head' },
    h('div', { class: 'logo-wrap' }, logoImg('auth-logo', 72)),
    h('h1', { text: title }),
    h('p', { text: subtitle }));
}

async function showEntry(notice = '') {
  const status = await fetchStatus();
  if (!status) return;
  if (!status.exists) showCreate();
  else if (status.unlocked) await enterMain(status);
  else showUnlock(notice);
}

async function fetchStatus() {
  const r = await call('status');
  if (!r.ok) {
    root.replaceChildren(h('div', { class: 'boot', role: 'alert', text: apiMessage(r, 'Não foi possível abrir o aplicativo.') }));
    return null;
  }
  state.status = r;
  return r;
}

function showUnlock(notice = '') {
  const pw = passwordField({ id: 'unlock-password', label: 'Senha mestra', autofocus: true });
  const error = h('p', { class: 'msg error', id: 'unlock-error', role: 'alert' });
  const submit = h('button', { class: 'btn btn-primary wide', id: 'unlock-submit', type: 'submit', text: 'Abrir cofre' });

  const form = h('form', { novalidate: '' }, pw.el, error, submit);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    const typed = pw.input.value;
    error.textContent = '';
    submit.disabled = true;
    submit.textContent = 'Abrindo...';
    const r = await call('unlock', typed);
    if (r.ok) {
      pw.input.value = '';
      await showEntry();
      return;
    }
    submit.disabled = false;
    submit.textContent = 'Abrir cofre';
    error.textContent = apiMessage(r, 'Não foi possível abrir o cofre.');
    pw.input.select();
    pw.input.focus();
  });

  const card = h('div', { class: 'auth-card ow-in' },
    authHead('OwLock', 'Digite a senha mestra para abrir o cofre.'),
    notice ? h('p', { class: 'notice', role: 'status', text: notice }) : null,
    form,
    h('p', { class: 'auth-foot', text: state.status?.vault_path || '' }));
  root.replaceChildren(h('div', { class: 'auth' }, card));
  pw.input.focus();
}

function showCreate() {
  const pw = passwordField({ id: 'create-password', label: 'Senha mestra', autofocus: true });
  const confirm = passwordField({ id: 'create-confirm', label: 'Confirmar senha mestra' });
  const error = h('p', { class: 'msg error', id: 'create-error', role: 'alert' });
  const submit = h('button', { class: 'btn btn-primary wide', id: 'create-submit', type: 'submit', text: 'Criar cofre' });

  const form = h('form', { novalidate: '' },
    pw.el,
    h('p', { class: 'hint', text: 'Use pelo menos 8 caracteres.' }),
    confirm.el,
    h('p', { class: 'notice warn', text: 'Atenção: não existe recuperação. Se você esquecer a senha mestra, ninguém consegue abrir o cofre, nem mesmo o OwLock.' }),
    error,
    submit);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    const first = pw.input.value;
    const second = confirm.input.value;
    error.textContent = '';
    if (first.length < 8) {
      error.textContent = 'A senha mestra precisa ter pelo menos 8 caracteres.';
      pw.input.focus();
      return;
    }
    if (first !== second) {
      error.textContent = 'As senhas não conferem.';
      confirm.input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Criando...';
    const r = await call('create_vault', first, second);
    if (!r.ok) {
      submit.disabled = false;
      submit.textContent = 'Criar cofre';
      error.textContent = apiMessage(r, 'Não foi possível criar o cofre.');
      return;
    }
    pw.input.value = '';
    confirm.input.value = '';
    const status = await fetchStatus();
    if (!status) return;
    if (status.unlocked) {
      await enterMain(status);
    } else {
      const opened = await call('unlock', first);
      if (opened.ok) await showEntry();
      else showUnlock();
    }
  });

  const card = h('div', { class: 'auth-card ow-in' },
    authHead('Criar cofre', 'Escolha a senha mestra que vai proteger todas as suas senhas.'),
    form,
    h('p', { class: 'auth-foot', text: state.status?.vault_path || '' }));
  root.replaceChildren(h('div', { class: 'auth' }, card));
  pw.input.focus();
}

/* ======================================================================
   Bloqueio, contagem regressiva e atividade
   ====================================================================== */

async function lockNow(notice = '') {
  if (!state.unlocked) return;
  closeModal();
  wipeState();
  await call('lock');
  await showEntry(notice);
}

window.addEventListener('owlock:locked', () => {
  lockNow('O cofre foi bloqueado.');
});

function secondsLeft() {
  return Math.max(0, Math.ceil((state.deadline - Date.now()) / 1000));
}

function tick() {
  if (!state.unlocked) return;
  const left = secondsLeft();
  if (ui.timerText) ui.timerText.textContent = `Bloqueia em ${formatClock(left)}`;
  if (ui.timer) ui.timer.className = `timer${left < 15 ? ' critical' : left < 60 ? ' low' : ''}`;
  if (left <= 0) lockNow('Cofre bloqueado por inatividade.');
}

function startTimer(seconds) {
  state.deadline = Date.now() + seconds * 1000;
  state.lastTouch = Date.now();
  clearInterval(tickTimer);
  tickTimer = setInterval(tick, 1000);
  tick();
}

async function registerActivity() {
  if (!state.unlocked) return;
  const now = Date.now();
  if (now - state.lastTouch < TOUCH_EVERY_MS) return;
  state.lastTouch = now;
  const r = await call('touch');
  if (r.ok && typeof r.seconds_left === 'number' && state.unlocked) {
    state.deadline = Date.now() + r.seconds_left * 1000;
    tick();
  }
}

for (const name of ['mousemove', 'keydown', 'click']) {
  document.addEventListener(name, registerActivity, { passive: true });
}

/* ======================================================================
   Tela principal
   ====================================================================== */

async function enterMain(status) {
  state.unlocked = true;
  state.status = status;
  buildShell();
  startTimer(typeof status.seconds_left === 'number' ? status.seconds_left : status.auto_lock_seconds || 300);
  await Promise.all([loadOptions(), loadCategories()]);
  await loadEntries();
  if (state.entries.length && !state.selected) {
    state.selected = state.entries[0];
    renderList();
  }
  renderDetail({ first: true });
}

function railButton(id, iconName, label, onClick, extra = '') {
  return h('button', { class: `btn rail-btn ${extra}`.trim(), id: `nav-${id}`, type: 'button', 'data-view': id, onClick },
    icon(iconName, 20), h('span', { text: label }));
}

function buildShell() {
  ui.shell = h('div', { class: 'shell', 'data-view': 'vault', 'data-screen': 'list' });

  const rail = h('nav', { class: 'rail', 'aria-label': 'Navegação' },
    logoImg('rail-logo', 40),
    railButton('vault', 'vault', 'Cofre', () => setView('vault')),
    railButton('generator', 'generator', 'Gerador', () => setView('generator')),
    railButton('settings', 'sliders', 'Ajustes', () => setView('settings')),
    h('div', { class: 'rail-spacer' }),
    railButton('lock', 'lock', 'Bloquear', () => lockNow('Cofre bloqueado.'), 'rail-lock'));

  ui.shell.append(rail, buildListColumn(), buildMain());
  root.replaceChildren(ui.shell);
  setView('vault');
}

function buildListColumn() {
  ui.timerText = h('span', { id: 'timer-text', text: 'Bloqueia em --:--' });
  ui.timer = h('span', { class: 'timer' }, led('mint'), ui.timerText);

  ui.search = h('input', {
    id: 'search', type: 'text', placeholder: 'Buscar', 'aria-label': 'Buscar contas', autocomplete: 'off', spellcheck: 'false',
  });
  const runSearch = debounce(() => {
    state.query = ui.search.value.trim();
    loadEntries();
  }, 150);
  ui.searchClear = h('button', { class: 'btn search-clear', id: 'search-clear', type: 'button', hidden: true, 'aria-label': 'Limpar busca' }, icon('close', 11, 3));
  ui.search.addEventListener('input', () => {
    ui.searchClear.hidden = ui.search.value === '';
    runSearch();
  });
  ui.searchClear.addEventListener('click', () => {
    ui.search.value = '';
    ui.searchClear.hidden = true;
    state.query = '';
    loadEntries();
    ui.search.focus();
  });

  ui.tabs = [['all', 'Todas'], ['2fa', 'Com 2FA'], ['attention', 'Atenção']].map(([id, label]) =>
    h('button', {
      class: 'btn tab', type: 'button', role: 'tab', id: `tab-${id}`, 'data-filter': id,
      'aria-selected': id === state.filter ? 'true' : 'false',
      onClick: () => setFilter(id),
    }, label));

  ui.tabsBox = h('div', { class: 'segmented', role: 'tablist', 'aria-label': 'Filtro', 'data-index': '0' },
    h('span', { class: 'seg-thumb', 'aria-hidden': 'true' }), ui.tabs);
  ui.catStrip = h('div', { class: 'cat-strip', id: 'cat-strip', role: 'group', 'aria-label': 'Categorias' });
  ui.catStrip.addEventListener('wheel', (event) => {
    if (ui.catStrip.scrollWidth <= ui.catStrip.clientWidth || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    ui.catStrip.scrollLeft += event.deltaY;
    event.preventDefault();
  }, { passive: false });
  ui.statsMobile = h('div', { class: 'stats stats-mobile' });
  ui.rows = h('div', { class: 'rows', id: 'entry-list' });

  const newButton = h('button', { class: 'btn btn-primary new-btn', id: 'new-entry', type: 'button', onClick: () => openEntryForm(null) },
    icon('plus', 16, 2.4), h('span', { class: 'label', text: 'Nova conta' }));

  return h('section', { class: 'list-col', 'aria-label': 'Contas' },
    h('div', { class: 'list-head' }, h('h2', { text: 'Cofre' }), ui.timer),
    ui.statsMobile,
    h('label', { class: 'search' }, icon('search', 16), ui.search, ui.searchClear),
    ui.catStrip,
    ui.tabsBox,
    ui.rows,
    newButton);
}

function buildMain() {
  ui.statsDesktop = h('div', { class: 'stats stats-desktop' });
  ui.detail = h('div', { class: 'detail-slot', id: 'detail' });
  ui.paneVault = h('div', { class: 'pane pane-vault' }, ui.statsDesktop, ui.detail);
  ui.paneGen = h('div', { class: 'pane pane-generator' });
  ui.paneSettings = h('div', { class: 'pane pane-settings' });
  return h('main', { class: 'main' }, ui.paneVault, ui.paneGen, ui.paneSettings);
}

function setView(view) {
  if (state.view === 'vault' && view !== 'vault') hideReveal();
  state.view = view;
  ui.shell.dataset.view = view;
  for (const button of ui.shell.querySelectorAll('.rail-btn[data-view]')) {
    if (button.dataset.view === view) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
  ui.paneGen.replaceChildren();
  ui.paneSettings.replaceChildren();
  state.gen = null;
  if (view === 'generator') buildGenerator();
  if (view === 'settings') buildSettings();
}

function setScreen(screen) {
  state.screen = screen;
  ui.shell.dataset.screen = screen;
}

function syncTabs() {
  for (const tab of ui.tabs) tab.setAttribute('aria-selected', tab.dataset.filter === state.filter ? 'true' : 'false');
  ui.tabsBox.dataset.index = String(Math.max(0, ['all', '2fa', 'attention'].indexOf(state.filter)));
}

function setFilter(filter) {
  state.filter = filter;
  syncTabs();
  loadEntries();
}

/* ---------- carregamento da lista ---------- */

async function loadEntries() {
  const seq = ++state.loadSeq;
  const r = await call('list_entries', state.query, state.filter, state.categoryFilter);
  if (seq !== state.loadSeq || !state.unlocked) return;
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r), 'warn');
    return;
  }
  state.entries = r.entries;
  state.stats = r.stats || { ...EMPTY_STATS };
  if (state.selected) {
    const fresh = state.entries.find((entry) => entry.id === state.selected.id);
    if (fresh) state.selected = fresh;
  }
  renderStats();
  renderCategories();
  renderList();
}

function statCard(value, longLabel, shortLabel, tone, delay) {
  const card = h('div', { class: `stat ${tone}` },
    led(tone === 'red' ? 'red' : 'mint'),
    h('b', { text: String(value) }),
    h('span', {}, h('span', { class: 'long', text: longLabel }), h('span', { class: 'short', text: shortLabel })));
  if (delay != null) {
    card.classList.add('ow-in');
    setDelay(card, delay);
  }
  return card;
}

function renderStats() {
  const { total, with_2fa: withTwofa, attention } = state.stats;
  const build = (animated) => [
    statCard(total, plural(total, 'conta no cofre', 'contas no cofre'), plural(total, 'conta', 'contas'), '', animated ? 0 : null),
    statCard(withTwofa, 'com verificação em 2 etapas', 'com 2FA', 'mint', animated ? 60 : null),
    statCard(attention, plural(attention, 'senha precisa de atenção', 'senhas precisam de atenção'), 'atenção', attention > 0 ? 'red' : 'mint', animated ? 120 : null),
  ];
  const firstPaint = !ui.statsDesktop.firstChild;
  ui.statsDesktop.replaceChildren(...build(firstPaint));
  ui.statsMobile.replaceChildren(...build(false));
}

function emptyList() {
  const activeCategory = state.categories.find((category) => category.id === state.categoryFilter);
  if (activeCategory && state.query === '' && state.filter === 'all') {
    return h('div', { class: 'empty', id: 'empty-category' },
      h('div', { class: 'empty-icon cat-tile' }, tint(icon(activeCategory.icon, 24), activeCategory.color_hex)),
      h('h3', { text: `Nenhuma conta em ${activeCategory.name}` }),
      h('p', { text: 'Quando você adicionar contas a esta categoria, elas aparecem aqui.' }),
      h('button', { class: 'btn btn-primary', id: 'empty-new', type: 'button', onClick: () => openEntryForm(null) },
        icon('plus', 16, 2.4), 'Nova conta'));
  }
  const searching = state.query !== '' || state.filter !== 'all' || state.categoryFilter !== '';
  if (searching) {
    return h('div', { class: 'empty' },
      h('div', { class: 'empty-icon' }, icon('search', 22)),
      h('h3', { text: 'Nada encontrado' }),
      h('p', { text: 'Nenhuma conta combina com a busca ou com o filtro escolhido.' }));
  }
  return h('div', { class: 'empty', id: 'empty-vault' },
    h('div', { class: 'empty-icon' }, icon('vault', 24)),
    h('h3', { text: 'Seu cofre está vazio' }),
    h('p', { text: 'Guarde suas senhas aqui, cifradas com a senha mestra. Comece criando a primeira conta.' }),
    h('button', { class: 'btn btn-primary', id: 'empty-new', type: 'button', onClick: () => openEntryForm(null) },
      icon('plus', 16, 2.4), 'Criar primeira conta'));
}

function renderList() {
  if (!ui.rows) return;
  if (!state.entries.length) {
    ui.rows.replaceChildren(emptyList());
    return;
  }
  const rows = state.entries.map((entry, index) => {
    const score = entry.strength.score;
    const warn = score <= 2;
    const row = h('button', {
      class: 'btn row' + (state.selected?.id === entry.id ? ' is-selected' : ''),
      type: 'button', 'data-id': entry.id,
      onClick: () => selectEntry(entry.id, true),
    },
      monoBadge(entry),
      h('span', { class: 'row-text' },
        h('span', { class: 'row-name', text: entry.service }),
        h('span', { class: 'row-user', text: entry.username || '' })),
      h('span', { class: `led ${strengthTone(score)}`, role: 'img', 'aria-label': warn ? 'Precisa de atenção' : 'Segura' }));
    setDelay(row, Math.min(index, 12) * 55);
    return row;
  });
  ui.rows.replaceChildren(...rows);
}

function monoBadge(entry) {
  const el = h('span', { class: 'mono-badge', 'aria-hidden': 'true', text: monogram(entry) });
  if (entry.category) {
    el.classList.add('cat');
    el.style.setProperty('--cat', entry.category.color_hex);
  }
  return el;
}

function monogram(entry) {
  return (entry.service.trim()[0] || '?').toUpperCase();
}

function selectEntry(id, openDetail = false) {
  const entry = state.entries.find((item) => item.id === id);
  if (!entry) return;
  if (state.selected?.id !== id) hideReveal();
  state.selected = entry;
  for (const row of ui.rows.querySelectorAll('.row')) row.classList.toggle('is-selected', row.dataset.id === id);
  renderDetail();
  if (openDetail) setScreen('detail');
}

/* ---------- detalhes da conta ---------- */

function emptyDetail() {
  const none = state.stats.total === 0;
  return h('div', { class: 'empty empty-card ow-in', id: 'detail-empty' },
    h('div', { class: 'empty-icon' }, icon('vault', 24)),
    h('h3', { text: none ? 'Nenhuma conta ainda' : 'Nenhuma conta selecionada' }),
    h('p', { text: none ? 'Crie a primeira conta para vê-la aqui.' : 'Escolha uma conta na lista para ver os detalhes e copiar a senha.' }));
}

function renderDetail({ first = false } = {}) {
  const entry = state.selected;
  ui.detail.replaceChildren();
  ui.pwText = null;
  if (!entry) {
    ui.detail.append(emptyDetail());
    return;
  }

  const twofaOn = entry.has_2fa;
  const twofaText = twofaOn ? (entry.twofa_app ? `Ativada · ${entry.twofa_app}` : 'Ativada') : 'Desativada';
  const score = entry.strength.score;

  ui.revealButton = h('button', { class: 'btn btn-chip', id: 'reveal-toggle', type: 'button', 'aria-controls': 'password-display', onClick: toggleReveal });
  ui.pwText = h('div', { class: 'pw-text', id: 'password-display' });

  const barFill = h('div', { class: 'meter-fill ow-bar' });
  barFill.style.setProperty('width', `${STRENGTH_PCT[score]}%`);
  const strengthText = `Força: ${entry.strength.label}${STRENGTH_HINT[score]} · ${entry.password_length} ${plural(entry.password_length, 'caractere', 'caracteres')}`;

  const copyButton = h('button', { class: 'btn btn-primary', id: 'copy-password', type: 'button', onClick: () => copyField(entry, 'password') });
  paintCopyButton(copyButton, entry.id);

  const infoRows = [
    h('div', { class: 'group-row' },
      h('span', { class: 'row-k', text: 'Login / e-mail' }),
      h('span', { class: 'row-v', id: 'detail-username', text: entry.username || '—' })),
    h('div', { class: 'group-row' },
      h('span', { class: 'row-k', text: 'Verificação em 2 etapas' }),
      h('span', { class: twofaOn ? 'row-v' : 'row-v warn', text: twofaText })),
  ];
  if (entry.notes) {
    infoRows.push(h('div', { class: 'group-row stacked' },
      h('span', { class: 'row-k', text: 'Notas' }),
      h('span', { class: 'row-v', text: entry.notes })));
  }

  const card = h('article', { class: first ? 'detail ow-in' : 'detail ow-swap', 'aria-label': `Detalhes de ${entry.service}` },
    h('button', { class: 'btn back-btn', id: 'back', type: 'button', onClick: () => setScreen('list') }, icon('back', 22, 2.2), 'Cofre'),
    h('header', { class: 'detail-head' },
      monoBadge(entry),
      h('div', { class: 'detail-title' },
        h('h1', { id: 'detail-name', text: entry.service }),
        entry.category ? detailCategory(entry.category) : null,
        h('span', { text: `Atualizada ${timeAgo(entry.updated_at)}`.trim() })),
      h('button', { class: 'btn btn-ghost small', id: 'edit-entry', type: 'button', onClick: () => openEntryForm(entry) }, 'Editar')),
    h('div', { class: 'group' }, infoRows),
    h('div', { class: 'pw-box' },
      h('div', { class: 'pw-head' }, h('span', { class: 'k', text: 'Senha' }), ui.revealButton),
      ui.pwText,
      h('div', { class: `meter ${strengthClass(score)}` },
        h('div', { class: 'meter-track' }, barFill),
        h('span', { class: 'meter-label', id: 'strength-label', text: strengthText })),
      h('div', { class: 'pw-actions' },
        copyButton,
        h('button', { class: 'btn btn-ghost', id: 'copy-username', type: 'button', onClick: () => copyField(entry, 'username') }, 'Copiar login'),
        h('button', { class: 'btn btn-ghost danger', id: 'delete-entry', type: 'button', onClick: () => confirmDelete(entry) }, 'Excluir'))));

  if (first) setDelay(card, 140);
  ui.detail.append(card);
  paintPassword(false);
}

/* Mostra a senha (com animação caractere a caractere) ou os pontos. */
function paintPassword(animate) {
  if (!ui.pwText) return;
  const shown = state.revealed && state.selected && state.revealed.id === state.selected.id;
  if (shown) {
    const chars = [...state.revealed.text].map((ch, index) => {
      const span = h('span', { class: animate ? 'ow-char' : '', text: ch });
      if (animate) setDelay(span, index * 28);
      return span;
    });
    ui.pwText.replaceChildren(...chars);
  } else {
    ui.pwText.replaceChildren(h('span', { class: 'masked', 'aria-label': 'Senha oculta', text: '••••••••••••' }));
  }
  ui.revealButton.textContent = shown ? 'Ocultar' : 'Mostrar';
  ui.revealButton.setAttribute('aria-pressed', shown ? 'true' : 'false');
}

function hideReveal() {
  clearTimeout(revealTimer);
  state.revealed = null;
  paintPassword(false);
}

async function toggleReveal() {
  const entry = state.selected;
  if (!entry) return;
  if (state.revealed && state.revealed.id === entry.id) {
    hideReveal();
    return;
  }
  ui.revealButton.disabled = true;
  const r = await call('reveal_password', entry.id);
  ui.revealButton.disabled = false;
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r), 'warn');
    return;
  }
  if (state.selected?.id !== entry.id) return;
  state.revealed = { id: entry.id, text: r.password };
  paintPassword(true);
  clearTimeout(revealTimer);
  revealTimer = setTimeout(hideReveal, REVEAL_AUTOHIDE_MS);
}

/* Botão "Copiar senha" com anel de contagem de 30 s. */
function paintCopyButton(button, id) {
  const copied = state.copied;
  const active = copied && copied.id === id && Date.now() < copied.until;
  button.replaceChildren();
  if (!active) {
    button.append(icon('copy', 18, 2.2), 'Copiar senha');
    return;
  }
  const elapsed = (Date.now() - copied.startedAt) / 1000;
  const progress = svg('circle', { class: 'ow-count', cx: 20, cy: 20, r: 18, fill: 'none', stroke: '#1FB894', 'stroke-width': 4, 'stroke-linecap': 'round' });
  progress.style.setProperty('animation-duration', `${copied.seconds}s`);
  progress.style.setProperty('animation-delay', `-${elapsed.toFixed(2)}s`);
  const ring = svg('svg', { class: 'ring', width: 22, height: 22, viewBox: '0 0 40 40', 'aria-hidden': 'true' });
  ring.append(
    svg('circle', { cx: 20, cy: 20, r: 18, fill: 'none', stroke: 'rgba(11,12,15,.14)', 'stroke-width': 4 }),
    progress);
  button.append(ring, `Copiada · limpa em ${copied.seconds} s`);
}

async function copyField(entry, field) {
  const r = await call('copy_field', entry.id, field);
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r), 'warn');
    return;
  }
  if (field === 'username') {
    toast('Login copiado');
    return;
  }
  const seconds = r.clear_in || 30;
  state.copied = { id: entry.id, seconds, startedAt: Date.now(), until: Date.now() + seconds * 1000 };
  const button = document.getElementById('copy-password');
  if (button) paintCopyButton(button, entry.id);
  clearTimeout(copyTimer);
  copyTimer = setTimeout(() => {
    state.copied = null;
    const current = document.getElementById('copy-password');
    if (current && state.selected) paintCopyButton(current, state.selected.id);
  }, seconds * 1000);
  toast('Senha copiada');
}

/* ======================================================================
   Formulário de conta (nova / edição)
   ====================================================================== */

function openEntryForm(entry) {
  const editing = Boolean(entry);
  const serviceInput = h('input', { class: 'row-input', id: 'form-service', type: 'text', autocomplete: 'off', value: editing ? entry.service : '', 'data-autofocus': '', placeholder: 'Obrigatório' });
  const userInput = h('input', { class: 'row-input', id: 'form-username', type: 'text', autocomplete: 'off', spellcheck: 'false', value: editing ? entry.username : '' });
  const pwInput = h('input', {
    class: 'row-input', id: 'form-password', type: 'password', autocomplete: 'new-password', spellcheck: 'false',
    placeholder: editing ? 'Deixe em branco para manter a senha atual' : '',
  });
  const showButton = h('button', { class: 'btn btn-chip', id: 'form-toggle-password', type: 'button', 'aria-pressed': 'false', 'aria-label': 'Mostrar senha' }, 'Mostrar');
  const genButton = h('button', { class: 'btn btn-chip', id: 'form-generate', type: 'button' }, 'Gerar');
  const meter = createMeter('form-strength');
  meter.clear(editing ? 'A senha atual será mantida.' : '');

  const twofaBox = h('input', { class: 'ios-switch', type: 'checkbox', role: 'switch', id: 'form-2fa', ...(editing && entry.has_2fa ? { checked: true } : {}) });
  const twofaApp = h('input', { class: 'row-input', id: 'form-2fa-app', type: 'text', autocomplete: 'off', value: editing ? entry.twofa_app || '' : '', placeholder: 'Ex.: Google Authenticator' });
  const syncTwofa = () => {
    twofaApp.disabled = !twofaBox.checked;
  };
  twofaBox.addEventListener('change', syncTwofa);
  syncTwofa();

  let categoryId = editing ? entry.category_id || '' : (state.categoryFilter && state.categoryFilter !== 'none' ? state.categoryFilter : '');
  const categoryPicker = h('div', { class: 'cat-strip in-form', id: 'form-categories', role: 'radiogroup', 'aria-label': 'Categoria' });
  const paintCategoryPicker = () => {
    const choose = (id) => {
      categoryId = id;
      paintCategoryPicker();
    };
    const options = [{ id: '', name: 'Nenhuma', icon: 'none', color_hex: '#A1A6B4' }, ...state.categories];
    categoryPicker.replaceChildren(...options.map((option) => catPill({
      name: option.name, hex: option.color_hex, iconName: option.icon, selected: categoryId === option.id,
      role: 'radio', onClick: () => choose(option.id), id: `form-cat-${option.id || 'none'}`,
    })));
  };
  paintCategoryPicker();

  const notes = h('textarea', { class: 'row-input', id: 'form-notes', rows: '3', value: editing ? entry.notes || '' : '' });
  const error = h('p', { class: 'msg error', id: 'form-error', role: 'alert' });
  const submit = h('button', { class: 'btn btn-primary', id: 'form-submit', type: 'submit' }, 'Salvar');
  const cancel = h('button', { class: 'btn btn-ghost', id: 'form-cancel', type: 'button', onClick: closeModal }, 'Cancelar');

  showButton.addEventListener('click', () => {
    const visible = pwInput.type === 'text';
    pwInput.type = visible ? 'password' : 'text';
    showButton.textContent = visible ? 'Mostrar' : 'Ocultar';
    showButton.setAttribute('aria-pressed', visible ? 'false' : 'true');
    showButton.setAttribute('aria-label', visible ? 'Mostrar senha' : 'Ocultar senha');
  });

  let strengthSeq = 0;
  const refreshStrength = async () => {
    const value = pwInput.value;
    const seq = ++strengthSeq;
    if (value === '') {
      meter.clear(editing ? 'A senha atual será mantida.' : '');
      return;
    }
    const r = await call('check_strength', value);
    if (seq !== strengthSeq || !r.ok) return;
    meter.set(r.score, `Força: ${r.label}${STRENGTH_HINT[r.score]}`);
  };
  const refreshStrengthSoon = debounce(refreshStrength, 200);
  pwInput.addEventListener('input', refreshStrengthSoon);

  genButton.addEventListener('click', async () => {
    const r = await call('generate_password', 20, true, true, true, true);
    if (!r.ok) {
      error.textContent = apiMessage(r);
      return;
    }
    pwInput.value = r.password;
    pwInput.type = 'text';
    showButton.textContent = 'Ocultar';
    showButton.setAttribute('aria-pressed', 'true');
    showButton.setAttribute('aria-label', 'Ocultar senha');
    strengthSeq += 1;
    if (r.strength) meter.set(r.strength.score, `Força: ${r.strength.label}${STRENGTH_HINT[r.strength.score]}`);
  });

  const form = h('form', { novalidate: '' },
    h('div', { class: 'group' },
      h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-service', text: 'Serviço *' }), serviceInput),
      h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-username', text: 'Login / e-mail' }), userInput)),
    h('div', { class: 'group' },
      h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-password', text: 'Senha' }), pwInput, showButton, genButton)),
    h('div', { class: 'form-meter' }, meter.el),
    h('div', { class: 'group' },
      h('label', { class: 'group-row switch-row', for: 'form-2fa' }, h('span', { class: 'row-k grow', text: 'Verificação em duas etapas (2FA)' }), twofaBox),
      h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-2fa-app', text: 'App autenticador' }), twofaApp)),
    h('div', { class: 'group' },
      h('div', { class: 'group-row stacked' }, h('span', { class: 'row-k', id: 'form-cat-label', text: 'Categoria' }), categoryPicker),
      h('div', { class: 'group-row stacked' }, h('label', { class: 'row-k', for: 'form-notes', text: 'Notas' }), notes)),
    error,
    h('div', { class: 'modal-actions' }, cancel, submit));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    error.textContent = '';
    serviceInput.parentElement.classList.remove('invalid');
    const service = serviceInput.value.trim();
    if (!service) {
      serviceInput.parentElement.classList.add('invalid');
      error.textContent = 'Informe o nome do serviço.';
      serviceInput.focus();
      return;
    }
    const typed = pwInput.value;
    const data = {
      service,
      username: userInput.value.trim(),
      password: editing && typed === '' ? null : typed,
      category_id: categoryId,
      has_2fa: twofaBox.checked,
      twofa_app: twofaBox.checked ? twofaApp.value.trim() : '',
      notes: notes.value,
    };
    if (editing) data.id = entry.id;
    submit.disabled = true;
    submit.textContent = 'Salvando...';
    const r = await call('save_entry', data);
    pwInput.value = '';
    if (!r.ok) {
      if (r.error === 'locked') return;
      submit.disabled = false;
      submit.textContent = 'Salvar';
      error.textContent = apiMessage(r, 'Não foi possível salvar a conta.');
      return;
    }
    closeModal();
    await afterSave(r.entry);
  });

  const card = h('div', { class: 'modal', 'aria-labelledby': 'form-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'form-title', text: editing ? 'Editar conta' : 'Nova conta' }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    form);
  openModal(card);
}

async function afterSave(saved) {
  hideReveal();
  state.query = '';
  state.filter = 'all';
  ui.search.value = '';
  ui.searchClear.hidden = true;
  state.categoryFilter = '';
  syncTabs();
  state.selected = saved;
  await Promise.all([loadCategories(), loadEntries()]);
  state.copied = null;
  renderDetail();
  setScreen('detail');
  toast('Conta salva');
}

/* ======================================================================
   Categorias
   ====================================================================== */

async function loadOptions() {
  const r = await call('category_options');
  if (r.ok) state.options = { colors: r.colors || [], icons: r.icons || [] };
}

async function loadCategories() {
  const r = await call('list_categories');
  if (!r.ok || !state.unlocked) return;
  state.categories = r.categories;
  renderCategories();
  if (state.view === 'settings' && ui.catSettings) renderCategorySettings();
}

function tint(el, hex) {
  el.style.setProperty('color', hex);
  return el;
}

/* Pílula de categoria (faixa da lista, formulário e pré-visualização). */
function catPill({ name, hex, iconName, count = null, selected = false, onClick, id, role = null, label = null }) {
  const pill = h('button', {
    class: 'btn cat-pill', type: 'button', 'aria-pressed': selected ? 'true' : 'false',
    ...(id ? { id } : {}), ...(role ? { role, 'aria-checked': selected ? 'true' : 'false' } : {}),
    ...(label ? { 'aria-label': label } : {}),
  }, icon(iconName, 16), h('span', { class: 'cat-name', text: name }),
  count != null ? h('span', { class: 'cat-count', text: String(count) }) : null);
  if (role) pill.removeAttribute('aria-pressed');
  pill.style.setProperty('--cat', hex);
  if (onClick) pill.addEventListener('click', onClick);
  return pill;
}

function renderCategories() {
  if (!ui.catStrip) return;
  const keep = ui.catStrip.scrollLeft;
  const current = state.categoryFilter;
  const pills = [catPill({
    id: 'cat-all', name: 'Todas', hex: '#9FE3D3', iconName: 'vault', count: state.stats.total,
    selected: current === '', onClick: () => setCategoryFilter(''),
  })];
  for (const category of state.categories) {
    pills.push(catPill({
      id: `cat-${category.id}`, name: category.name, hex: category.color_hex, iconName: category.icon, count: category.count,
      selected: current === category.id, onClick: () => setCategoryFilter(category.id),
    }));
  }
  if (state.stats.uncategorized > 0 || current === 'none') {
    pills.push(catPill({
      id: 'cat-none', name: 'Sem categoria', hex: '#A1A6B4', iconName: 'none', count: state.stats.uncategorized || 0,
      selected: current === 'none', onClick: () => setCategoryFilter('none'),
    }));
  }
  pills.push(catPill({
    id: 'cat-add', name: '', hex: '#9FE3D3', iconName: 'plus', label: 'Nova categoria',
    onClick: () => openCategoryEditor(null),
  }));
  pills[pills.length - 1].classList.add('cat-add');
  ui.catStrip.replaceChildren(...pills);
  ui.catStrip.scrollLeft = keep;
  // garante que a pílula ativa fique visível (ex.: filtro vindo da pílula do detalhe)
  const active = pills.find((pill) => pill.classList.contains('is-selected') || pill.getAttribute('aria-pressed') === 'true');
  if (active) {
    const strip = ui.catStrip;
    const left = active.getBoundingClientRect().left - strip.getBoundingClientRect().left + strip.scrollLeft;
    const right = left + active.offsetWidth;
    if (left < strip.scrollLeft || right > strip.scrollLeft + strip.clientWidth) {
      strip.scrollTo({ left: Math.max(0, left - 24), behavior: 'smooth' });
    }
  }
}

function setCategoryFilter(id) {
  state.categoryFilter = state.categoryFilter === id ? '' : id;
  renderCategories();
  loadEntries();
}

function detailCategory(category) {
  const chip = h('button', {
    class: 'btn cat-chip', id: 'detail-category', type: 'button', 'aria-label': `Filtrar por ${category.name}`,
    onClick: () => {
      state.categoryFilter = category.id;
      setScreen('list');
      renderCategories();
      loadEntries();
    },
  }, icon(category.icon, 14), h('span', { text: category.name }));
  chip.style.setProperty('--cat', category.color_hex);
  return chip;
}

/* Ajustes > Categorias */
function renderCategorySettings() {
  const rows = state.categories.map((category) => {
    const tile = h('span', { class: 'cat-tile', 'aria-hidden': 'true' }, icon(category.icon, 18));
    tile.style.setProperty('--cat', category.color_hex);
    return h('button', {
      class: 'btn group-row cat-row', type: 'button', 'data-cat-id': category.id,
      onClick: () => openCategoryEditor(category),
    }, tile,
    h('span', { class: 'row-k grow', text: category.name }),
    h('span', { class: 'cat-row-count', text: String(category.count) }),
    h('span', { class: 'chev', 'aria-hidden': 'true' }, icon('chevron', 16, 2.4)));
  });
  rows.push(h('button', { class: 'btn group-row cat-row cat-new', id: 'settings-new-category', type: 'button', onClick: () => openCategoryEditor(null) },
    h('span', { class: 'cat-tile mint', 'aria-hidden': 'true' }, icon('plus', 18, 2.4)),
    h('span', { class: 'row-k grow', text: 'Nova categoria' })));
  ui.catSettings.replaceChildren(
    h('h2', { class: 'group-title', text: 'Categorias' }),
    h('div', { class: 'group', id: 'category-group' }, rows));
}

/* Editor de categoria (modal no desktop, sheet no celular) */
function openCategoryEditor(category) {
  const editing = Boolean(category);
  const colors = state.options.colors;
  const icons = state.options.icons;
  const draft = {
    name: editing ? category.name : '',
    color: editing ? category.color : (colors[0]?.key || 'mint'),
    icon: editing ? category.icon : (icons.includes('star') ? 'star' : icons[0] || 'star'),
  };
  const hexOf = (key) => colors.find((c) => c.key === key)?.hex || '#9FE3D3';

  const nameInput = h('input', { class: 'row-input', id: 'cat-name', type: 'text', maxlength: String(MAX_CATEGORY_NAME), autocomplete: 'off', value: draft.name, placeholder: 'Ex.: Estudos', 'data-autofocus': '' });
  const counter = h('span', { class: 'cat-counter', id: 'cat-counter', 'aria-hidden': 'true' });
  const preview = h('div', { class: 'cat-preview', id: 'cat-preview', 'aria-label': 'Pré-visualização' });
  const colorGrid = h('div', { class: 'color-grid', role: 'radiogroup', 'aria-label': 'Cor' });
  const iconGrid = h('div', { class: 'icon-grid', role: 'radiogroup', 'aria-label': 'Ícone' });
  const error = h('p', { class: 'msg error', id: 'cat-error', role: 'alert' });

  const paint = () => {
    const hex = hexOf(draft.color);
    counter.textContent = `${draft.name.length}/${MAX_CATEGORY_NAME}`;
    const pill = catPill({ name: draft.name.trim() || 'Nome da categoria', hex, iconName: draft.icon, selected: true });
    pill.tabIndex = -1;
    pill.setAttribute('aria-hidden', 'true');
    preview.replaceChildren(pill);
    colorGrid.replaceChildren(...colors.map((color) => {
      const dot = h('button', {
        class: 'btn color-dot', type: 'button', role: 'radio', 'aria-checked': color.key === draft.color ? 'true' : 'false',
        'aria-label': COLOR_NAMES[color.key] || color.key, id: `cat-color-${color.key}`,
        onClick: () => { draft.color = color.key; paint(); },
      });
      dot.style.setProperty('--cat', color.hex);
      return dot;
    }));
    iconGrid.replaceChildren(...icons.map((key) => {
      const button = h('button', {
        class: 'btn icon-pick', type: 'button', role: 'radio', 'aria-checked': key === draft.icon ? 'true' : 'false',
        'aria-label': ICON_NAMES[key] || key, id: `cat-icon-${key}`,
        onClick: () => { draft.icon = key; paint(); },
      }, icon(key, 22));
      button.style.setProperty('--cat', hex);
      return button;
    }));
  };
  nameInput.addEventListener('input', () => {
    draft.name = nameInput.value;
    counter.textContent = `${draft.name.length}/${MAX_CATEGORY_NAME}`;
    const pill = preview.firstChild;
    if (pill) pill.querySelector('.cat-name').textContent = draft.name.trim() || 'Nome da categoria';
  });

  const submit = h('button', { class: 'btn btn-primary', id: 'cat-save', type: 'submit' }, 'Salvar');
  const actions = h('div', { class: 'modal-actions' });
  if (editing) {
    actions.append(h('button', { class: 'btn btn-ghost danger push-left', id: 'cat-delete', type: 'button', onClick: () => confirmDeleteCategory(category) }, 'Excluir categoria'));
  }
  actions.append(h('button', { class: 'btn btn-ghost', id: 'cat-cancel', type: 'button', onClick: closeModal }, 'Cancelar'), submit);

  const form = h('form', { novalidate: '' },
    h('div', { class: 'cat-preview-wrap' }, preview),
    h('div', { class: 'group' }, h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'cat-name', text: 'Nome' }), nameInput, counter)),
    h('div', { class: 'group' }, h('div', { class: 'group-row stacked' }, h('span', { class: 'row-k', text: 'Cor' }), colorGrid)),
    h('div', { class: 'group' }, h('div', { class: 'group-row stacked' }, h('span', { class: 'row-k', text: 'Ícone' }), iconGrid)),
    error,
    actions);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    error.textContent = '';
    if (!draft.name.trim()) {
      error.textContent = 'Informe o nome da categoria.';
      nameInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Salvando...';
    const data = { name: draft.name.trim(), color: draft.color, icon: draft.icon };
    if (editing) data.id = category.id;
    const r = await call('save_category', data);
    if (!r.ok) {
      if (r.error === 'locked') return;
      submit.disabled = false;
      submit.textContent = 'Salvar';
      error.textContent = apiMessage(r, 'Não foi possível salvar a categoria.');
      return;
    }
    closeModal();
    await Promise.all([loadCategories(), loadEntries()]);
    if (state.selected) {
      const fresh = state.entries.find((item) => item.id === state.selected.id);
      if (fresh) {
        state.selected = fresh;
        if (state.view === 'vault') renderDetail();
      }
    }
    toast('Categoria salva');
  });

  const card = h('div', { class: 'modal', 'aria-labelledby': 'cat-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'cat-title', text: editing ? 'Editar categoria' : 'Nova categoria' }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    form);
  paint();
  openModal(card);
}

function confirmDeleteCategory(category) {
  const n = category.count;
  const consequence = n === 0
    ? 'Nenhuma conta usa esta categoria.'
    : n === 1 ? 'A 1 conta desta categoria ficará sem categoria.' : `As ${n} contas desta categoria ficarão sem categoria.`;
  const error = h('p', { class: 'msg error', role: 'alert' });
  const confirmButton = h('button', { class: 'btn btn-primary danger', id: 'confirm-delete-category', type: 'button', 'data-autofocus': '' }, 'Excluir');
  confirmButton.addEventListener('click', async () => {
    confirmButton.disabled = true;
    const r = await call('delete_category', category.id);
    if (!r.ok) {
      if (r.error === 'locked') return;
      confirmButton.disabled = false;
      error.textContent = apiMessage(r, 'Não foi possível excluir a categoria.');
      return;
    }
    closeModal();
    if (state.categoryFilter === category.id) state.categoryFilter = '';
    await Promise.all([loadCategories(), loadEntries()]);
    if (state.selected) {
      const fresh = state.entries.find((item) => item.id === state.selected.id);
      if (fresh) state.selected = fresh;
      if (state.view === 'vault') renderDetail();
    }
    toast('Categoria excluída');
  });
  const card = h('div', { class: 'modal narrow', 'aria-labelledby': 'delete-cat-title' },
    h('h2', { id: 'delete-cat-title', text: 'Excluir categoria?' }),
    h('p', { class: 'lead' }, 'Você vai excluir ', h('strong', { text: category.name }), `. ${consequence}`),
    error,
    h('div', { class: 'modal-actions' },
      h('button', { class: 'btn btn-ghost', id: 'cancel-delete-category', type: 'button', onClick: closeModal }, 'Cancelar'),
      confirmButton));
  openModal(card, { dismissOnBackdrop: true });
}

/* ======================================================================
   Excluir
   ====================================================================== */

function confirmDelete(entry) {
  const error = h('p', { class: 'msg error', role: 'alert' });
  const confirmButton = h('button', { class: 'btn btn-primary danger', id: 'confirm-delete', type: 'button', 'data-autofocus': '' }, 'Excluir');
  confirmButton.addEventListener('click', async () => {
    confirmButton.disabled = true;
    const r = await call('delete_entry', entry.id);
    if (!r.ok) {
      if (r.error === 'locked') return;
      confirmButton.disabled = false;
      error.textContent = apiMessage(r, 'Não foi possível excluir a conta.');
      return;
    }
    closeModal();
    hideReveal();
    state.selected = null;
    state.copied = null;
    await Promise.all([loadCategories(), loadEntries()]);
    renderDetail();
    setScreen('list');
    toast('Conta excluída');
  });

  const card = h('div', { class: 'modal narrow', 'aria-labelledby': 'delete-title' },
    h('h2', { id: 'delete-title', text: 'Excluir conta?' }),
    h('p', { class: 'lead' }, 'Você vai excluir ', h('strong', { text: entry.service }), '. Esta ação não pode ser desfeita.'),
    error,
    h('div', { class: 'modal-actions' },
      h('button', { class: 'btn btn-ghost', id: 'cancel-delete', type: 'button', onClick: closeModal }, 'Cancelar'),
      confirmButton));
  openModal(card, { dismissOnBackdrop: true });
}

/* ======================================================================
   Gerador
   ====================================================================== */

function buildGenerator() {
  const gen = { length: 20, upper: true, lower: true, digits: true, symbols: true, password: '' };
  state.gen = gen;

  const output = h('div', { class: 'gen-out', id: 'gen-output', 'aria-label': 'Senha gerada' });
  const meter = createMeter('gen-strength');
  const lengthLabel = h('output', { id: 'gen-length-value', for: 'gen-length', text: String(gen.length) });
  const range = h('input', { type: 'range', id: 'gen-length', min: '8', max: '64', value: String(gen.length) });
  const error = h('p', { class: 'msg error', role: 'alert' });

  const generate = async () => {
    error.textContent = '';
    const r = await call('generate_password', gen.length, gen.upper, gen.lower, gen.digits, gen.symbols);
    if (state.gen !== gen) return;
    if (!r.ok) {
      if (r.error !== 'locked') error.textContent = apiMessage(r, 'Escolha pelo menos um tipo de caractere.');
      return;
    }
    gen.password = r.password;
    const chars = [...r.password].map((ch, index) => {
      const span = h('span', { class: 'ow-char', text: ch });
      setDelay(span, Math.min(index, 40) * 12);
      return span;
    });
    output.replaceChildren(...chars);
    meter.set(r.strength.score, `Força: ${r.strength.label}${STRENGTH_HINT[r.strength.score]}`);
  };
  const generateSoon = debounce(generate, 120);

  range.addEventListener('input', () => {
    gen.length = Number(range.value);
    lengthLabel.textContent = String(gen.length);
    generateSoon();
  });

  const toggle = (key, label, id) => {
    const input = h('input', { class: 'ios-switch', type: 'checkbox', role: 'switch', id, checked: true });
    input.addEventListener('change', () => {
      gen[key] = input.checked;
      generate();
    });
    return h('label', { class: 'group-row switch-row', for: id }, h('span', { class: 'row-k grow', text: label }), input);
  };

  const copyButton = h('button', { class: 'btn btn-ghost', id: 'gen-copy', type: 'button' }, icon('copy', 18, 2.2), 'Copiar');
  copyButton.addEventListener('click', async () => {
    if (!gen.password) return;
    const r = await call('copy_text', gen.password);
    if (r && r.ok) toast('Senha copiada — será apagada em 30 s');
    else if (r && r.error !== 'locked') toast((r && r.message) || 'Não foi possível copiar.', 'warn');
  });

  const card = h('div', { class: 'gen-stack ow-in' },
    output,
    meter.el,
    h('div', { class: 'group' },
      h('div', { class: 'group-row stacked' },
        h('div', { class: 'range-head' }, h('label', { for: 'gen-length', text: 'Tamanho' }), lengthLabel),
        range)),
    h('div', { class: 'group' },
      toggle('upper', 'Letras maiúsculas', 'gen-upper'),
      toggle('lower', 'Letras minúsculas', 'gen-lower'),
      toggle('digits', 'Números', 'gen-digits'),
      toggle('symbols', 'Símbolos', 'gen-symbols')),
    error,
    h('div', { class: 'btn-row' },
      h('button', { class: 'btn btn-primary', id: 'gen-again', type: 'button', onClick: generate }, icon('generator', 18, 2.2), 'Gerar outra'),
      copyButton),
    h('p', { class: 'hint', text: 'A senha gerada aqui não é salva. Ao copiar, ela é apagada da área de transferência em 30 s.' }));

  ui.paneGen.replaceChildren(
    h('div', { class: 'page-title' }, h('h1', { text: 'Gerador' }), h('p', { text: 'Crie senhas fortes e aleatórias.' })),
    card);
  generate();
}

/* ======================================================================
   Ajustes
   ====================================================================== */

function groupPasswordRow({ id, label, autofocus = false }) {
  const input = h('input', { class: 'row-input', id, type: 'password', autocomplete: 'off', spellcheck: 'false', ...(autofocus ? { 'data-autofocus': '' } : {}) });
  return { input, el: h('div', { class: 'group-row field-row' }, h('label', { class: 'row-k', for: id, text: label }), input) };
}

function buildSettings() {
  const current = groupPasswordRow({ id: 'set-current', label: 'Senha atual' });
  const next = groupPasswordRow({ id: 'set-new', label: 'Nova senha' });
  const confirm = groupPasswordRow({ id: 'set-confirm', label: 'Confirmar nova senha' });
  const message = h('p', { class: 'msg', id: 'settings-msg', role: 'status' });
  const submit = h('button', { class: 'btn btn-primary', id: 'settings-submit', type: 'submit' }, 'Trocar senha mestra');

  const form = h('form', { class: 'form-stack', novalidate: '' },
    h('div', { class: 'group' }, current.el, next.el, confirm.el),
    message,
    h('div', { class: 'btn-row' }, submit));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    message.className = 'msg';
    message.textContent = '';
    submit.disabled = true;
    submit.textContent = 'Trocando...';
    const r = await call('change_master_password', current.input.value, next.input.value, confirm.input.value);
    submit.disabled = false;
    submit.textContent = 'Trocar senha mestra';
    if (r.ok) {
      form.reset();
      message.className = 'msg ok';
      message.textContent = 'Senha mestra alterada com sucesso.';
      toast('Senha mestra alterada');
    } else if (r.error !== 'locked') {
      message.className = 'msg error';
      message.textContent = apiMessage(r, 'Não foi possível trocar a senha mestra.');
    }
  });

  const minutes = Math.round((state.status?.auto_lock_seconds || 300) / 60);
  ui.catSettings = h('div', { class: 'settings-stack ow-in', id: 'cat-settings' });
  renderCategorySettings();
  ui.paneSettings.replaceChildren(
    h('div', { class: 'page-title' }, h('h1', { text: 'Ajustes' }), h('p', { text: 'Segurança e informações do cofre.' })),
    h('div', { class: 'settings-stack ow-in' }, h('h2', { class: 'group-title', text: 'Senha mestra' }), form),
    ui.catSettings,
    h('div', { class: 'settings-stack ow-in' },
      h('h2', { class: 'group-title', text: 'Cofre' }),
      h('div', { class: 'group' },
        h('div', { class: 'group-row stacked' },
          h('span', { class: 'row-k', text: 'Arquivo do cofre' }),
          h('span', { class: 'row-v path', id: 'vault-path', text: state.status?.vault_path || '' })))),
    h('div', { class: 'settings-stack ow-in' },
      h('h2', { class: 'group-title', text: 'Proteção automática' }),
      h('div', { class: 'group' },
        h('div', { class: 'group-row' },
          h('span', { class: 'row-k grow', text: 'Bloqueio automático' }),
          h('span', { class: 'row-v', text: `${minutes} ${plural(minutes, 'minuto', 'minutos')}` })),
        h('div', { class: 'group-row' },
          h('span', { class: 'row-k grow', text: 'Limpar área de transferência' }),
          h('span', { class: 'row-v', text: '30 segundos' }))),
      h('p', { class: 'hint', text: `O cofre bloqueia sozinho após ${minutes} ${plural(minutes, 'minuto', 'minutos')} sem uso, e a área de transferência é limpa 30 segundos depois de copiar uma senha ou login.` })));
  current.input.focus();
}

/* ======================================================================
   Início
   ====================================================================== */

showEntry();
