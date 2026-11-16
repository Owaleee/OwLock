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
};

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
  for (const [tag, attrs] of ICONS[name]) el.append(svg(tag, attrs));
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
  });
  ui = {};
  root.replaceChildren();
}

/* ======================================================================
   Avisos e utilidades de texto
   ====================================================================== */

function toast(message, kind = 'ok') {
  const el = h('div', { class: kind === 'warn' ? 'toast warn' : 'toast', text: message });
  toastRoot.append(el);
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
    h('div', { class: 'logo big' }, icon('lock', 26, 2.3)),
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
  if (ui.timer) ui.timer.classList.toggle('low', left <= 30);
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
  await loadEntries();
  if (state.entries.length && !state.selected) {
    state.selected = state.entries[0];
    renderList();
  }
  renderDetail({ first: true });
}

function railButton(id, iconName, label, onClick) {
  return h('button', { class: 'btn rail-btn', id: `nav-${id}`, type: 'button', 'data-view': id, onClick },
    icon(iconName, 20), h('span', { text: label }));
}

function buildShell() {
  ui.shell = h('div', { class: 'shell', 'data-view': 'vault', 'data-screen': 'list' });

  const rail = h('nav', { class: 'rail', 'aria-label': 'Navegação' },
    h('div', { class: 'logo', 'aria-hidden': 'true' }, icon('lock', 20, 2.3)),
    railButton('vault', 'vault', 'Cofre', () => setView('vault')),
    railButton('generator', 'generator', 'Gerador', () => setView('generator')),
    railButton('settings', 'sliders', 'Ajustes', () => setView('settings')),
    h('div', { class: 'rail-spacer' }),
    railButton('lock', 'lock', 'Bloquear', () => lockNow('Cofre bloqueado.')));

  ui.shell.append(rail, buildListColumn(), buildMain());
  root.replaceChildren(ui.shell);
  setView('vault');
}

function buildListColumn() {
  ui.timerText = h('span', { id: 'timer-text', text: 'Bloqueia em --:--' });
  ui.timer = h('span', { class: 'timer' }, h('span', { class: 'timer-dot ow-dot', 'aria-hidden': 'true' }), ui.timerText);

  ui.search = h('input', {
    id: 'search', type: 'text', placeholder: 'Buscar', 'aria-label': 'Buscar contas', autocomplete: 'off', spellcheck: 'false',
  });
  ui.search.addEventListener('input', debounce(() => {
    state.query = ui.search.value.trim();
    loadEntries();
  }, 150));

  ui.tabs = [['all', 'Todas'], ['2fa', 'Com 2FA'], ['attention', 'Atenção']].map(([id, label]) =>
    h('button', {
      class: 'btn tab', type: 'button', role: 'tab', id: `tab-${id}`, 'data-filter': id,
      'aria-selected': id === state.filter ? 'true' : 'false',
      onClick: () => setFilter(id),
    }, label));

  ui.statsMobile = h('div', { class: 'stats stats-mobile' });
  ui.rows = h('div', { class: 'rows', id: 'entry-list' });

  const newButton = h('button', { class: 'btn btn-primary new-btn', id: 'new-entry', type: 'button', onClick: () => openEntryForm(null) },
    icon('plus', 16, 2.4), h('span', { class: 'label', text: 'Nova conta' }));

  return h('section', { class: 'list-col', 'aria-label': 'Contas' },
    h('div', { class: 'list-head' }, h('h2', { text: 'Cofre' }), ui.timer),
    ui.statsMobile,
    h('label', { class: 'search' }, icon('search', 16), ui.search),
    h('div', { class: 'tabs', role: 'tablist', 'aria-label': 'Filtro' }, ui.tabs),
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

function setFilter(filter) {
  state.filter = filter;
  for (const tab of ui.tabs) tab.setAttribute('aria-selected', tab.dataset.filter === filter ? 'true' : 'false');
  loadEntries();
}

/* ---------- carregamento da lista ---------- */

async function loadEntries() {
  const seq = ++state.loadSeq;
  const r = await call('list_entries', state.query, state.filter);
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
  renderList();
}

function statCard(value, longLabel, shortLabel, tone, delay) {
  const card = h('div', { class: `stat ${tone}` },
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
    statCard(attention, plural(attention, 'senha precisa de atenção', 'senhas precisam de atenção'), 'atenção', 'amber', animated ? 120 : null),
  ];
  const firstPaint = !ui.statsDesktop.firstChild;
  ui.statsDesktop.replaceChildren(...build(firstPaint));
  ui.statsMobile.replaceChildren(...build(false));
}

function emptyList() {
  const searching = state.query !== '' || state.filter !== 'all';
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
    const warn = entry.strength.score <= 2;
    const row = h('button', {
      class: 'btn row' + (state.selected?.id === entry.id ? ' is-selected' : ''),
      type: 'button', 'data-id': entry.id,
      onClick: () => selectEntry(entry.id, true),
    },
      h('span', { class: 'mono-badge', 'aria-hidden': 'true', text: monogram(entry) }),
      h('span', { class: 'row-text' },
        h('span', { class: 'row-name', text: entry.service }),
        h('span', { class: 'row-user', text: entry.username || '' })),
      h('span', { class: warn ? 'dot warn' : 'dot', role: 'img', 'aria-label': warn ? 'Precisa de atenção' : 'Segura' }));
    setDelay(row, Math.min(index, 12) * 55);
    return row;
  });
  ui.rows.replaceChildren(...rows);
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
  return h('div', { class: 'empty card ow-in', id: 'detail-empty' },
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

  const card = h('article', { class: 'card ow-in', 'aria-label': `Detalhes de ${entry.service}` },
    h('button', { class: 'btn back-btn', id: 'back', type: 'button', onClick: () => setScreen('list') }, icon('back', 20, 2.2), 'Cofre'),
    h('header', { class: 'detail-head' },
      h('span', { class: 'mono-badge', 'aria-hidden': 'true', text: monogram(entry) }),
      h('div', { class: 'detail-title' },
        h('h1', { id: 'detail-name', text: entry.service }),
        h('span', { text: `Atualizada ${timeAgo(entry.updated_at)}`.trim() })),
      h('button', { class: 'btn btn-ghost small', id: 'edit-entry', type: 'button', onClick: () => openEntryForm(entry) }, 'Editar')),
    h('div', { class: 'info-grid' },
      h('div', { class: 'info' }, h('span', { class: 'k', text: 'Login / e-mail' }), h('span', { class: 'v', id: 'detail-username', text: entry.username || '—' })),
      h('div', { class: 'info' }, h('span', { class: 'k', text: 'Verificação em duas etapas' }), h('span', { class: twofaOn ? 'v' : 'v warn', text: twofaText }))),
    h('div', { class: 'pw-box' },
      h('div', { class: 'pw-head' }, h('span', { class: 'k', text: 'Senha' }), ui.revealButton),
      ui.pwText,
      h('div', { class: `meter ${strengthClass(score)}` },
        h('div', { class: 'meter-track' }, barFill),
        h('span', { class: 'meter-label', id: 'strength-label', text: strengthText })),
      h('div', { class: 'pw-actions' },
        copyButton,
        h('button', { class: 'btn btn-ghost', id: 'copy-username', type: 'button', onClick: () => copyField(entry, 'username') }, 'Copiar login'),
        h('button', { class: 'btn btn-ghost danger', id: 'delete-entry', type: 'button', onClick: () => confirmDelete(entry) }, 'Excluir'))),
    entry.notes ? h('div', { class: 'notes' }, h('span', { class: 'k', text: 'Notas' }), h('span', { class: 'v', text: entry.notes })) : null);

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
  const progress = svg('circle', { class: 'ow-count', cx: 20, cy: 20, r: 18, fill: 'none', stroke: '#0B0C0F', 'stroke-width': 4, 'stroke-linecap': 'round' });
  progress.style.setProperty('animation-duration', `${copied.seconds}s`);
  progress.style.setProperty('animation-delay', `-${elapsed.toFixed(2)}s`);
  const ring = svg('svg', { class: 'ring', width: 22, height: 22, viewBox: '0 0 40 40', 'aria-hidden': 'true' });
  ring.append(
    svg('circle', { cx: 20, cy: 20, r: 18, fill: 'none', stroke: 'rgba(11,12,15,.15)', 'stroke-width': 4 }),
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
  const serviceInput = h('input', { class: 'input', id: 'form-service', type: 'text', autocomplete: 'off', value: editing ? entry.service : '', 'data-autofocus': '' });
  const userInput = h('input', { class: 'input', id: 'form-username', type: 'text', autocomplete: 'off', spellcheck: 'false', value: editing ? entry.username : '' });
  const pwInput = h('input', {
    id: 'form-password', type: 'password', autocomplete: 'new-password', spellcheck: 'false',
    placeholder: editing ? 'Deixe em branco para manter a senha atual' : '',
  });
  const showButton = h('button', { class: 'btn btn-chip', id: 'form-toggle-password', type: 'button', 'aria-pressed': 'false', 'aria-label': 'Mostrar senha' }, 'Mostrar');
  const genButton = h('button', { class: 'btn btn-chip', id: 'form-generate', type: 'button' }, 'Gerar');
  const meter = createMeter('form-strength');
  meter.clear(editing ? 'A senha atual será mantida.' : '');

  const twofaBox = h('input', { type: 'checkbox', id: 'form-2fa', ...(editing && entry.has_2fa ? { checked: true } : {}) });
  const twofaApp = h('input', { class: 'input', id: 'form-2fa-app', type: 'text', autocomplete: 'off', value: editing ? entry.twofa_app || '' : '', placeholder: 'Ex.: Google Authenticator' });
  const syncTwofa = () => {
    twofaApp.disabled = !twofaBox.checked;
  };
  twofaBox.addEventListener('change', syncTwofa);
  syncTwofa();

  const notes = h('textarea', { class: 'input', id: 'form-notes', rows: '3', value: editing ? entry.notes || '' : '' });
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
    h('div', { class: 'field' }, h('label', { for: 'form-service', text: 'Serviço *' }), serviceInput),
    h('div', { class: 'field' }, h('label', { for: 'form-username', text: 'Login / e-mail' }), userInput),
    h('div', { class: 'field' },
      h('label', { for: 'form-password', text: 'Senha' }),
      h('div', { class: 'input-wrap' }, pwInput, showButton, genButton),
      meter.el),
    h('label', { class: 'check' }, twofaBox, 'Esta conta usa verificação em duas etapas (2FA)'),
    h('div', { class: 'field' }, h('label', { for: 'form-2fa-app', text: 'App autenticador' }), twofaApp),
    h('div', { class: 'field' }, h('label', { for: 'form-notes', text: 'Notas' }), notes),
    error,
    h('div', { class: 'modal-actions' }, cancel, submit));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    error.textContent = '';
    serviceInput.classList.remove('invalid');
    const service = serviceInput.value.trim();
    if (!service) {
      serviceInput.classList.add('invalid');
      error.textContent = 'Informe o nome do serviço.';
      serviceInput.focus();
      return;
    }
    const typed = pwInput.value;
    const data = {
      service,
      username: userInput.value.trim(),
      password: editing && typed === '' ? null : typed,
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
  for (const tab of ui.tabs) tab.setAttribute('aria-selected', tab.dataset.filter === 'all' ? 'true' : 'false');
  state.selected = saved;
  await loadEntries();
  state.copied = null;
  renderDetail();
  setScreen('detail');
  toast('Conta salva');
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
    await loadEntries();
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
    const input = h('input', { type: 'checkbox', id, checked: true });
    input.addEventListener('change', () => {
      gen[key] = input.checked;
      generate();
    });
    return h('label', { class: 'switch', for: id }, h('span', { text: label }), input);
  };

  const copyButton = h('button', { class: 'btn btn-ghost', id: 'gen-copy', type: 'button' }, icon('copy', 18, 2.2), 'Copiar');
  copyButton.addEventListener('click', async () => {
    if (!gen.password) return;
    const r = await call('copy_text', gen.password);
    if (r && r.ok) toast('Senha copiada — será apagada em 30 s');
    else if (r && r.error !== 'locked') toast((r && r.message) || 'Não foi possível copiar.', 'warn');
  });

  const card = h('div', { class: 'card ow-in' },
    output,
    meter.el,
    h('div', { class: 'range-row' },
      h('div', { class: 'range-head' }, h('label', { for: 'gen-length', text: 'Tamanho' }), lengthLabel),
      range),
    h('div', { class: 'switches' },
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
    h('div', { class: 'page-title' }, h('h1', { text: 'Gerador de senhas' }), h('p', { text: 'Crie senhas fortes e aleatórias.' })),
    card);
  generate();
}

/* ======================================================================
   Ajustes
   ====================================================================== */

function buildSettings() {
  const current = passwordField({ id: 'set-current', label: 'Senha mestra atual' });
  const next = passwordField({ id: 'set-new', label: 'Nova senha mestra' });
  const confirm = passwordField({ id: 'set-confirm', label: 'Confirmar nova senha mestra' });
  const message = h('p', { class: 'msg', id: 'settings-msg', role: 'status' });
  const submit = h('button', { class: 'btn btn-primary', id: 'settings-submit', type: 'submit' }, 'Trocar senha mestra');

  const form = h('form', { class: 'form-stack', novalidate: '' }, current.el, next.el, confirm.el, message, h('div', { class: 'btn-row' }, submit));
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
  ui.paneSettings.replaceChildren(
    h('div', { class: 'page-title' }, h('h1', { text: 'Ajustes' }), h('p', { text: 'Segurança e informações do cofre.' })),
    h('div', { class: 'card ow-in' }, h('h2', { text: 'Trocar senha mestra' }), form),
    h('div', { class: 'card ow-in' },
      h('h2', { text: 'Cofre' }),
      h('div', { class: 'field' }, h('span', { class: 'field-label', text: 'Arquivo do cofre' }), h('div', { class: 'kv-path', id: 'vault-path', text: state.status?.vault_path || '' }))),
    h('div', { class: 'card ow-in' },
      h('h2', { text: 'Proteção automática' }),
      h('ul', { class: 'list-plain' },
        h('li', { text: `O cofre bloqueia sozinho após ${minutes} ${plural(minutes, 'minuto', 'minutos')} sem uso.` }),
        h('li', { text: 'A área de transferência é limpa 30 segundos depois de copiar uma senha ou login.' }))));
  current.input.focus();
}

/* ======================================================================
   Início
   ====================================================================== */

showEntry();
