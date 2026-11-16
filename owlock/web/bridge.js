// Ponte entre a interface e a Api do Python.
// Dentro da janela nativa usa window.pywebview.api; no navegador (devserver) usa HTTP.

const READY_TIMEOUT_MS = 3000;

let modePromise = null;

function detectMode() {
  if (modePromise) return modePromise;
  modePromise = new Promise((resolve) => {
    if (window.pywebview?.api) {
      resolve('native');
      return;
    }
    let timer = null;
    const finish = (mode) => {
      clearTimeout(timer);
      window.removeEventListener('pywebviewready', onReady);
      resolve(mode);
    };
    const onReady = () => finish('native');
    window.addEventListener('pywebviewready', onReady);
    timer = setTimeout(() => finish(window.pywebview?.api ? 'native' : 'http'), READY_TIMEOUT_MS);
  });
  return modePromise;
}

function failure(error, message) {
  return { ok: false, error, message };
}

async function callNative(method, args) {
  const fn = window.pywebview.api[method];
  if (typeof fn !== 'function') return failure('unknown_method', 'Operação indisponível.');
  return fn(...args);
}

async function callHttp(method, args) {
  const response = await fetch('/api/' + encodeURIComponent(method), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ args }),
  });
  return response.json();
}

export async function call(method, ...args) {
  let result;
  try {
    const mode = await detectMode();
    result = mode === 'native' ? await callNative(method, args) : await callHttp(method, args);
  } catch {
    return failure('unavailable', 'Não foi possível falar com o aplicativo.');
  }
  if (!result || typeof result !== 'object') {
    return failure('bad_response', 'Resposta inesperada do aplicativo.');
  }
  if (result.ok === false && result.error === 'locked') {
    window.dispatchEvent(new CustomEvent('owlock:locked'));
  }
  return result;
}
