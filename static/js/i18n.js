/* ═══════════════════════════════════════════════════════════════
   I18N — Internationalization support (LE-3)
   ═══════════════════════════════════════════════════════════════

   Loads translation strings from JSON locale files.
   Default locale is 'pt' (pt-BR content). Override via localStorage, ?lang=, or <html lang="xx">.

   Usage:
     import { t, setLocale, getLocale } from './i18n.js';
     t('wizard.welcome_title')          // => "Welcome to AutoApply"
     t('errors.invalid_status', { valid_statuses: 'a, b' })  // => interpolation
*/

let _strings = {};
let _locale = 'pt';
let _ready = false;
const _readyCallbacks = [];

/**
 * Get a translated string by dot-notation key.
 * Falls back to the key itself if not found.
 * Supports {placeholder} interpolation.
 */
export function t(key, params) {
  const parts = key.split('.');
  let val = _strings;
  for (const p of parts) {
    if (val && typeof val === 'object' && p in val) {
      val = val[p];
    } else {
      return key; // fallback: return key as-is
    }
  }
  if (typeof val !== 'string') return key;
  if (!params) return val;
  return val.replace(/\{(\w+)\}/g, (_, k) => (k in params ? params[k] : `{${k}}`));
}

/** Return current locale code. */
export function getLocale() {
  return _locale;
}

/** Load a locale and switch to it. Returns a promise. */
function _mergeLocales(base, overlay) {
  const out = { ...base };
  for (const [k, v] of Object.entries(overlay)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object') {
      out[k] = { ...base[k], ...v };
    } else {
      out[k] = v;
    }
  }
  return out;
}

export async function setLocale(locale) {
  try {
    const enRes = await fetch('/static/locales/en.json');
    const enStrings = enRes.ok ? await enRes.json() : {};
    if (locale === 'en') {
      _strings = enStrings;
    } else {
      const res = await fetch(`/static/locales/${locale}.json`);
      if (!res.ok) throw new Error(`Locale ${locale} not found (${res.status})`);
      const localeStrings = await res.json();
      _strings = _mergeLocales(enStrings, localeStrings);
    }
    _locale = locale;
    _ready = true;
    document.documentElement.lang = locale;
    // Persist to localStorage (FR-132)
    try { localStorage.setItem('autoapply_locale', locale); } catch { /* private browsing */ }
    // Sync backend locale (FR-133)
    fetch('/api/locale', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ locale }),
    }).catch(() => { /* best-effort sync */ });
    _applyDataI18n();
    _readyCallbacks.forEach(fn => fn());
    _readyCallbacks.length = 0;
  } catch (e) {
    console.warn(`[i18n] Failed to load locale "${locale}":`, e);
    if (locale !== 'en') {
      console.warn('[i18n] Falling back to "en"');
      await setLocale('en');
    }
  }
}

/** Register a callback that fires once translations are loaded. */
export function onReady(fn) {
  if (_ready) { fn(); return; }
  _readyCallbacks.push(fn);
}

/** Detect locale from localStorage, query param ?lang=, <html lang>, or default 'pt'. */
function detectLocale() {
  // localStorage takes priority (FR-132)
  try {
    const stored = localStorage.getItem('autoapply_locale');
    if (stored) return stored;
  } catch { /* private browsing */ }
  const params = new URLSearchParams(window.location.search);
  const qLang = params.get('lang');
  if (qLang) return qLang;
  const htmlLang = document.documentElement.lang;
  if (htmlLang) return htmlLang.split('-')[0];
  return 'pt';
}

/**
 * Apply translations to all elements with data-i18n attributes.
 * Supports: data-i18n="key" (textContent), data-i18n-placeholder="key",
 * data-i18n-aria-label="key", data-i18n-title="key".
 */
export function _applyDataI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });
  document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria-label')));
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.getAttribute('data-i18n-title'));
  });
}

// Auto-initialize on import
const _initLocale = detectLocale();
setLocale(_initLocale);
