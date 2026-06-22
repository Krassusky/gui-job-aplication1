/* Desktop shortcut helpers for packaged builds */
import { t } from './i18n.js';

export async function loadShortcutsPanel() {
  const panel = document.getElementById('shortcuts-panel');
  if (!panel) return;

  const devNotice = document.getElementById('shortcuts-dev-notice');
  const statusEl = document.getElementById('shortcuts-status-msg');
  const installBtn = document.getElementById('btn-install-shortcuts');

  try {
    const res = await fetch('/api/shortcuts/status');
    const data = await res.json();
    const available = !!data.available;
    panel.classList.remove('hidden');
    if (devNotice) devNotice.classList.toggle('hidden', available);
    if (installBtn) installBtn.classList.toggle('hidden', !available);
    if (!available) {
      if (statusEl) statusEl.textContent = '';
      return;
    }

    if (statusEl) {
      statusEl.textContent = formatShortcutsStatus(data);
    }
    if (installBtn) {
      installBtn.disabled = false;
      installBtn.textContent = data.desktop_exists
        ? t('shortcuts.recreate')
        : t('shortcuts.create');
    }
  } catch {
    if (statusEl) statusEl.textContent = t('shortcuts.status_error');
  }
}

function formatShortcutsStatus(data) {
  if (data.desktop_exists && (data.start_menu_exists || data.applications_installed)) {
    return t('shortcuts.status_installed');
  }
  if (data.desktop_exists) {
    return t('shortcuts.status_desktop_only');
  }
  return t('shortcuts.status_missing');
}

export async function installDesktopShortcuts() {
  const statusEl = document.getElementById('shortcuts-status-msg');
  const installBtn = document.getElementById('btn-install-shortcuts');
  if (installBtn) {
    installBtn.disabled = true;
    installBtn.textContent = t('shortcuts.installing');
  }
  if (statusEl) statusEl.textContent = t('shortcuts.installing');

  try {
    const res = await fetch('/api/shortcuts/install', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || t('shortcuts.install_failed'));
    }
    if (statusEl) statusEl.textContent = t('shortcuts.install_success');
    if (installBtn) installBtn.textContent = t('shortcuts.recreate');
    hideShortcutsPrompt();
    await loadShortcutsPanel();
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message || t('shortcuts.install_failed');
  } finally {
    if (installBtn) installBtn.disabled = false;
  }
}

export async function declineShortcutsPrompt() {
  try {
    await fetch('/api/shortcuts/decline', { method: 'POST' });
  } catch { /* ignore */ }
  hideShortcutsPrompt();
}

export function hideShortcutsPrompt() {
  const overlay = document.getElementById('shortcuts-overlay');
  if (overlay) overlay.classList.add('hidden');
}

export async function maybeShowShortcutsPrompt() {
  const overlay = document.getElementById('shortcuts-overlay');
  if (!overlay) return;

  try {
    const res = await fetch('/api/shortcuts/status');
    const data = await res.json();
    if (data.available && data.needs_prompt) {
      const title = document.getElementById('shortcuts-title');
      const body = document.getElementById('shortcuts-body');
      if (title) title.textContent = t('shortcuts.prompt_title');
      if (body) {
        body.textContent = data.platform === 'darwin'
          ? t('shortcuts.prompt_body_mac')
          : t('shortcuts.prompt_body_win');
      }
      overlay.classList.remove('hidden');
    }
  } catch { /* ignore */ }
}
