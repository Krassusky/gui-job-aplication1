/* ═══════════════════════════════════════════════════════════════
   LOADING — global overlays, boot screen, button & nav feedback
   ═══════════════════════════════════════════════════════════════ */
import { t } from './i18n.js';

let _overlayCount = 0;
let _navLoadingCount = 0;

function _overlayEls() {
  return {
    overlay: document.getElementById('global-loading-overlay'),
    message: document.getElementById('global-loading-message'),
  };
}

/** Show full-screen blocking overlay (reference-counted for nested calls). */
export function showLoading(message) {
  const { overlay, message: msgEl } = _overlayEls();
  if (!overlay) return;
  _overlayCount++;
  if (msgEl) {
    msgEl.textContent = message || t('loading.please_wait');
  }
  overlay.classList.remove('hidden');
  overlay.setAttribute('aria-busy', 'true');
}

/** Hide full-screen overlay when all nested showLoading calls complete. */
export function hideLoading() {
  const { overlay } = _overlayEls();
  if (!overlay) return;
  _overlayCount = Math.max(0, _overlayCount - 1);
  if (_overlayCount === 0) {
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-busy', 'false');
  }
}

/** Run an async function behind the global overlay. */
export async function withLoading(fn, message) {
  showLoading(message);
  try {
    return await fn();
  } finally {
    hideLoading();
  }
}

/** Hide the initial boot splash once the app is ready. */
export function hideAppBootLoader() {
  const el = document.getElementById('app-boot-loader');
  if (!el) return;
  el.classList.add('hidden');
  el.setAttribute('aria-hidden', 'true');
  el.setAttribute('aria-busy', 'false');
}

/** Thin indeterminate bar under the navbar while a screen loads data. */
export function showNavLoading() {
  const bar = document.getElementById('nav-loading-bar');
  if (!bar) return;
  _navLoadingCount++;
  bar.classList.remove('hidden');
  bar.setAttribute('aria-hidden', 'false');
}

export function hideNavLoading() {
  const bar = document.getElementById('nav-loading-bar');
  if (!bar) return;
  _navLoadingCount = Math.max(0, _navLoadingCount - 1);
  if (_navLoadingCount === 0) {
    bar.classList.add('hidden');
    bar.setAttribute('aria-hidden', 'true');
  }
}

/** Disable a button and show an inline spinner. */
export function setButtonLoading(btn, loading) {
  if (!btn) return;
  if (loading) {
    if (!btn.dataset.loadingBound) {
      btn.dataset.loadingBound = '1';
      if (!btn.dataset.originalHtml) {
        btn.dataset.originalHtml = btn.innerHTML;
      }
    }
    btn.disabled = true;
    btn.classList.add('btn-loading');
    btn.setAttribute('aria-busy', 'true');
  } else {
    btn.disabled = false;
    btn.classList.remove('btn-loading');
    btn.removeAttribute('aria-busy');
    if (btn.dataset.originalHtml) {
      btn.innerHTML = btn.dataset.originalHtml;
    }
  }
}

/** Disable a group of buttons during an async action. */
export function setButtonsDisabled(buttons, disabled) {
  for (const btn of buttons) {
    if (btn) btn.disabled = disabled;
  }
}
