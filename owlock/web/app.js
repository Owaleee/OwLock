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
  chevronLeft: [['path', { d: 'M15 6l-6 6 6 6' }]],
  tag: [['path', { d: 'M3 3h8.2a2 2 0 0 1 1.4.6l8 8a2 2 0 0 1 0 2.8l-6.2 6.2a2 2 0 0 1-2.8 0l-8-8A2 2 0 0 1 3 11.2V3z' }], ['circle', { cx: 7.5, cy: 7.5, r: 1.3 }]],
  external: [['path', { d: 'M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4' }]],
  check: [['path', { d: 'M5 12.5l4.5 4.5L19 7.5' }]],
  shieldKey: [['path', { d: 'M12 3l7.5 3v5.2c0 4.6-3.1 8.1-7.5 9.8-4.4-1.7-7.5-5.2-7.5-9.8V6L12 3z' }], ['circle', { cx: 12, cy: 10, r: 2 }], ['path', { d: 'M12 12v4M12 14.5h1.8' }]],
  download: [['path', { d: 'M12 4v11M7.5 11l4.5 4.5 4.5-4.5M5 20h14' }]],
  link: [['path', { d: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1' }]],
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

/* LED da conta: vermelho se fraca ou repetida, âmbar se razoável ou antiga, menta se segura. */
function entryTone(entry) {
  const score = entry.strength.score;
  if (score <= 1 || entry.reused) return 'red';
  if (score === 2 || entry.stale) return 'amber';
  return 'mint';
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
const FILTERS = [['all', 'Todas'], ['favorites', 'Favoritas'], ['2fa', 'Com 2FA'], ['attention', 'Atenção']];

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
  settings: null, // { settings, options }
  weakCount: 0, // contas fracas (calculado na lista sem filtros, se a Api não mandar)
  history: null, // { id, created_at, history }
  histReveal: null, // { id, index, text }
  options: { colors: [], icons: [] },
  brandIcons: [], // [{ slug, title, icon_url, color }]
  services: [], // biblioteca de serviços (ServiceSummary)
  gen: null,
};

let ui = {}; // referências de DOM da tela principal
let tickTimer = null;
let revealTimer = null;
let copyTimer = null;
let histTimer = null;
let quickMode = false; // rota #quick: janela compacta de busca rápida
let kitWipe = null; // descarta chave e senha da tela do Kit de emergência

function wipeState() {
  if (kitWipe) kitWipe();
  clearInterval(tickTimer);
  clearTimeout(revealTimer);
  clearTimeout(copyTimer);
  clearTimeout(histTimer);
  Object.assign(state, {
    unlocked: false, view: 'vault', screen: 'list', filter: 'all', query: '', entries: [],
    stats: { ...EMPTY_STATS }, selected: null, revealed: null, copied: null, gen: null, deadline: 0,
    categories: [], categoryFilter: '', settings: null, history: null, histReveal: null, services: [], weakCount: 0,
  });
  ui = {};
  root.replaceChildren();
}

/* ======================================================================
   Avisos e utilidades de texto
   ====================================================================== */

function toast(message, kind = 'ok') {
  const el = h('div', { class: 'toast' }, led(kind === 'warn' ? 'red' : 'mint'), h('span', { text: message }));
  // um aviso por vez, como a Dynamic Island: o novo substitui o anterior
  toastRoot.replaceChildren(el);
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

function openModal(card, { dismissOnBackdrop = false, nested = false, onClose = null } = {}) {
  // nested: o modal atual fica escondido (com o que foi digitado) e volta ao fechar o novo
  const parent = nested ? activeModal : null;
  if (parent) {
    parent.backdrop.hidden = true;
    activeModal = null;
  } else {
    closeModal();
  }
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
  activeModal = { backdrop, card, opener, parent, onClose };
  const first = card.querySelector('[data-autofocus]') || card.querySelector(FOCUSABLE);
  first?.focus();
}

function closeModal() {
  if (!activeModal) return;
  const { backdrop, opener, parent, onClose } = activeModal;
  activeModal = null;
  backdrop.remove();
  if (parent) {
    activeModal = parent;
    parent.backdrop.hidden = false;
  } else {
    root.removeAttribute('inert');
  }
  if (opener && opener.isConnected) opener.focus();
  if (onClose) onClose();
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

/* Campo da Chave Secreta: fonte mono, maiúsculas automáticas (também ao colar). */
function secretKeyField() {
  const input = h('input', {
    class: 'input mono', id: 'unlock-secret', type: 'text', autocomplete: 'off', spellcheck: 'false', autocapitalize: 'characters',
    placeholder: 'OW2-XXXXX-XXXXX-…', 'aria-describedby': 'unlock-secret-help',
  });
  input.addEventListener('input', () => {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const upper = input.value.toUpperCase();
    if (upper !== input.value) {
      input.value = upper;
      input.setSelectionRange(start, end);
    }
  });
  const el = h('div', { class: 'field', id: 'unlock-secret-field' },
    h('label', { for: 'unlock-secret', text: 'Chave Secreta' }), input,
    h('p', { class: 'hint', id: 'unlock-secret-help', text: 'Este cofre foi criado em outro computador. Digite a Chave Secreta do seu Kit de emergência.' }));
  return { input, el };
}

function showUnlock(notice = '') {
  const pw = passwordField({ id: 'unlock-password', label: 'Senha mestra', autofocus: true });
  const secret = secretKeyField();
  secret.el.hidden = !state.status?.secret_key_required;
  const error = h('p', { class: 'msg error', id: 'unlock-error', role: 'alert' });
  const submit = h('button', { class: 'btn btn-primary wide', id: 'unlock-submit', type: 'submit', text: 'Abrir cofre' });

  const form = h('form', { novalidate: '' }, pw.el, secret.el, error, submit);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    const typed = pw.input.value;
    const typedSecret = secret.el.hidden ? '' : secret.input.value.trim();
    error.textContent = '';
    submit.disabled = true;
    submit.textContent = 'Abrindo...';
    const r = await call('unlock', typed, typedSecret || null);
    if (r.ok) {
      pw.input.value = '';
      secret.input.value = '';
      if (r.migrated) {
        await showMigrationKit(typed, r);
        return;
      }
      await showEntry();
      return;
    }
    submit.disabled = false;
    submit.textContent = 'Abrir cofre';
    const secretProblem = ['wrong_secret_key', 'invalid_secret_key', 'secret_key_required'].includes(r.error);
    if (r.error === 'secret_key_required') secret.el.hidden = false;
    error.textContent = r.error === 'wrong_secret_key'
      ? 'Chave Secreta não confere com este cofre.'
      : apiMessage(r, 'Não foi possível abrir o cofre.');
    if (secretProblem) {
      secret.input.select();
      secret.input.focus();
    } else {
      pw.input.select();
      pw.input.focus();
    }
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
    if (r.secret_key) {
      showKitScreen({ secretKey: r.secret_key, password: first });
      return;
    }
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
   Kit de emergência (Chave Secreta): tela cheia depois de criar/migrar o cofre
   ====================================================================== */

/* Anel de contagem regressiva dentro de um botão de cópia. */
function countdownRing(seconds) {
  const progress = svg('circle', { class: 'ow-count', cx: 20, cy: 20, r: 18, fill: 'none', stroke: '#1FB894', 'stroke-width': 4, 'stroke-linecap': 'round' });
  progress.style.setProperty('animation-duration', `${seconds}s`);
  const ring = svg('svg', { class: 'ring', width: 22, height: 22, viewBox: '0 0 40 40', 'aria-hidden': 'true' });
  ring.append(svg('circle', { cx: 20, cy: 20, r: 18, fill: 'none', stroke: 'rgba(255,255,255,.16)', 'stroke-width': 4 }), progress);
  return ring;
}

/* Cartão de vidro com a Chave em grupos (OW2-XXXXX-XXXXX-...). */
function kitKeyCard(secretKey) {
  const parts = secretKey.split('-');
  // cada grupo leva o hífen junto, para a quebra de linha nunca deixá-lo sozinho
  const piece = (part, index) => [
    h('span', { class: 'kit-grp', text: part }),
    index < parts.length - 1 ? h('span', { class: 'kit-dash', 'aria-hidden': 'true', text: '-' }) : null,
  ];
  const nodes = parts.slice(0, -2).map((part, index) => h('span', { class: 'kit-unit' }, piece(part, index)));
  // os dois últimos grupos (final do corpo + verificação) ficam juntos na mesma linha
  nodes.push(h('span', { class: 'kit-unit' }, piece(parts[parts.length - 2], parts.length - 2), piece(parts[parts.length - 1], parts.length - 1)));
  return h('div', { class: 'kit-key glass', id: 'kit-key', role: 'group', 'aria-label': 'Chave Secreta' }, nodes);
}

/* Botões "Copiar chave" e "Salvar Kit". As funções devolvem o segredo/senha só no momento do uso. */
function kitActions({ getSecret, getPassword, idPrefix }) {
  const status = h('p', { class: 'msg kit-status', id: `${idPrefix}-status`, role: 'status' });
  const label = [icon('copy', 18, 2.2), 'Copiar chave'];
  const copyButton = h('button', { class: 'btn btn-ghost', id: `${idPrefix}-copy`, type: 'button' }, ...label);
  let copyTimerId = null;
  copyButton.addEventListener('click', async () => {
    const secret = getSecret();
    if (!secret) return;
    const r = await call('copy_text', secret);
    if (!r.ok) {
      if (r.error !== 'locked') toast(apiMessage(r, 'Não foi possível copiar.'), 'warn');
      return;
    }
    const seconds = r.clear_in || 30;
    copyButton.replaceChildren(countdownRing(seconds), `Copiada · limpa em ${seconds} s`);
    clearTimeout(copyTimerId);
    copyTimerId = setTimeout(() => {
      if (copyButton.isConnected) copyButton.replaceChildren(...label.map((item) => (typeof item === 'string' ? item : icon('copy', 18, 2.2))));
    }, seconds * 1000);
  });

  const saveButton = h('button', { class: 'btn btn-primary', id: `${idPrefix}-save`, type: 'button' }, icon('download', 18, 2.2), 'Salvar Kit');
  saveButton.addEventListener('click', async () => {
    const password = getPassword();
    if (!password) return;
    saveButton.disabled = true;
    status.className = 'msg kit-status';
    status.textContent = '';
    const r = await call('save_emergency_kit', password);
    saveButton.disabled = false;
    if (r.ok) {
      status.className = 'msg kit-status ok';
      status.textContent = r.path ? `Kit salvo em ${r.path}` : 'Kit salvo.';
    } else if (r.error === 'cancelled') {
      status.textContent = '';
    } else if (r.error !== 'locked') {
      status.className = 'msg kit-status error';
      status.textContent = apiMessage(r, 'Não foi possível salvar o Kit.');
    }
  });
  return { row: h('div', { class: 'btn-row kit-actions' }, saveButton, copyButton), status };
}

const KIT_LEAD = 'Sem a Chave Secreta e a senha mestra, ninguém abre o cofre — nem você em outro computador. Salve o Kit, imprima e guarde longe do arquivo do cofre.';

/* Depois de uma migração a Api devolve a Chave; se não vier, pede com a senha que acabou de ser digitada. */
async function showMigrationKit(password, response) {
  let secretKey = response.secret_key;
  if (!secretKey) {
    const kit = await call('emergency_kit', password);
    secretKey = kit.ok ? kit.secret_key : '';
  }
  if (!secretKey) {
    await showEntry();
    return;
  }
  showKitScreen({ secretKey, password, migrated: true, backupPath: response.v1_backup_path || '' });
}

function showKitScreen({ secretKey, password, migrated = false, backupPath = '' }) {
  // a chave e a senha só existem nestas variáveis, até sair da tela
  let secret = secretKey;
  let master = password;
  const keepAlive = setInterval(() => { call('touch'); }, 60000);
  const wipe = () => {
    clearInterval(keepAlive);
    secret = null;
    master = null;
    kitWipe = null;
    root.replaceChildren();
  };
  kitWipe = wipe;

  const actions = kitActions({ getSecret: () => secret, getPassword: () => master, idPrefix: 'kit' });
  const saved = h('input', { class: 'ios-switch', type: 'checkbox', role: 'switch', id: 'kit-saved' });
  const proceed = h('button', { class: 'btn btn-primary wide', id: 'kit-continue', type: 'button', disabled: true }, 'Continuar');
  saved.addEventListener('change', () => {
    proceed.disabled = !saved.checked;
  });
  proceed.addEventListener('click', async () => {
    if (proceed.disabled) return;
    wipe();
    await showEntry();
  });

  const blocks = [
    h('div', { class: 'kit-badge', 'aria-hidden': 'true' }, icon('shieldKey', 34, 1.8)),
    h('h1', { class: 'kit-title', text: 'Guarde seu Kit de emergência' }),
    migrated ? h('p', { class: 'notice kit-migrated', id: 'kit-migrated', text: 'Seu cofre foi atualizado para o formato v2, mais seguro.' }) : null,
    h('p', { class: 'kit-lead', text: KIT_LEAD }),
    kitKeyCard(secret),
    actions.row,
    actions.status,
  ];
  if (migrated && backupPath) blocks.push(oldCopyBlock(backupPath));
  blocks.push(
    h('div', { class: 'group' },
      h('label', { class: 'group-row switch-row', for: 'kit-saved' }, h('span', { class: 'row-k grow', text: 'Guardei meu Kit em local seguro' }), saved)),
    proceed);

  root.replaceChildren(h('div', { class: 'kit-screen' }, h('div', { class: 'kit-col ow-in' }, blocks)));
  proceed.disabled = true;
  actions.row.querySelector('button')?.focus();
}

/* Cópia do cofre antigo (formato v1) deixada pela migração. */
function oldCopyBlock(backupPath) {
  const box = h('div', { class: 'group kit-old', id: 'kit-old' });
  const status = h('p', { class: 'msg', id: 'kit-old-status', role: 'status' });
  const button = h('button', { class: 'btn btn-ghost danger', id: 'kit-old-delete', type: 'button' }, 'Apagar cópia antiga');
  button.addEventListener('click', () => confirmDeleteOldCopy(async () => {
    const r = await call('delete_v1_backup');
    if (r.ok || r.error === 'not_found') {
      box.replaceChildren(h('div', { class: 'group-row stacked' },
        h('span', { class: 'row-k', text: 'Cópia do cofre antigo' }),
        h('span', { class: 'row-v', id: 'kit-old-done', text: 'A cópia antiga foi apagada.' })));
      return null;
    }
    return apiMessage(r, 'Não foi possível apagar a cópia antiga.');
  }, status));
  box.append(
    h('div', { class: 'group-row stacked' },
      h('span', { class: 'row-k', text: 'Cópia do cofre antigo' }),
      h('span', { class: 'row-v path', id: 'kit-old-path', text: backupPath }),
      h('span', { class: 'hint kit-old-hint', text: 'Ela ainda abre só com a senha mestra, sem a Chave Secreta. Apague depois de guardar seu Kit.' })),
    h('div', { class: 'group-row' }, status, h('span', { class: 'grow-spacer' }), button));
  return box;
}

function confirmDeleteOldCopy(run, statusEl) {
  const error = h('p', { class: 'msg error', role: 'alert' });
  const confirmButton = h('button', { class: 'btn btn-primary danger', id: 'confirm-delete-old', type: 'button', 'data-autofocus': '' }, 'Apagar');
  confirmButton.addEventListener('click', async () => {
    confirmButton.disabled = true;
    const problem = await run();
    if (problem) {
      confirmButton.disabled = false;
      error.textContent = problem;
      return;
    }
    closeModal();
    toast('Cópia antiga apagada');
  });
  const card = h('div', { class: 'modal narrow', 'aria-labelledby': 'delete-old-title' },
    h('h2', { id: 'delete-old-title', text: 'Apagar a cópia antiga?' }),
    h('p', { class: 'lead', text: 'A cópia antiga ainda abre só com a senha mestra. Apague depois de guardar seu Kit.' }),
    error,
    h('div', { class: 'modal-actions' },
      h('button', { class: 'btn btn-ghost', id: 'cancel-delete-old', type: 'button', onClick: closeModal }, 'Cancelar'),
      confirmButton));
  openModal(card, { dismissOnBackdrop: true });
  if (statusEl) statusEl.textContent = '';
}

/* Sheet dos Ajustes: pede a senha mestra e mostra a Chave; some ao fechar. */
function openKitSheet() {
  let secret = null;
  let master = null;
  const pw = passwordField({ id: 'kit-password', label: 'Senha mestra', autofocus: true });
  const error = h('p', { class: 'msg error', id: 'kit-sheet-error', role: 'alert' });
  const submit = h('button', { class: 'btn btn-primary', id: 'kit-sheet-submit', type: 'submit' }, 'Mostrar Kit');
  const body = h('div', { class: 'kit-sheet-body' });
  const form = h('form', { novalidate: '' },
    h('p', { class: 'lead', text: 'Digite a senha mestra para ver a Chave Secreta deste cofre.' }),
    pw.el, error,
    h('div', { class: 'modal-actions' },
      h('button', { class: 'btn btn-ghost', id: 'kit-sheet-cancel', type: 'button', onClick: closeModal }, 'Cancelar'),
      submit));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    error.textContent = '';
    submit.disabled = true;
    const typed = pw.input.value;
    const r = await call('emergency_kit', typed);
    pw.input.value = '';
    if (!r.ok) {
      submit.disabled = false;
      if (r.error === 'locked') return;
      error.textContent = r.error === 'wrong_password' ? apiMessage(r, 'Senha mestra incorreta.') : apiMessage(r, 'Não foi possível abrir o Kit.');
      pw.input.focus();
      return;
    }
    secret = r.secret_key;
    master = typed;
    const actions = kitActions({ getSecret: () => secret, getPassword: () => master, idPrefix: 'kit-sheet' });
    body.replaceChildren(
      h('p', { class: 'lead', text: 'Guarde esta chave com o Kit impresso. Sem ela e sem a senha mestra, ninguém abre o cofre em outro computador.' }),
      kitKeyCard(secret),
      h('div', { class: 'group' },
        h('div', { class: 'group-row' }, h('span', { class: 'row-k', text: 'Guardada em' }), h('span', { class: 'row-v', id: 'kit-sheet-storage', text: r.key_storage || '' })),
        r.vault_path ? h('div', { class: 'group-row stacked' }, h('span', { class: 'row-k', text: 'Arquivo do cofre' }), h('span', { class: 'row-v path', text: r.vault_path })) : null),
      actions.row,
      actions.status,
      h('div', { class: 'modal-actions' }, h('button', { class: 'btn btn-ghost', id: 'kit-sheet-close', type: 'button', 'data-autofocus': '', onClick: closeModal }, 'Fechar')));
    form.hidden = true;
    body.querySelector('[data-autofocus]')?.focus();
  });

  const card = h('div', { class: 'modal', 'aria-labelledby': 'kit-sheet-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'kit-sheet-title', text: 'Kit de emergência' }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    form, body);
  openModal(card, {
    onClose: () => {
      secret = null;
      master = null;
      body.replaceChildren();
    },
  });
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

/* Bloqueio vindo de fora (bandeja, sessão do Windows, Api): cada janela reage ao seu modo. */
function handleExternalLock() {
  if (quickMode) {
    showQuickLocked();
    return;
  }
  if (kitWipe) {
    kitWipe();
    showEntry('O cofre foi bloqueado.');
    return;
  }
  lockNow('O cofre foi bloqueado.');
}

window.addEventListener('owlock:locked', handleExternalLock);

// A janela do aplicativo chama isto por evaluate_js quando algo fora da interface muda o estado.
window.owlockEvent = (name, arg) => {
  if (name === 'locked') handleExternalLock();
  // a busca rápida pediu para abrir a janela principal nesta conta
  if (name === 'select' && typeof arg === 'string' && state.unlocked) {
    setView('vault');
    goToEntry(arg);
  }
};

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
  await Promise.all([loadOptions(), loadCategories(), loadSettings(), loadServices(), loadBrandIcons()]);
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
    railButton('categories', 'tag', 'Categorias', () => setView('categories')),
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

  ui.tabs = FILTERS.map(([id, label]) =>
    h('button', {
      class: 'btn tab', type: 'button', role: 'tab', id: `tab-${id}`, 'data-filter': id,
      'aria-selected': id === state.filter ? 'true' : 'false',
      onClick: () => setFilter(id),
    }, label));

  ui.tabsBox = h('div', { class: 'segmented', role: 'tablist', 'aria-label': 'Filtro', 'data-index': '0', 'data-cols': String(FILTERS.length) },
    h('span', { class: 'seg-thumb', 'aria-hidden': 'true' }), ui.tabs);
  ui.catStrip = h('div', { class: 'cat-strip', id: 'cat-strip', role: 'group', 'aria-label': 'Categorias' });
  ui.catStripWrap = makeScrollStrip(ui.catStrip);
  ui.statsMobile = h('div', { class: 'stats stats-mobile' });
  ui.rows = h('div', { class: 'rows', id: 'entry-list' });

  const newButton = h('button', { class: 'btn btn-primary new-btn', id: 'new-entry', type: 'button', onClick: () => openEntryForm(null) },
    icon('plus', 16, 2.4), h('span', { class: 'label', text: 'Nova conta' }));

  return h('section', { class: 'list-col', 'aria-label': 'Contas' },
    h('div', { class: 'list-head' }, h('h2', { text: 'Cofre' }), ui.timer),
    ui.statsMobile,
    h('label', { class: 'search' }, icon('search', 16), ui.search, ui.searchClear),
    ui.catStripWrap,
    ui.tabsBox,
    ui.rows,
    newButton);
}

function buildMain() {
  ui.statsDesktop = h('div', { class: 'stats stats-desktop' });
  ui.detail = h('div', { class: 'detail-slot', id: 'detail' });
  ui.paneVault = h('div', { class: 'pane pane-vault' }, ui.statsDesktop, ui.detail);
  ui.paneCats = h('div', { class: 'pane pane-categories' });
  ui.paneGen = h('div', { class: 'pane pane-generator' });
  ui.paneSettings = h('div', { class: 'pane pane-settings' });
  ui.paneLib = h('div', { class: 'pane pane-library' });
  return h('main', { class: 'main' }, ui.paneVault, ui.paneCats, ui.paneGen, ui.paneSettings, ui.paneLib);
}

function setView(view) {
  if (state.view === 'vault' && view !== 'vault') {
    hideReveal();
    clearHistReveal();
  }
  state.view = view;
  ui.shell.dataset.view = view;
  for (const button of ui.shell.querySelectorAll('.rail-btn[data-view]')) {
    const here = button.dataset.view === (view === 'library' ? 'settings' : view);
    if (here) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
  ui.paneCats.replaceChildren();
  ui.paneGen.replaceChildren();
  ui.paneSettings.replaceChildren();
  ui.paneLib.replaceChildren();
  ui.catView = null;
  ui.libList = null;
  state.gen = null;
  if (view === 'categories') buildCategoriesView();
  if (view === 'generator') buildGenerator();
  if (view === 'settings') buildSettings();
  if (view === 'library') buildLibraryView();
}

function setScreen(screen) {
  state.screen = screen;
  ui.shell.dataset.screen = screen;
}

function syncTabs() {
  for (const tab of ui.tabs) tab.setAttribute('aria-selected', tab.dataset.filter === state.filter ? 'true' : 'false');
  ui.tabsBox.dataset.index = String(Math.max(0, FILTERS.findIndex(([id]) => id === state.filter)));
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
  if (state.filter === 'all' && !state.query && !state.categoryFilter) {
    state.weakCount = state.entries.filter((entry) => entry.strength.score <= 2).length;
  }
  if (state.selected) {
    const fresh = state.entries.find((entry) => entry.id === state.selected.id);
    if (fresh) state.selected = fresh;
  }
  renderStats();
  renderCategories();
  renderList();
}

/* ---------- favoritas ---------- */

function paintStar(button, favorite) {
  button.classList.toggle('on', favorite);
  button.setAttribute('aria-pressed', favorite ? 'true' : 'false');
  button.setAttribute('aria-label', favorite ? 'Remover dos favoritos' : 'Favoritar');
}

function starButton(entry, where) {
  const button = h('button', {
    class: `btn star-btn star-${where}`, type: 'button', 'data-star-id': entry.id,
    ...(where === 'detail' ? { id: 'detail-star' } : {}),
  }, icon('star', where === 'detail' ? 20 : 16, 2));
  paintStar(button, Boolean(entry.favorite));
  button.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleFavorite(entry);
  });
  return button;
}

async function toggleFavorite(entry) {
  const r = await call('toggle_favorite', entry.id);
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r, 'Não foi possível atualizar os favoritos.'), 'warn');
    return;
  }
  entry.favorite = r.favorite;
  if (state.selected?.id === entry.id) state.selected.favorite = r.favorite;
  for (const button of document.querySelectorAll(`[data-star-id="${CSS.escape(entry.id)}"]`)) {
    paintStar(button, r.favorite);
    if (r.favorite) {
      button.classList.remove('pop');
      void button.offsetWidth; // reinicia a animação de mola
      button.classList.add('pop');
    }
  }
  // deixa a animação terminar antes de reordenar (favoritas vão para o topo)
  setTimeout(() => {
    if (state.unlocked) loadEntries();
  }, 480);
}

function statCard(value, longLabel, shortLabel, tone, delay, legend = '') {
  const card = h('div', { class: `stat ${tone}` },
    led(tone === 'red' ? 'red' : 'mint'),
    h('b', { text: String(value) }),
    h('span', {}, h('span', { class: 'long', text: longLabel }), h('span', { class: 'short', text: shortLabel })),
    legend ? h('small', { class: 'stat-legend', id: 'attention-legend', text: legend }) : null);
  if (legend) card.setAttribute('title', legend);
  if (delay != null) {
    card.classList.add('ow-in');
    setDelay(card, delay);
  }
  return card;
}

/* Detalhamento do cartão de atenção: "2 fracas · 1 repetida · 1 antiga" (sem zeros). */
function attentionLegend() {
  const { reused = 0, stale = 0 } = state.stats;
  const weak = typeof state.stats.weak === 'number' ? state.stats.weak : state.weakCount;
  const parts = [];
  if (weak > 0) parts.push(`${weak} ${plural(weak, 'fraca', 'fracas')}`);
  if (reused > 0) parts.push(`${reused} ${plural(reused, 'repetida', 'repetidas')}`);
  if (stale > 0) parts.push(`${stale} ${plural(stale, 'antiga', 'antigas')}`);
  return parts.join(' · ');
}

function renderStats() {
  const { total, with_2fa: withTwofa, attention } = state.stats;
  const legend = attentionLegend();
  const build = (animated) => [
    statCard(total, plural(total, 'conta no cofre', 'contas no cofre'), plural(total, 'conta', 'contas'), '', animated ? 0 : null),
    statCard(withTwofa, 'com verificação em 2 etapas', 'com 2FA', 'mint', animated ? 60 : null),
    statCard(attention, plural(attention, 'senha precisa de atenção', 'senhas precisam de atenção'), 'atenção', attention > 0 ? 'red' : 'mint', animated ? 120 : null, legend),
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
    const tone = entryTone(entry);
    const warn = tone !== 'mint';
    const row = h('button', {
      class: 'btn row' + (state.selected?.id === entry.id ? ' is-selected' : ''),
      type: 'button', 'data-id': entry.id,
      onClick: () => selectEntry(entry.id, true),
    },
      monoBadge(entry),
      h('span', { class: 'row-text' },
        h('span', { class: 'row-name', text: entry.service }),
        h('span', { class: 'row-user', text: entry.username || '' })),
      h('span', { class: 'star-slot', 'aria-hidden': 'true' }),
      h('span', { class: `led ${tone}`, role: 'img', 'aria-label': warn ? 'Precisa de atenção' : 'Segura' }));
    const item = h('div', { class: 'row-item' }, row, starButton(entry, 'row'));
    setDelay(item, Math.min(index, 12) * 55);
    return item;
  });
  ui.rows.replaceChildren(...rows);
}

/* ---------- ícone da conta (ladrilho de app com a marca, ou monograma) ---------- */

const HEX_COLOR = /^#[0-9A-F]{6}$/i;
const ICON_URL = /^icons\/brands\/[a-z0-9-]+\.svg$/;
const GRAPHITE = '#2A2B31';

function relativeLuminance(hex) {
  const channel = (offset) => {
    const v = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

/* Ladrilho da marca: fundo na cor oficial (grafite se for escura demais) e desenho branco.
   Sem desenho válido, volta ao monograma com o degradê da categoria. */
function iconTile({ url, color, letter, category = null, size = 40 }) {
  const valid = typeof url === 'string' && ICON_URL.test(url);
  if (!valid) {
    const mono = h('span', { class: 'mono-badge', 'aria-hidden': 'true', text: letter });
    if (category) {
      mono.classList.add('cat');
      mono.style.setProperty('--cat', category.color_hex);
    }
    mono.style.setProperty('--s', `${size}px`);
    return mono;
  }
  const brand = typeof color === 'string' && HEX_COLOR.test(color) ? color : GRAPHITE;
  const dark = relativeLuminance(brand) < 0.08;
  const tile = h('span', { class: 'acc-icon' + (dark ? ' dark' : ''), 'aria-hidden': 'true' });
  tile.style.setProperty('--tile', dark ? GRAPHITE : brand);
  tile.style.setProperty('--s', `${size}px`);
  const img = h('img', { src: url, alt: '', draggable: 'false', decoding: 'async' });
  img.addEventListener('error', () => {
    tile.classList.add('broken');
    tile.replaceChildren(h('span', { class: 'acc-letter', text: letter }));
  });
  tile.append(img);
  return tile;
}

function monoBadge(entry, size = 40) {
  return iconTile({ url: entry.icon_url, color: entry.icon_color, letter: monogram(entry), category: entry.category, size });
}

function monogram(entry) {
  return (entry.service.trim()[0] || '?').toUpperCase();
}

function serviceTile(service, size = 36) {
  return iconTile({ url: service.icon_url, color: service.color, letter: (service.name.trim()[0] || '?').toUpperCase(), size });
}

/* ---------- biblioteca de serviços (dados) ---------- */

async function loadServices() {
  const r = await call('list_services', '');
  if (r.ok && state.unlocked) state.services = r.services || [];
}

async function loadBrandIcons() {
  const r = await call('brand_icons');
  if (r.ok) state.brandIcons = r.icons || [];
}

function libraryDomain(url) {
  return siteHost(url || '').replace(/^www\./, '');
}

function selectEntry(id, openDetail = false) {
  const entry = state.entries.find((item) => item.id === id);
  if (!entry) return;
  if (state.selected?.id !== id) {
    hideReveal();
    clearHistReveal();
  }
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

  ui.historySlot = h('div', { class: 'settings-stack', id: 'history-slot' });
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
  if (entry.url) {
    infoRows.splice(1, 0, h('div', { class: 'group-row', id: 'detail-site-row' },
      h('span', { class: 'row-k', text: 'Site' }),
      h('span', { class: 'row-v', id: 'detail-site', text: siteHost(entry.url) }),
      h('button', { class: 'btn btn-chip with-icon', id: 'open-site', type: 'button', onClick: () => openSite(entry) }, icon('external', 14, 2.2), 'Abrir site')));
  } else if (entry.service_key) {
    const service = state.services.find((item) => item.key === entry.service_key);
    if (service && service.login_url) {
      infoRows.splice(1, 0, h('div', { class: 'group-row', id: 'detail-site-row' },
        h('span', { class: 'row-k', text: 'Site' }),
        h('span', { class: 'row-v site-lib' },
          h('span', { id: 'detail-site', text: libraryDomain(service.login_url) }),
          h('span', { class: 'badge-pill', id: 'detail-site-source', text: 'da biblioteca' })),
        h('button', { class: 'btn btn-chip with-icon', id: 'open-login', type: 'button', onClick: () => openSite(entry, true) }, icon('external', 14, 2.2), 'Abrir login')));
    }
  }
  if (entry.notes) {
    infoRows.push(h('div', { class: 'group-row stacked' },
      h('span', { class: 'row-k', text: 'Notas' }),
      h('span', { class: 'row-v', text: entry.notes })));
  }

  const card = h('article', { class: first ? 'detail ow-in' : 'detail ow-swap', 'aria-label': `Detalhes de ${entry.service}` },
    h('button', { class: 'btn back-btn', id: 'back', type: 'button', onClick: () => setScreen('list') }, icon('back', 22, 2.2), 'Cofre'),
    h('header', { class: 'detail-head' },
      monoBadge(entry, 64),
      h('div', { class: 'detail-title' },
        h('h1', { id: 'detail-name', text: entry.service }),
        entry.category ? detailCategory(entry.category) : null,
        h('span', { text: `Atualizada ${timeAgo(entry.updated_at)}`.trim() })),
      starButton(entry, 'detail'),
      h('button', { class: 'btn btn-ghost small', id: 'edit-entry', type: 'button', onClick: () => openEntryForm(entry) }, 'Editar')),
    healthBlock(entry),
    h('div', { class: 'group' }, infoRows),
    h('div', { class: 'pw-box' },
      h('div', { class: 'pw-head' }, h('span', { class: 'k', text: 'Senha' }),
        entry.history_count > 0 ? h('span', { class: 'badge-pill', id: 'history-badge', text: `${entry.history_count} ${plural(entry.history_count, 'versão anterior', 'versões anteriores')}` }) : null,
        ui.revealButton),
      ui.pwText,
      h('div', { class: `meter ${strengthClass(score)}` },
        h('div', { class: 'meter-track' }, barFill),
        h('span', { class: 'meter-label', id: 'strength-label', text: strengthText })),
      h('div', { class: 'pw-actions' },
        copyButton,
        h('button', { class: 'btn btn-ghost', id: 'copy-username', type: 'button', onClick: () => copyField(entry, 'username') }, 'Copiar login'),
        h('button', { class: 'btn btn-ghost danger', id: 'delete-entry', type: 'button', onClick: () => confirmDelete(entry) }, 'Excluir'))),
    ui.historySlot);

  if (first) setDelay(card, 140);
  ui.detail.append(card);
  paintPassword(false);
  loadHistory(entry);
  if (entry.reused) loadReusedWith(entry);
}

/* ---------- saúde da senha (avisos em pílulas) ---------- */

function healthBlock(entry) {
  const pills = [];
  if (entry.reused) {
    const n = entry.reused_count || 1;
    pills.push(h('span', { class: 'health-pill red', id: 'health-reused', text: `Repetida em ${n} ${plural(n, 'conta', 'contas')}` }));
  }
  if (entry.stale) {
    pills.push(h('span', { class: 'health-pill amber', id: 'health-stale', text: 'Sem troca há mais de 1 ano' }));
  }
  if (!pills.length) return null;
  return h('div', { class: 'health', id: 'health' },
    h('div', { class: 'health-pills' }, pills),
    entry.reused ? h('div', { class: 'health-with', id: 'health-with' }) : null);
}

async function loadReusedWith(entry) {
  const r = await call('get_entry', entry.id);
  if (!r.ok || state.selected?.id !== entry.id) return;
  const holder = document.getElementById('health-with');
  const list = r.entry?.reused_with || [];
  if (!holder || !list.length) return;
  holder.replaceChildren(
    h('span', { class: 'health-with-label', text: 'Mesma senha em:' }),
    ...list.map((other) => h('button', {
      class: 'btn btn-chip health-link', type: 'button', 'data-id': other.id, onClick: () => goToEntry(other.id),
    }, other.service)));
}

/* Seleciona uma conta mesmo que ela esteja fora do filtro atual. */
async function goToEntry(id) {
  if (!state.entries.some((entry) => entry.id === id)) {
    state.query = '';
    state.filter = 'all';
    state.categoryFilter = '';
    ui.search.value = '';
    ui.searchClear.hidden = true;
    syncTabs();
    await loadEntries();
  }
  selectEntry(id, true);
  ui.rows.querySelector(`.row[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' });
}

/* ---------- site e histórico de senhas ---------- */

function siteHost(url) {
  try {
    return new URL(url).host || url;
  } catch {
    return url;
  }
}

async function openSite(entry, fromLibrary = false) {
  const r = await call('open_url', entry.id);
  if (r.ok) toast(fromLibrary ? 'Abrindo o login...' : 'Abrindo o site...');
  else if (r.error !== 'locked') toast(apiMessage(r, fromLibrary ? 'Não foi possível abrir o login.' : 'Não foi possível abrir o site.'), 'warn');
}

const DATE_FORMAT = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'short', year: 'numeric' });

function shortDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : DATE_FORMAT.format(date);
}

function clearHistReveal() {
  clearTimeout(histTimer);
  if (!state.histReveal) return;
  state.histReveal = null;
  if (ui.historySlot && ui.historySlot.isConnected) paintHistory();
}

async function loadHistory(entry) {
  state.history = null;
  const r = await call('get_password_history', entry.id);
  if (!r.ok || state.selected?.id !== entry.id || !ui.historySlot || !ui.historySlot.isConnected) return;
  state.history = { id: entry.id, created_at: r.created_at, history: r.history || [] };
  paintHistory();
}

function paintHistory(animateIndex = -1) {
  const data = state.history;
  if (!data || !ui.historySlot) return;
  const entryId = data.id;
  const rows = [h('div', { class: 'group-row', id: 'history-created' },
    h('span', { class: 'row-k grow', text: 'Criada em' }),
    h('span', { class: 'row-v', text: shortDate(data.created_at) }))];
  if (!data.history.length) {
    rows.push(h('div', { class: 'group-row', id: 'history-empty' }, h('span', { class: 'row-k grow', text: 'Esta senha nunca foi alterada.' })));
  }
  for (const item of data.history) {
    const shown = state.histReveal && state.histReveal.id === entryId && state.histReveal.index === item.index;
    const pw = h('div', { class: 'hist-pw', id: `hist-pw-${item.index}` });
    if (shown) {
      pw.replaceChildren(...[...state.histReveal.text].map((ch, i) => {
        const span = h('span', { class: animateIndex === item.index ? 'ow-char' : '', text: ch });
        if (animateIndex === item.index) setDelay(span, i * 28);
        return span;
      }));
    } else {
      pw.append(h('span', { class: 'masked', 'aria-label': 'Senha oculta', text: '•••' }));
    }
    rows.push(h('div', { class: 'group-row hist-row', id: `hist-row-${item.index}` },
      h('span', { class: `led ${strengthTone(item.strength.score)}`, role: 'img', 'aria-label': `Força: ${item.strength.label}` }),
      h('div', { class: 'hist-info' },
        h('span', { class: 'hist-title', text: 'Senha anterior' }),
        h('span', { class: 'hist-sub', text: `alterada em ${shortDate(item.changed_at)}` }),
        pw),
      h('div', { class: 'hist-actions' },
        h('button', { class: 'btn btn-chip', id: `hist-show-${item.index}`, type: 'button', 'aria-pressed': shown ? 'true' : 'false', onClick: () => toggleHistReveal(entryId, item.index) }, shown ? 'Ocultar' : 'Mostrar'),
        h('button', { class: 'btn btn-chip', id: `hist-copy-${item.index}`, type: 'button', onClick: () => copyHistory(entryId, item.index) }, 'Copiar'))));
  }
  ui.historySlot.replaceChildren(h('h2', { class: 'group-title', text: 'Histórico de senhas' }), h('div', { class: 'group', id: 'history-group' }, rows));
}

async function toggleHistReveal(entryId, index) {
  if (state.histReveal && state.histReveal.id === entryId && state.histReveal.index === index) {
    clearHistReveal();
    return;
  }
  const r = await call('reveal_history_password', entryId, index);
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r), 'warn');
    return;
  }
  if (state.selected?.id !== entryId) return;
  state.histReveal = { id: entryId, index, text: r.password };
  paintHistory(index);
  clearTimeout(histTimer);
  histTimer = setTimeout(clearHistReveal, REVEAL_AUTOHIDE_MS);
}

async function copyHistory(entryId, index) {
  const r = await call('copy_history_password', entryId, index);
  if (r.ok) toast('Senha anterior copiada');
  else if (r.error !== 'locked') toast(apiMessage(r), 'warn');
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

/* Controle segmentado genérico (Automático / Letra / Escolher etc.). */
function segmentedControl({ id, label, options, value, onChange }) {
  const box = h('div', { class: 'segmented', id, role: 'radiogroup', 'aria-label': label, 'data-cols': String(options.length), 'data-index': '0' },
    h('span', { class: 'seg-thumb', 'aria-hidden': 'true' }));
  const buttons = options.map((option) => h('button', {
    class: 'btn tab', type: 'button', role: 'radio', id: `${id}-${option.value}`, 'data-value': option.value,
    onClick: () => {
      set(option.value);
      onChange(option.value);
    },
  }, option.label));
  box.append(...buttons);
  function set(next) {
    box.dataset.index = String(Math.max(0, options.findIndex((option) => option.value === next)));
    for (const button of buttons) button.setAttribute('aria-checked', button.dataset.value === next ? 'true' : 'false');
  }
  set(value);
  return { el: box, set };
}

/* Grade pesquisável de ícones de marca, em um modal por cima do atual. */
function openIconPicker({ current = '', onPick, onCancel }) {
  let chosen = false;
  const search = h('input', {
    class: 'row-input', id: 'icon-search', type: 'text', placeholder: 'Buscar ícone', autocomplete: 'off', spellcheck: 'false',
    'aria-label': 'Buscar ícone', 'data-autofocus': '',
  });
  const grid = h('div', { class: 'brand-grid', id: 'brand-grid', role: 'radiogroup', 'aria-label': 'Ícones' });
  const empty = h('p', { class: 'hint', id: 'icon-empty', text: 'Nenhum ícone encontrado.' });
  empty.hidden = true;
  const paint = () => {
    const needle = search.value.trim().toLowerCase();
    const list = state.brandIcons.filter((item) => !needle || item.title.toLowerCase().includes(needle) || item.slug.includes(needle));
    grid.replaceChildren(...list.map((item) => {
      const selected = item.slug === current;
      return h('button', {
        class: 'btn brand-cell', type: 'button', role: 'radio', 'aria-checked': selected ? 'true' : 'false',
        id: `brand-${item.slug}`, 'data-slug': item.slug, 'aria-label': item.title,
        onClick: () => {
          chosen = true;
          closeModal();
          onPick(item.slug);
        },
      }, iconTile({ url: item.icon_url, color: item.color, letter: (item.title[0] || '?').toUpperCase(), size: 44 }),
      h('span', { class: 'brand-name', text: item.title }));
    }));
    empty.hidden = list.length > 0;
  };
  search.addEventListener('input', paint);
  paint();
  const card = h('div', { class: 'modal', 'aria-labelledby': 'icon-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'icon-title', text: 'Escolher ícone' }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    h('label', { class: 'search' }, icon('search', 16), search),
    h('div', { class: 'brand-scroll' }, grid, empty));
  openModal(card, { nested: true, dismissOnBackdrop: true, onClose: () => { if (!chosen && onCancel) onCancel(); } });
}

function openEntryForm(entry) {
  const editing = Boolean(entry);
  const serviceInput = h('input', {
    class: 'row-input', id: 'form-service', type: 'text', autocomplete: 'off', value: editing ? entry.service : '', 'data-autofocus': '', placeholder: 'Obrigatório',
    role: 'combobox', 'aria-autocomplete': 'list', 'aria-expanded': 'false', 'aria-controls': 'service-suggestions', spellcheck: 'false',
  });
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
  const categoryPicker = h('div', { class: 'cat-wrap-list', id: 'form-categories', role: 'radiogroup', 'aria-label': 'Categoria' });
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

  const urlInput = h('input', { class: 'row-input', id: 'form-url', type: 'text', autocomplete: 'off', spellcheck: 'false', inputmode: 'url', placeholder: 'exemplo.com', value: editing ? entry.url || '' : '' });
  const urlError = h('p', { class: 'msg error', id: 'form-url-error', role: 'alert' });
  const urlNote = h('p', { class: 'msg note', id: 'form-url-note' }, icon('check', 13, 2.6), 'Link preenchido pela biblioteca');
  urlNote.hidden = true;

  /* --- biblioteca: sugestões, preenchimento do link e ícone --- */
  let autoLink = null; // último link preenchido pela biblioteca (some se o usuário editar o Site)
  let touched = false; // o usuário digitou no Serviço
  let lastMatch = null;
  let lookedFor = null;
  let pending = Promise.resolve();
  let suggestions = [];
  let activeIndex = -1;

  const suggestBox = h('div', { class: 'suggest', id: 'service-suggestions', role: 'listbox', 'aria-label': 'Serviços da biblioteca' });
  suggestBox.hidden = true;

  let iconMode = editing ? (entry.icon === 'none' ? 'letter' : entry.icon ? 'pick' : 'auto') : 'auto';
  let iconSlug = editing && entry.icon && entry.icon !== 'none' ? entry.icon : '';
  const iconPreview = h('span', { class: 'icon-preview', id: 'form-icon-preview' });
  const paintIconPreview = () => {
    const letter = (serviceInput.value.trim()[0] || '?').toUpperCase();
    let tile;
    if (iconMode === 'pick') {
      const brand = state.brandIcons.find((item) => item.slug === iconSlug);
      tile = brand ? iconTile({ url: brand.icon_url, color: brand.color, letter, size: 32 })
        : iconTile({ url: editing ? entry.icon_url : null, color: editing ? entry.icon_color : null, letter, size: 32 });
    } else if (iconMode === 'auto') {
      const source = touched ? lastMatch : (editing ? { icon_url: entry.icon_url, color: entry.icon_color } : null);
      tile = iconTile({ url: source?.icon_url, color: source?.color || source?.icon_color, letter, size: 32 });
    } else {
      tile = iconTile({ letter, size: 32 });
    }
    iconPreview.replaceChildren(tile);
  };
  const iconSeg = segmentedControl({
    id: 'form-icon', label: 'Ícone',
    options: [{ value: 'auto', label: 'Automático' }, { value: 'letter', label: 'Letra' }, { value: 'pick', label: 'Escolher' }],
    value: iconMode,
    onChange: (mode) => {
      if (mode !== 'pick') {
        iconMode = mode;
        paintIconPreview();
        return;
      }
      openIconPicker({
        current: iconSlug,
        onPick: (slug) => {
          iconSlug = slug;
          iconMode = 'pick';
          iconSeg.set('pick');
          paintIconPreview();
        },
        onCancel: () => iconSeg.set(iconMode),
      });
    },
  });

  const closeSuggestions = () => {
    suggestBox.hidden = true;
    suggestions = [];
    activeIndex = -1;
    serviceInput.setAttribute('aria-expanded', 'false');
    serviceInput.removeAttribute('aria-activedescendant');
  };
  const markActive = () => {
    [...suggestBox.children].forEach((node, index) => {
      node.setAttribute('aria-selected', index === activeIndex ? 'true' : 'false');
      node.classList.toggle('is-active', index === activeIndex);
    });
    if (activeIndex >= 0) {
      serviceInput.setAttribute('aria-activedescendant', `suggest-opt-${activeIndex}`);
      suggestBox.children[activeIndex]?.scrollIntoView({ block: 'nearest' });
    } else {
      serviceInput.removeAttribute('aria-activedescendant');
    }
  };
  const applyLink = (service) => {
    if (!service || !service.login_url) return;
    const current = urlInput.value.trim();
    if (current === '' || (autoLink && current === autoLink)) {
      urlInput.value = service.login_url;
      autoLink = service.login_url;
      urlNote.hidden = false;
    }
  };
  const chooseSuggestion = (service) => {
    serviceInput.value = service.name;
    touched = true;
    lastMatch = service;
    lookedFor = service.name.trim();
    applyLink(service);
    closeSuggestions();
    paintIconPreview();
    serviceInput.focus();
  };
  const paintSuggestions = () => {
    if (!suggestions.length || document.activeElement !== serviceInput) {
      closeSuggestions();
      return;
    }
    suggestBox.replaceChildren(...suggestions.map((service, index) => h('div', {
      class: 'suggest-item', role: 'option', id: `suggest-opt-${index}`, 'aria-selected': 'false', 'data-key': service.key,
      onMousedown: (event) => event.preventDefault(),
      onClick: () => chooseSuggestion(service),
      onMousemove: () => {
        if (activeIndex !== index) {
          activeIndex = index;
          markActive();
        }
      },
    }, serviceTile(service, 32),
    h('span', { class: 'suggest-text' },
      h('span', { class: 'suggest-name', text: service.name }),
      h('span', { class: 'suggest-domain', text: libraryDomain(service.login_url) })))));
    suggestBox.hidden = false;
    serviceInput.setAttribute('aria-expanded', 'true');
    activeIndex = -1;
    markActive();
  };
  const runLookup = async (value) => {
    const r = await call('lookup_service', value);
    if (!r.ok) return null;
    // respostas atrasadas não sobrescrevem o estado do texto atual
    if (serviceInput.value.trim() === value) {
      lastMatch = r.match || null;
      lookedFor = value;
      suggestions = r.suggestions || [];
      if (iconMode === 'auto') paintIconPreview();
    }
    return r;
  };
  const lookupSoon = debounce(async () => {
    const value = serviceInput.value.trim();
    if (!value) {
      lastMatch = null;
      lookedFor = '';
      closeSuggestions();
      paintIconPreview();
      return;
    }
    const r = await runLookup(value);
    if (r && serviceInput.value.trim() === value) paintSuggestions();
  }, 120);

  serviceInput.addEventListener('input', () => {
    touched = true;
    paintIconPreview();
    lookupSoon();
  });
  serviceInput.addEventListener('keydown', (event) => {
    const open = !suggestBox.hidden && suggestions.length > 0;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!open) return;
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      activeIndex = (activeIndex + step + suggestions.length) % suggestions.length;
      markActive();
    } else if (event.key === 'Enter' && open && activeIndex >= 0) {
      event.preventDefault();
      chooseSuggestion(suggestions[activeIndex]);
    } else if (event.key === 'Escape' && open) {
      event.preventDefault();
      event.stopPropagation();
      closeSuggestions();
    }
  });
  serviceInput.addEventListener('blur', () => {
    closeSuggestions();
    if (!touched) return;
    const value = serviceInput.value.trim();
    if (!value) return;
    pending = (async () => {
      let match = lookedFor === value ? lastMatch : null;
      if (lookedFor !== value) {
        const r = await runLookup(value);
        match = r ? r.match : null;
      }
      if (match && serviceInput.value.trim() === value) {
        serviceInput.value = match.name;
        applyLink(match);
        paintIconPreview();
      }
    })();
  });
  urlInput.addEventListener('input', () => {
    autoLink = null;
    urlNote.hidden = true;
  });
  paintIconPreview();

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
    h('div', { class: 'suggest-wrap' },
      h('div', { class: 'group' },
        h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-service', text: 'Serviço *' }), serviceInput),
        h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-username', text: 'Login / e-mail' }), userInput),
        h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-url', text: 'Site' }), urlInput)),
      suggestBox),
    urlNote,
    urlError,
    h('div', { class: 'group' },
      h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-password', text: 'Senha' }), pwInput, showButton, genButton)),
    h('div', { class: 'form-meter' }, meter.el),
    h('div', { class: 'group' },
      h('label', { class: 'group-row switch-row', for: 'form-2fa' }, h('span', { class: 'row-k grow', text: 'Verificação em duas etapas (2FA)' }), twofaBox),
      h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'form-2fa-app', text: 'App autenticador' }), twofaApp)),
    h('div', { class: 'group' },
      h('div', { class: 'group-row stacked' },
        h('div', { class: 'icon-head' }, h('span', { class: 'row-k', id: 'form-icon-label', text: 'Ícone' }), iconPreview),
        iconSeg.el),
      h('div', { class: 'group-row stacked' }, h('span', { class: 'row-k', id: 'form-cat-label', text: 'Categoria' }), categoryPicker),
      h('div', { class: 'group-row stacked' }, h('label', { class: 'row-k', for: 'form-notes', text: 'Notas' }), notes)),
    error,
    h('div', { class: 'modal-actions' }, cancel, submit));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    await pending;
    error.textContent = '';
    serviceInput.parentElement.classList.remove('invalid');
    urlInput.parentElement.classList.remove('invalid');
    urlError.textContent = '';
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
      url: urlInput.value.trim(),
      icon: iconMode === 'letter' ? 'none' : iconMode === 'pick' ? iconSlug : '',
      has_2fa: twofaBox.checked,
      twofa_app: twofaBox.checked ? twofaApp.value.trim() : '',
      notes: notes.value,
    };
    if (editing) data.id = entry.id;
    submit.disabled = true;
    submit.textContent = 'Salvando...';
    const r = await call('save_entry', data);
    if (!r.ok) {
      if (r.error === 'locked') return;
      submit.disabled = false;
      submit.textContent = 'Salvar';
      if (r.error === 'invalid_url') {
        urlInput.parentElement.classList.add('invalid');
        urlError.textContent = apiMessage(r, 'Endereço do site inválido.');
        urlInput.focus();
        return;
      }
      error.textContent = apiMessage(r, 'Não foi possível salvar a conta.');
      return;
    }
    pwInput.value = '';
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
  clearHistReveal();
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
  if (state.view === 'categories' && ui.catView) renderCategoryGroup();
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
  if (!ui.catStrip || !ui.catStrip.isConnected) return;
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
  ui.catStripWrap?.update();
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

/* Tela Categorias */
function buildCategoriesView() {
  ui.catView = h('div', { class: 'settings-stack ow-in', id: 'cat-view' });
  renderCategoryGroup();
  ui.paneCats.replaceChildren(
    h('div', { class: 'page-title' }, h('h1', { text: 'Categorias' }), h('p', { text: 'Organize as contas com cores e ícones.' })),
    ui.catView);
}

function renderCategoryGroup() {
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
  ui.catView.replaceChildren(h('div', { class: 'group', id: 'category-group' }, rows));
}

/* Faixa rolável: setas, roda vertical e arrastar com o mouse. */
function makeScrollStrip(strip) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const left = h('button', { class: 'btn strip-arrow left', id: 'cat-prev', type: 'button', 'aria-label': 'Categorias anteriores', tabindex: '-1' }, icon('chevronLeft', 16, 2.4));
  const right = h('button', { class: 'btn strip-arrow right', id: 'cat-next', type: 'button', 'aria-label': 'Próximas categorias', tabindex: '-1' }, icon('chevron', 16, 2.4));
  const wrap = h('div', { class: 'cat-strip-wrap' }, strip, left, right);

  const update = () => {
    const max = strip.scrollWidth - strip.clientWidth;
    const showLeft = strip.scrollLeft > 2;
    const showRight = max > 2 && strip.scrollLeft < max - 2;
    for (const [button, on] of [[left, showLeft], [right, showRight]]) {
      button.classList.toggle('is-on', on);
      button.tabIndex = on ? 0 : -1;
      button.setAttribute('aria-hidden', on ? 'false' : 'true');
    }
  };
  const nudge = (direction) => strip.scrollBy({ left: direction * Math.max(120, strip.clientWidth * 0.7), behavior: reduce.matches ? 'auto' : 'smooth' });
  left.addEventListener('click', () => nudge(-1));
  right.addEventListener('click', () => nudge(1));
  strip.addEventListener('scroll', update, { passive: true });
  if (typeof ResizeObserver === 'function') new ResizeObserver(update).observe(strip);
  window.addEventListener('resize', update);

  strip.addEventListener('wheel', (event) => {
    if (strip.scrollWidth <= strip.clientWidth || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    strip.scrollLeft += event.deltaY;
    event.preventDefault();
  }, { passive: false });

  let drag = null;
  let suppressClick = false;
  strip.addEventListener('pointerdown', (event) => {
    if (event.pointerType !== 'mouse' || event.button !== 0) return;
    drag = { x: event.clientX, left: strip.scrollLeft, moved: false, id: event.pointerId };
  });
  strip.addEventListener('pointermove', (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x;
    if (!drag.moved && Math.abs(dx) > 5) {
      drag.moved = true;
      strip.classList.add('dragging');
      strip.setPointerCapture(event.pointerId);
    }
    if (drag.moved) strip.scrollLeft = drag.left - dx;
  });
  const endDrag = (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    if (drag.moved) {
      suppressClick = true;
      setTimeout(() => { suppressClick = false; }, 0);
      strip.classList.remove('dragging');
    }
    drag = null;
  };
  strip.addEventListener('pointerup', endDrag);
  strip.addEventListener('pointercancel', endDrag);
  strip.addEventListener('click', (event) => {
    if (suppressClick) {
      event.stopPropagation();
      event.preventDefault();
    }
  }, true);

  wrap.update = update;
  return wrap;
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

  ui.protection = h('div', { class: 'settings-stack ow-in', id: 'protection' });
  renderProtection();
  ui.backupsBox = h('div', { class: 'settings-stack ow-in', id: 'backups' });
  ui.desktopBox = h('div', { class: 'settings-stack ow-in', id: 'desktop' });
  ui.desktopBox.hidden = true;
  const catCount = state.categories.length;
  ui.paneSettings.replaceChildren(
    h('div', { class: 'page-title' }, h('h1', { text: 'Ajustes' }), h('p', { text: 'Segurança e informações do cofre.' })),
    h('div', { class: 'settings-stack ow-in' }, h('h2', { class: 'group-title', text: 'Senha mestra' }), form),
    h('div', { class: 'settings-stack ow-in' },
      h('h2', { class: 'group-title', text: 'Organização' }),
      h('div', { class: 'group' },
        h('button', { class: 'btn group-row cat-row', id: 'settings-categories', type: 'button', onClick: () => setView('categories') },
          h('span', { class: 'cat-tile mint', 'aria-hidden': 'true' }, icon('tag', 18)),
          h('span', { class: 'row-k grow', text: 'Categorias' }),
          h('span', { class: 'cat-row-count', text: String(catCount) }),
          h('span', { class: 'chev', 'aria-hidden': 'true' }, icon('chevron', 16, 2.4))),
        h('button', { class: 'btn group-row cat-row', id: 'settings-library', type: 'button', onClick: () => setView('library') },
          h('span', { class: 'cat-tile blue', 'aria-hidden': 'true' }, icon('link', 18)),
          h('span', { class: 'row-k grow', text: 'Biblioteca de links' }),
          h('span', { class: 'cat-row-count', text: String(state.services.length) }),
          h('span', { class: 'chev', 'aria-hidden': 'true' }, icon('chevron', 16, 2.4))))),
    ui.protection,
    ui.backupsBox,
    ui.desktopBox,
    h('div', { class: 'settings-stack ow-in' },
      h('h2', { class: 'group-title', text: 'Chave Secreta e Kit de emergência' }),
      h('div', { class: 'group' },
        h('div', { class: 'group-row', id: 'key-storage-row' },
          h('span', { class: 'row-k', text: 'Guardada em' }),
          h('span', { class: 'row-v', id: 'key-storage', text: state.status?.key_storage || 'Não disponível' })),
        h('button', { class: 'btn group-row cat-row', id: 'open-kit', type: 'button', onClick: openKitSheet },
          h('span', { class: 'cat-tile mint', 'aria-hidden': 'true' }, icon('shieldKey', 18)),
          h('span', { class: 'row-k grow', text: 'Ver Kit de emergência' }),
          h('span', { class: 'chev', 'aria-hidden': 'true' }, icon('chevron', 16, 2.4)))),
      h('p', { class: 'hint', text: 'A Chave Secreta fica neste computador e protege o arquivo do cofre se ele sair daqui. Para abrir o cofre em outro computador você precisa dela e da senha mestra.' })),
    h('div', { class: 'settings-stack ow-in' },
      h('h2', { class: 'group-title', text: 'Cofre' }),
      h('div', { class: 'group' },
        h('div', { class: 'group-row stacked' },
          h('span', { class: 'row-k', text: 'Arquivo do cofre' }),
          h('span', { class: 'row-v path', id: 'vault-path', text: state.status?.vault_path || '' })))),
    state.status?.app_version ? h('p', { class: 'app-version', id: 'app-version', text: `OwLock v${state.status.app_version}` }) : null);
  current.input.focus();
  loadBackups();
  loadDesktop();
}

/* ======================================================================
   Backups (Ajustes > Backups)
   ====================================================================== */

const LONG_DATE = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });

function longDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso || '') : LONG_DATE.format(date);
}

async function loadBackups() {
  const box = ui.backupsBox;
  if (!box) return;
  const r = await call('list_backups');
  if (!r.ok || box !== ui.backupsBox || !box.isConnected) return;
  const items = r.backups || r.items || [];
  const rows = items.map((backup, index) => h('div', { class: 'group-row backup-row', 'data-id': backup.id },
    h('span', { class: 'backup-text' },
      h('span', { class: 'backup-date', text: longDate(backup.created_at) }),
      h('span', { class: 'backup-meta', text: `${backup.entries ?? 0} ${plural(backup.entries ?? 0, 'conta', 'contas')}` })),
    h('button', { class: 'btn btn-chip', id: `restore-${index}`, type: 'button', 'aria-label': `Restaurar o backup de ${longDate(backup.created_at)}`, onClick: () => openRestoreSheet(backup) }, 'Restaurar')));
  box.replaceChildren(
    h('h2', { class: 'group-title', text: 'Backups' }),
    items.length
      ? h('div', { class: 'group', id: 'backups-list' }, rows)
      : h('p', { class: 'hint', id: 'backups-empty', text: 'Ainda não há backups. Eles são criados sozinhos enquanto você usa o cofre.' }),
    h('p', { class: 'hint', text: 'O OwLock guarda os 20 backups mais recentes, todos protegidos com a sua senha mestra atual.' }));
}

function openRestoreSheet(backup) {
  const pw = passwordField({ id: 'restore-password', label: 'Senha mestra', autofocus: true });
  const error = h('p', { class: 'msg error', id: 'restore-error', role: 'alert' });
  const submit = h('button', { class: 'btn btn-primary', id: 'restore-submit', type: 'submit' }, 'Restaurar');
  const form = h('form', { novalidate: '' },
    h('p', { class: 'lead' }, 'Restaurar o backup de ', h('strong', { text: longDate(backup.created_at) }), '. As contas voltam ao estado daquele momento.'),
    h('p', { class: 'notice', id: 'restore-notice', text: 'O estado atual também vira um backup antes da restauração.' }),
    pw.el, error,
    h('div', { class: 'modal-actions' },
      h('button', { class: 'btn btn-ghost', id: 'restore-cancel', type: 'button', onClick: closeModal }, 'Cancelar'),
      submit));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    error.textContent = '';
    if (!pw.input.value) {
      error.textContent = 'Digite a senha mestra para restaurar.';
      pw.input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Restaurando...';
    const typed = pw.input.value;
    const r = await call('restore_backup', backup.id, typed);
    pw.input.value = '';
    if (!r.ok) {
      submit.disabled = false;
      submit.textContent = 'Restaurar';
      if (r.error === 'locked') return;
      error.textContent = r.error === 'wrong_password' ? apiMessage(r, 'Senha mestra incorreta.') : apiMessage(r, 'Não foi possível restaurar o backup.');
      pw.input.focus();
      return;
    }
    closeModal();
    state.selected = null;
    state.query = '';
    state.categoryFilter = '';
    await Promise.all([loadCategories(), loadServices(), loadSettings()]);
    await loadEntries();
    if (state.entries.length) state.selected = state.entries[0];
    renderList();
    renderDetail();
    loadBackups();
    toast('Backup restaurado');
  });
  const card = h('div', { class: 'modal narrow', 'aria-labelledby': 'restore-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'restore-title', text: 'Restaurar backup' }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    form);
  openModal(card);
}

/* ======================================================================
   Área de trabalho (Windows): bandeja, bloqueio e atalho
   ====================================================================== */

// Só para desenvolvimento: com ?desktop=windows na URL a seção aparece mesmo no servidor de teste,
// para poder vê-la e fotografá-la. No aplicativo real a Api informa a plataforma e esta chave não existe.
const DEV_DESKTOP = new URLSearchParams(location.search).get('desktop') === 'windows';

const DESKTOP_DEFAULTS = {
  close_to_tray: true, lock_on_minimize: false, lock_on_session_lock: true, quick_search_hotkey: true, start_with_windows: false,
};

const DESKTOP_ROWS = [
  { key: 'close_to_tray', id: 'desk-tray', label: 'Manter na bandeja ao fechar' },
  { key: 'lock_on_minimize', id: 'desk-minimize', label: 'Bloquear ao minimizar' },
  { key: 'lock_on_session_lock', id: 'desk-session', label: 'Bloquear ao travar o Windows' },
  { key: 'quick_search_hotkey', id: 'desk-hotkey', label: 'Atalho Ctrl+Shift+Espaço para busca rápida' },
  { key: 'start_with_windows', id: 'desk-autostart', label: 'Iniciar com o Windows' },
];

async function loadDesktop() {
  const box = ui.desktopBox;
  if (!box) return;
  const r = await call('get_desktop_config');
  if (box !== ui.desktopBox || !box.isConnected) return;
  const real = r.ok && r.platform === 'windows';
  if (!real && !DEV_DESKTOP) return;
  const info = r.ok ? r : {};
  let config = { ...DESKTOP_DEFAULTS, ...(info.config || {}) };
  const error = h('p', { class: 'msg error', id: 'desktop-error', role: 'alert' });
  const rows = DESKTOP_ROWS.map((item) => {
    const input = h('input', { class: 'ios-switch', type: 'checkbox', role: 'switch', id: item.id, ...(config[item.key] ? { checked: true } : {}) });
    input.addEventListener('change', async () => {
      error.textContent = '';
      const wanted = input.checked;
      const saved = await call('save_desktop_config', { ...config, [item.key]: wanted });
      if (saved.ok && saved.config) {
        config = { ...DESKTOP_DEFAULTS, ...saved.config };
        input.checked = Boolean(config[item.key]);
        toast('Ajuste salvo');
      } else {
        input.checked = !wanted;
        if (saved.error !== 'locked') error.textContent = apiMessage(saved, 'Não foi possível salvar o ajuste.');
      }
    });
    return h('label', { class: 'group-row switch-row', for: item.id }, h('span', { class: 'row-k grow', text: item.label }), input);
  });
  const hotkeyWarn = real && info.hotkey_available === false
    ? h('p', { class: 'notice warn', id: 'desktop-hotkey-warning', text: 'O atalho Ctrl+Shift+Espaço está em uso por outro programa e não pôde ser registrado.' })
    : null;
  box.replaceChildren(...[
    h('h2', { class: 'group-title', text: 'Área de trabalho' }),
    h('div', { class: 'group', id: 'desktop-group' }, rows),
    hotkeyWarn,
    error,
    h('p', { class: 'hint', text: 'Com o OwLock na bandeja, o cofre continua protegido pelo bloqueio automático e abre rápido pelo atalho.' }),
  ].filter(Boolean));
  box.hidden = false;
}

/* ======================================================================
   Proteção automática (tempos escolhidos pelo usuário)
   ====================================================================== */

const PROTECTION = [
  { key: 'auto_lock_minutes', id: 'set-lock', title: 'Bloqueio automático', prompt: 'Bloquear após' },
  { key: 'clipboard_clear_seconds', id: 'set-clip', title: 'Limpar área de transferência', prompt: 'Limpar a área de transferência após' },
];

async function loadSettings() {
  const r = await call('get_settings');
  if (r.ok) state.settings = { settings: r.settings, options: r.options };
}

function optionLabel(key) {
  const config = state.settings;
  if (!config) return '';
  const value = config.settings[key];
  return config.options[key]?.find((option) => option.value === value)?.label || String(value);
}

function renderProtection() {
  if (!ui.protection) return;
  const rows = PROTECTION.map((item) => h('button', {
    class: 'btn group-row cat-row', id: `${item.id}-row`, type: 'button', onClick: () => openSettingPicker(item),
  }, h('span', { class: 'row-k grow', text: item.title }),
  h('span', { class: 'cat-row-count', id: `${item.id}-value`, text: optionLabel(item.key) }),
  h('span', { class: 'chev', 'aria-hidden': 'true' }, icon('chevron', 16, 2.4))));
  const lock = optionLabel('auto_lock_minutes').toLowerCase();
  const clip = optionLabel('clipboard_clear_seconds').toLowerCase();
  ui.protection.replaceChildren(
    h('h2', { class: 'group-title', text: 'Proteção automática' }),
    h('div', { class: 'group' }, rows),
    h('p', { class: 'hint', id: 'protection-hint', text: `O cofre bloqueia sozinho após ${lock} sem uso, e a área de transferência é limpa ${clip} depois de copiar uma senha ou login.` }));
}

/* Seletor estilo iOS: lista agrupada com ✓ na opção atual, em modal (desktop) ou sheet (celular). */
function openSettingPicker(item) {
  const config = state.settings;
  if (!config) return;
  const options = config.options[item.key] || [];
  const current = config.settings[item.key];
  const error = h('p', { class: 'msg error', role: 'alert' });
  const rows = options.map((option) => {
    const selected = option.value === current;
    return h('button', {
      class: 'btn group-row pick-row', type: 'button', role: 'radio', 'aria-checked': selected ? 'true' : 'false',
      'data-value': String(option.value), id: `${item.id}-opt-${option.value}`,
      ...(selected ? { 'data-autofocus': '' } : {}),
      onClick: () => chooseSetting(item, option.value, error),
    }, h('span', { class: 'row-k grow', text: option.label }),
    option.recommended ? h('span', { class: 'badge-rec', text: 'Recomendado' }) : null,
    h('span', { class: 'tick', 'aria-hidden': 'true' }, selected ? icon('check', 18, 2.6) : null));
  });
  const card = h('div', { class: 'modal narrow', 'aria-labelledby': 'picker-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'picker-title', text: item.title }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    h('p', { class: 'hint', text: item.prompt }),
    h('div', { class: 'group', role: 'radiogroup', 'aria-label': item.title }, rows),
    error);
  openModal(card, { dismissOnBackdrop: true });
}

async function chooseSetting(item, value, errorEl) {
  const current = state.settings.settings;
  if (current[item.key] === value) {
    closeModal();
    return;
  }
  const r = await call('save_settings', { ...current, [item.key]: value });
  if (!r.ok) {
    if (r.error !== 'locked') errorEl.textContent = apiMessage(r, 'Não foi possível salvar o ajuste.');
    return;
  }
  state.settings.settings = r.settings;
  closeModal();
  renderProtection();
  const fresh = await call('status');
  if (fresh.ok) state.status = fresh;
  const touched = await call('touch');
  if (touched.ok && typeof touched.seconds_left === 'number') {
    state.deadline = Date.now() + touched.seconds_left * 1000;
    state.lastTouch = Date.now();
    tick();
  }
  toast('Ajuste salvo');
}

/* ======================================================================
   Biblioteca de links (Ajustes > Biblioteca de links)
   ====================================================================== */

function buildLibraryView() {
  ui.libServices = state.services;
  ui.libSeq = 0;
  const search = h('input', {
    id: 'library-search', type: 'text', placeholder: 'Buscar serviço', 'aria-label': 'Buscar serviço', autocomplete: 'off', spellcheck: 'false',
  });
  const clear = h('button', { class: 'btn search-clear', id: 'library-search-clear', type: 'button', hidden: true, 'aria-label': 'Limpar busca' }, icon('close', 11, 3));
  const run = debounce(async () => {
    const seq = ++ui.libSeq;
    const r = await call('list_services', search.value.trim());
    if (seq !== ui.libSeq || !ui.libList) return;
    if (r.ok) {
      ui.libServices = r.services || [];
      renderLibrary();
    }
  }, 150);
  search.addEventListener('input', () => {
    clear.hidden = search.value === '';
    run();
  });
  clear.addEventListener('click', () => {
    search.value = '';
    clear.hidden = true;
    run();
    search.focus();
  });
  ui.libSearch = search;
  ui.libList = h('div', { class: 'settings-stack', id: 'library-list' });
  ui.paneLib.replaceChildren(
    h('button', { class: 'btn crumb', id: 'library-back', type: 'button', onClick: () => setView('settings') }, icon('chevronLeft', 18, 2.4), 'Ajustes'),
    h('div', { class: 'page-title' },
      h('h1', { text: 'Biblioteca de links' }),
      h('p', { text: 'Links de login que o app preenche ao digitar o nome do serviço.' })),
    h('div', { class: 'lib-bar' },
      h('label', { class: 'search' }, icon('search', 16), search, clear),
      h('button', { class: 'btn btn-primary', id: 'library-add', type: 'button', onClick: () => openServiceEditor(null) }, icon('plus', 16, 2.4), 'Adicionar serviço')),
    ui.libList);
  renderLibrary();
}

function renderLibrary() {
  if (!ui.libList) return;
  const list = ui.libServices || [];
  if (!list.length) {
    ui.libList.replaceChildren(h('p', { class: 'hint', id: 'library-empty', text: 'Nenhum serviço encontrado.' }));
    return;
  }
  const rows = list.map((service) => {
    const badge = !service.builtin
      ? h('span', { class: 'badge-pill mint', text: 'Personalizado' })
      : service.customized ? h('span', { class: 'badge-pill amber', text: 'Alterado' }) : null;
    return h('button', {
      class: 'btn group-row cat-row lib-row', type: 'button', 'data-key': service.key, 'data-name': service.name,
      onClick: () => openServiceEditor(service),
    }, serviceTile(service, 36),
    h('span', { class: 'lib-text' },
      h('span', { class: 'lib-name', text: service.name }),
      h('span', { class: 'lib-domain', text: libraryDomain(service.login_url) })),
    badge,
    h('span', { class: 'chev', 'aria-hidden': 'true' }, icon('chevron', 16, 2.4)));
  });
  ui.libList.replaceChildren(h('div', { class: 'group', id: 'library-group' }, rows));
}

/* Atualiza a biblioteca em memória, a tela e as contas (ícones e links dependem dela). */
async function afterServiceChange() {
  await loadServices();
  if (state.view === 'library' && ui.libList) {
    const r = await call('list_services', ui.libSearch ? ui.libSearch.value.trim() : '');
    if (r.ok) ui.libServices = r.services || [];
    renderLibrary();
  }
  await loadEntries();
  if (state.selected) renderDetail();
}

function splitAliases(text) {
  return text.split(',').map((part) => part.trim()).filter(Boolean);
}

function openServiceEditor(service) {
  const isNew = !service;
  const builtin = Boolean(service && service.builtin);
  const nameInput = h('input', {
    class: 'row-input', id: 'service-name', type: 'text', autocomplete: 'off', placeholder: 'Obrigatório', maxlength: '40',
    value: service ? service.name : '', ...(builtin ? {} : { 'data-autofocus': '' }),
  });
  const aliasInput = h('input', {
    class: 'row-input', id: 'service-aliases', type: 'text', autocomplete: 'off', spellcheck: 'false', placeholder: 'Separados por vírgula',
    value: service ? (service.aliases || []).join(', ') : '',
  });
  const urlInput = h('input', {
    class: 'row-input', id: 'service-url', type: 'text', autocomplete: 'off', spellcheck: 'false', inputmode: 'url', placeholder: 'exemplo.com/login',
    value: service ? service.login_url || '' : '', ...(builtin ? { 'data-autofocus': '' } : {}),
  });
  const nameError = h('p', { class: 'msg error', id: 'service-name-error', role: 'alert' });
  const urlError = h('p', { class: 'msg error', id: 'service-url-error', role: 'alert' });
  const error = h('p', { class: 'msg error', id: 'service-error', role: 'alert' });

  let iconSlug = service && !builtin ? service.icon || '' : '';
  let iconMode = iconSlug ? 'pick' : 'letter';
  const preview = h('span', { class: 'icon-preview', id: 'service-icon-preview' });
  const paintPreview = () => {
    const letter = (nameInput.value.trim()[0] || '?').toUpperCase();
    const brand = iconMode === 'pick' ? state.brandIcons.find((item) => item.slug === iconSlug) : null;
    preview.replaceChildren(brand ? iconTile({ url: brand.icon_url, color: brand.color, letter, size: 32 }) : iconTile({ letter, size: 32 }));
  };
  const iconSeg = segmentedControl({
    id: 'service-icon', label: 'Ícone',
    options: [{ value: 'letter', label: 'Letra' }, { value: 'pick', label: 'Escolher' }],
    value: iconMode,
    onChange: (mode) => {
      if (mode !== 'pick') {
        iconMode = 'letter';
        iconSlug = '';
        paintPreview();
        return;
      }
      openIconPicker({
        current: iconSlug,
        onPick: (slug) => {
          iconSlug = slug;
          iconMode = 'pick';
          iconSeg.set('pick');
          paintPreview();
        },
        onCancel: () => iconSeg.set(iconMode),
      });
    },
  });
  nameInput.addEventListener('input', paintPreview);
  paintPreview();

  const submit = h('button', { class: 'btn btn-primary', id: 'service-submit', type: 'submit' }, 'Salvar');
  const actions = [];
  if (builtin) {
    actions.push(h('button', {
      class: 'btn btn-ghost push-left', id: 'service-reset', type: 'button', ...(service.customized ? {} : { disabled: true }),
      onClick: async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        const r = await call('reset_service', service.key);
        if (!r.ok) {
          if (r.error !== 'locked') {
            button.disabled = false;
            error.textContent = apiMessage(r, 'Não foi possível restaurar o link.');
          }
          return;
        }
        closeModal();
        await afterServiceChange();
        toast('Link restaurado');
      },
    }, 'Restaurar link padrão'));
  } else if (!isNew) {
    actions.push(h('button', { class: 'btn btn-ghost danger push-left', id: 'service-delete', type: 'button', onClick: () => confirmDeleteService(service) }, 'Excluir serviço'));
  }
  actions.push(h('button', { class: 'btn btn-ghost', id: 'service-cancel', type: 'button', onClick: closeModal }, 'Cancelar'), submit);

  const nameRow = h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'service-name', text: 'Nome *' }), nameInput);
  const urlRow = h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'service-url', text: 'Link' }), urlInput);
  const fields = builtin
    ? [h('div', { class: 'group' }, urlRow)]
    : [h('div', { class: 'group' }, nameRow), nameError,
      h('div', { class: 'group' },
        h('div', { class: 'group-row' }, h('label', { class: 'row-k', for: 'service-aliases', text: 'Apelidos' }), aliasInput),
        urlRow)];

  const form = h('form', { novalidate: '' },
    builtin ? h('div', { class: 'service-head' },
      serviceTile(service, 44),
      h('div', { class: 'service-head-text' },
        h('strong', { text: service.name }),
        h('span', { text: `Link padrão: ${libraryDomain(service.default_url || service.login_url)}` }))) : null,
    ...fields,
    urlError,
    builtin ? null : h('div', { class: 'group' },
      h('div', { class: 'group-row stacked' },
        h('div', { class: 'icon-head' }, h('span', { class: 'row-k', text: 'Ícone' }), preview),
        iconSeg.el)),
    error,
    h('div', { class: 'modal-actions' }, actions));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    error.textContent = '';
    nameError.textContent = '';
    urlError.textContent = '';
    nameRow.classList.remove('invalid');
    urlRow.classList.remove('invalid');
    const data = {
      name: builtin ? service.name : nameInput.value.trim(),
      aliases: builtin ? service.aliases || [] : splitAliases(aliasInput.value),
      login_url: urlInput.value.trim(),
      icon: builtin ? service.icon || '' : iconSlug,
    };
    if (service) data.key = service.key;
    if (!builtin && !data.name) {
      nameRow.classList.add('invalid');
      nameError.textContent = 'Informe o nome do serviço.';
      nameInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = 'Salvando...';
    const r = await call('save_service', data);
    if (!r.ok) {
      if (r.error === 'locked') return;
      submit.disabled = false;
      submit.textContent = 'Salvar';
      const message = apiMessage(r, 'Não foi possível salvar o serviço.');
      if (['name_required', 'name_too_long', 'name_exists'].includes(r.error)) {
        nameRow.classList.add('invalid');
        nameError.textContent = message;
        nameInput.focus();
      } else if (r.error === 'invalid_url') {
        urlRow.classList.add('invalid');
        urlError.textContent = message;
        urlInput.focus();
      } else {
        error.textContent = message;
      }
      return;
    }
    closeModal();
    await afterServiceChange();
    toast(isNew ? 'Serviço adicionado' : 'Serviço salvo');
  });

  const title = isNew ? 'Adicionar serviço' : builtin ? 'Editar link' : 'Editar serviço';
  const card = h('div', { class: 'modal', 'aria-labelledby': 'service-title' },
    h('div', { class: 'modal-head' },
      h('h2', { id: 'service-title', text: title }),
      h('button', { class: 'btn btn-icon', type: 'button', 'aria-label': 'Fechar', onClick: closeModal }, icon('close', 18))),
    form);
  openModal(card);
}

function confirmDeleteService(service) {
  const error = h('p', { class: 'msg error', role: 'alert' });
  const confirmButton = h('button', { class: 'btn btn-primary danger', id: 'confirm-delete-service', type: 'button', 'data-autofocus': '' }, 'Excluir');
  confirmButton.addEventListener('click', async () => {
    confirmButton.disabled = true;
    const r = await call('delete_service', service.key);
    if (!r.ok) {
      if (r.error === 'locked') return;
      confirmButton.disabled = false;
      error.textContent = apiMessage(r, 'Não foi possível excluir o serviço.');
      return;
    }
    closeModal();
    await afterServiceChange();
    toast('Serviço excluído');
  });
  const card = h('div', { class: 'modal narrow', 'aria-labelledby': 'delete-service-title' },
    h('h2', { id: 'delete-service-title', text: 'Excluir serviço?' }),
    h('p', { class: 'lead' }, 'Você vai excluir ', h('strong', { text: service.name }), '. As contas já salvas continuam no cofre, mas deixam de usar o link e o ícone dele.'),
    error,
    h('div', { class: 'modal-actions' },
      h('button', { class: 'btn btn-ghost', id: 'cancel-delete-service', type: 'button', onClick: closeModal }, 'Cancelar'),
      confirmButton));
  openModal(card, { dismissOnBackdrop: true });
}

/* ======================================================================
   Busca rápida (rota #quick): janela compacta 560x420, sem barra lateral
   ====================================================================== */

const QUICK_LIMIT = 8;
const QUICK_HIDE_DELAY_MS = 600;
const quick = { search: null, list: null, entries: [], active: 0, seq: 0, built: false };

function quickHide() {
  return call('quick_hide');
}

async function bootQuick() {
  quickMode = true;
  document.body.classList.add('quick');
  document.addEventListener('keydown', onQuickKey);
  const reopen = () => refreshQuick();
  window.addEventListener('focus', reopen);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) reopen();
  });
  await refreshQuick();
}

/* Reabrir: confere o estado, limpa a busca e foca o campo de novo. */
async function refreshQuick() {
  const status = await call('status');
  if (!status.ok || !status.unlocked) {
    showQuickLocked();
    return;
  }
  if (!quick.built || !quick.search?.isConnected) buildQuick();
  quick.search.value = '';
  await runQuickSearch();
  quick.search.focus();
}

function showQuickLocked() {
  quick.built = false;
  quick.entries = [];
  quick.search = null;
  quick.list = null;
  const open = h('button', { class: 'btn btn-primary', id: 'quick-open-main', type: 'button', 'data-autofocus': '' }, 'Abrir OwLock');
  open.addEventListener('click', async () => {
    await call('quick_open_main');
    await quickHide();
  });
  root.replaceChildren(h('div', { class: 'quick-locked', id: 'quick-locked' },
    h('div', { class: 'kit-badge', 'aria-hidden': 'true' }, icon('lock', 32, 1.8)),
    h('h1', { text: 'O cofre está bloqueado' }),
    h('p', { text: 'Abra o OwLock e digite a senha mestra para buscar suas contas.' }),
    open));
  open.focus();
}

function buildQuick() {
  quick.search = h('input', {
    id: 'quick-search', type: 'text', placeholder: 'Buscar conta', autocomplete: 'off', spellcheck: 'false',
    role: 'combobox', 'aria-label': 'Buscar conta', 'aria-controls': 'quick-list', 'aria-expanded': 'true', 'aria-autocomplete': 'list',
  });
  quick.search.addEventListener('input', debounce(runQuickSearch, 100));
  quick.list = h('div', { class: 'quick-list', id: 'quick-list', role: 'listbox', 'aria-label': 'Resultados' });
  root.replaceChildren(h('div', { class: 'quick-wrap' },
    h('label', { class: 'quick-field' }, icon('search', 20), quick.search),
    quick.list,
    h('p', { class: 'quick-foot', text: '↑ ↓ navegar · Enter copia a senha · Ctrl+Enter copia o login · Esc fecha' })));
  quick.built = true;
}

async function runQuickSearch() {
  if (!quick.search) return;
  const seq = ++quick.seq;
  const r = await call('list_entries', quick.search.value.trim(), 'all', '');
  if (seq !== quick.seq || !quick.list) return;
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r), 'warn');
    return;
  }
  quick.entries = (r.entries || []).slice(0, QUICK_LIMIT);
  quick.active = 0;
  paintQuick();
}

function paintQuick() {
  if (!quick.list) return;
  if (!quick.entries.length) {
    quick.list.replaceChildren(h('p', { class: 'quick-empty', id: 'quick-empty', text: 'Nenhuma conta encontrada.' }));
    quick.search.removeAttribute('aria-activedescendant');
    return;
  }
  const rows = quick.entries.map((entry, index) => {
    const canOpen = Boolean(entry.url || entry.service_key);
    const act = (id, label, iconName, handler) => h('button', {
      class: 'btn quick-act', id: `${id}-${index}`, type: 'button', title: label, 'aria-label': `${label}: ${entry.service}`, tabindex: '-1',
      onClick: (event) => {
        event.stopPropagation();
        handler(entry);
      },
    }, icon(iconName, 16, 2));
    return h('div', {
      class: 'quick-row' + (index === quick.active ? ' is-active' : ''), id: `quick-opt-${index}`, role: 'option',
      'aria-selected': index === quick.active ? 'true' : 'false', 'data-id': entry.id,
      onMousemove: () => {
        if (quick.active !== index) {
          quick.active = index;
          markQuickActive();
        }
      },
    },
    monoBadge(entry, 32),
    h('span', { class: 'quick-text' },
      h('span', { class: 'quick-name', text: entry.service }),
      h('span', { class: 'quick-user', text: entry.username || '' })),
    entry.favorite ? h('span', { class: 'quick-fav', 'aria-label': 'Favorita', role: 'img' }, icon('star', 14, 2)) : null,
    h('span', { class: 'quick-actions' },
      act('quick-login', 'Copiar login', 'user', quickCopyLogin),
      act('quick-pass', 'Copiar senha', 'lock', quickCopyPassword),
      canOpen ? act('quick-site', 'Abrir site', 'external', quickOpenSite) : null));
  });
  quick.list.replaceChildren(...rows);
  markQuickActive();
}

function markQuickActive() {
  [...quick.list.querySelectorAll('.quick-row')].forEach((row, index) => {
    const on = index === quick.active;
    row.classList.toggle('is-active', on);
    row.setAttribute('aria-selected', on ? 'true' : 'false');
    if (on) row.scrollIntoView({ block: 'nearest' });
  });
  quick.search.setAttribute('aria-activedescendant', `quick-opt-${quick.active}`);
}

async function quickCopyLogin(entry) {
  const r = await call('copy_field', entry.id, 'username');
  if (r.ok) toast('Login copiado');
  else if (r.error !== 'locked') toast(apiMessage(r, 'Não foi possível copiar.'), 'warn');
}

async function quickCopyPassword(entry) {
  const r = await call('copy_field', entry.id, 'password');
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r, 'Não foi possível copiar.'), 'warn');
    return;
  }
  toast('Senha copiada');
  setTimeout(quickHide, QUICK_HIDE_DELAY_MS);
}

async function quickOpenSite(entry) {
  const r = await call('open_url', entry.id);
  if (!r.ok) {
    if (r.error !== 'locked') toast(apiMessage(r, 'Não foi possível abrir o site.'), 'warn');
    return;
  }
  toast('Abrindo o site...');
  setTimeout(quickHide, QUICK_HIDE_DELAY_MS);
}

function onQuickKey(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    quickHide();
    return;
  }
  if (!quick.list || !quick.entries.length) return;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    const step = event.key === 'ArrowDown' ? 1 : -1;
    quick.active = (quick.active + step + quick.entries.length) % quick.entries.length;
    markQuickActive();
  } else if (event.key === 'Enter') {
    event.preventDefault();
    const entry = quick.entries[quick.active];
    if (!entry) return;
    if (event.ctrlKey || event.metaKey) quickCopyLogin(entry);
    else quickCopyPassword(entry);
  }
}

/* ======================================================================
   Início
   ====================================================================== */

if (location.hash === '#quick') bootQuick();
else showEntry();
