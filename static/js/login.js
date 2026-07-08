/* ═══════════════════════════════════════════════════════════════
   PLATFORM LOGIN BROWSER
   ═══════════════════════════════════════════════════════════════ */
import { t } from './i18n.js';
import { showLoading, hideLoading } from './loading.js';

const LOGIN_URLS = {
  linkedin: 'https://www.linkedin.com/login',
  indeed: 'https://secure.indeed.com/auth',
};

let _loginPollTimer = null;
let _pendingPlatform = null;
let _wasConnectedAtOpen = false;

function resolveLoginUrl(urlOrPlatform) {
  const key = (urlOrPlatform || '').toLowerCase();
  return LOGIN_URLS[key] || urlOrPlatform;
}

function resolvePlatformKey(urlOrPlatform) {
  const key = (urlOrPlatform || '').toLowerCase();
  if (LOGIN_URLS[key]) return key;
  const url = (urlOrPlatform || '').toLowerCase();
  if (url.includes('linkedin')) return 'linkedin';
  if (url.includes('indeed')) return 'indeed';
  return null;
}

function updateSessionBadges(data) {
  const ids = [
    { id: 'linkedin-session-status', connected: data.linkedin },
    { id: 'indeed-session-status',   connected: data.indeed },
    { id: 'wiz-linkedin-session',    connected: data.linkedin },
    { id: 'wiz-indeed-session',      connected: data.indeed },
    { id: 'wf-linkedin-session',     connected: data.linkedin },
    { id: 'wf-indeed-session',       connected: data.indeed },
  ];
  for (const { id, connected } of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (connected) {
      el.innerHTML = '<span class="dot dot-green"></span> ' + t('login.connected');
      el.className = 'status-badge ok';
      el.style.fontSize = '.8rem';
    } else {
      el.innerHTML = '<span class="dot dot-gray"></span> ' + t('login.not_connected');
      el.className = 'status-badge';
      el.style.fontSize = '.8rem';
    }
  }
  updateLinkedInImportState(!!data.linkedin);
}

export function updateLinkedInImportState(linkedinConnected) {
  for (const id of ['btn-import-linkedin', 'wizard-btn-import-linkedin']) {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = !linkedinConnected;
  }
  const hint = document.getElementById('linkedin-import-connect-hint');
  if (hint) hint.classList.toggle('hidden', linkedinConnected);
}

export async function loadBrowserInfo() {
  try {
    const res = await fetch('/api/login/browser-info');
    if (!res.ok) return;
    const data = await res.json();
    const el = document.getElementById('settings-browser-info');
    if (el && data.display_name) {
      el.textContent = t('settings.browser_engine', { name: data.display_name });
    }
  } catch { /* non-critical */ }
}

function stopLoginPolling() {
  if (_loginPollTimer) {
    clearInterval(_loginPollTimer);
    _loginPollTimer = null;
  }
}

async function pollLoginFlow() {
  try {
    const statusRes = await fetch('/api/login/status');
    const status = await statusRes.json();
    updateLoginUI(status.open);

    const sessionsRes = await fetch('/api/login/sessions');
    if (sessionsRes.ok) {
      const sessions = await sessionsRes.json();
      updateSessionBadges(sessions);

      const target = _pendingPlatform;
      const connected = target ? sessions[target] : (sessions.linkedin || sessions.indeed);
      // Only auto-close when the user just logged in (was not connected when browser opened).
      if (connected && status.open && !_wasConnectedAtOpen) {
        _pendingPlatform = null;
        await closeLoginBrowser();
        return;
      }
    }

    if (!status.open) {
      stopLoginPolling();
    }
  } catch {
    stopLoginPolling();
    updateLoginUI(false);
  }
}

function startLoginPolling() {
  stopLoginPolling();
  pollLoginFlow();
  _loginPollTimer = setInterval(pollLoginFlow, 2000);
}

async function _sessionStateForPlatform(platformKey) {
  try {
    const res = await fetch('/api/login/sessions');
    if (!res.ok) return false;
    const data = await res.json();
    return platformKey ? !!data[platformKey] : !!(data.linkedin || data.indeed);
  } catch {
    return false;
  }
}

export async function openLoginBrowser(urlOrPlatform) {
  const url = resolveLoginUrl(urlOrPlatform);
  const platformKey = resolvePlatformKey(urlOrPlatform);
  _pendingPlatform = platformKey;
  _wasConnectedAtOpen = await _sessionStateForPlatform(platformKey);

  showLoading(t('loading.opening_browser'));
  try {
    const res = await fetch('/api/login/open', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || t('login.open_error'));
      return;
    }
    updateLoginUI(true);
    startLoginPolling();
  } catch (e) {
    alert(t('login.connection_error'));
  } finally {
    hideLoading();
  }
}

export async function closeLoginBrowser() {
  stopLoginPolling();
  _pendingPlatform = null;
  _wasConnectedAtOpen = false;
  try {
    await fetch('/api/login/close', { method: 'POST' });
  } catch { }
  updateLoginUI(false);
  setTimeout(checkLoginSessions, 500);
}

function updateLoginUI(isOpen) {
  const closeIds = ['wizard-close-browser', 'settings-close-browser', 'wf-close-browser'];
  for (const id of closeIds) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('hidden', !isOpen);
  }
}

export async function checkLoginSessions() {
  try {
    const res = await fetch('/api/login/sessions');
    if (!res.ok) return;
    const data = await res.json();
    updateSessionBadges(data);
  } catch { }
}

/** Wire login buttons via JS (more reliable than inline onclick). */
export function initLoginButtons() {
  const bindings = [
    ['wizard-linkedin-login', 'linkedin'],
    ['wizard-indeed-login', 'indeed'],
    ['settings-linkedin-login', 'linkedin'],
    ['settings-indeed-login', 'indeed'],
  ];
  for (const [id, platform] of bindings) {
    const el = document.getElementById(id);
    if (el && !el.dataset.loginBound) {
      el.dataset.loginBound = '1';
      el.addEventListener('click', (e) => {
        e.preventDefault();
        openLoginBrowser(platform);
      });
    }
  }
  document.querySelectorAll('[data-login-platform]').forEach((el) => {
    if (el.dataset.loginBound) return;
    el.dataset.loginBound = '1';
    el.addEventListener('click', (e) => {
      e.preventDefault();
      openLoginBrowser(el.dataset.loginPlatform);
    });
  });
}
