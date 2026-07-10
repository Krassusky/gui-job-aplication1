/* In-app updates (GitHub Releases) */
import { t } from './i18n.js';

const UPDATE_CHECK_KEY = 'jobapply_last_update_check';
const UPDATE_DISMISS_KEY = 'jobapply_update_dismissed_version';

let _pollTimer = null;
let _pendingUpdate = null;
let _updateRunning = false;
let _autoInstallWhenReady = false;

export async function loadUpdatePanel() {
  const verEl = document.getElementById('update-current-version');
  if (!verEl) return;
  try {
    const res = await fetch('/api/updates/info');
    const data = await res.json();
    verEl.textContent = data.current_version || '—';
    toggleDevNotice(!data.can_install);
    if (_pendingUpdate) {
      syncUpdateUI(_pendingUpdate);
    } else {
      resetUpdateUI();
    }
  } catch {
    verEl.textContent = '—';
  }
}

/** Check once per day on startup and show a banner if an update exists. */
export async function maybeAutoCheckUpdates() {
  try {
    const info = await fetch('/api/updates/info').then(r => r.json());
    if (!info.can_install) return;

    const dismissed = localStorage.getItem(UPDATE_DISMISS_KEY);
    const lastCheck = localStorage.getItem(UPDATE_CHECK_KEY);
    const dayMs = 24 * 60 * 60 * 1000;
    if (lastCheck && Date.now() - parseInt(lastCheck, 10) < dayMs) return;

    localStorage.setItem(UPDATE_CHECK_KEY, String(Date.now()));
    const data = await _fetchUpdateCheck();
    if (!data?.update_available) return;
    if (dismissed === data.latest_version) return;

    _pendingUpdate = data;
    showUpdateBanner(data);
    syncUpdateUI(data);
  } catch {
    /* offline or GitHub unavailable — ignore */
  }
}

/** One-click update: download (if needed) then install and restart. */
export async function runUpdateNow() {
  if (_updateRunning) return;

  let data = _pendingUpdate;
  if (!data) {
    data = await _fetchUpdateCheck();
    if (!data?.update_available) {
      setUpdateMessage(t('updates.up_to_date'), 'success');
      return;
    }
    _pendingUpdate = data;
  }

  if (!data.can_install) {
    setUpdateMessage(t('updates.dev_mode'), 'info');
    return;
  }

  _updateRunning = true;
  _autoInstallWhenReady = true;
  setBannerText(t('updates.preparing'));
  setBannerButtons(false);

  try {
    if (data.ready) {
      await installUpdate(true);
      return;
    }
    setBannerText(t('updates.downloading'));
    showBannerProgress(0);
    setUpdateMessage(t('updates.downloading'), 'info');
    syncUpdateUI({ ...data, update_available: true, ready: false });

    const res = await fetch('/api/updates/download', { method: 'POST' });
    const body = await res.json();
    if (!res.ok) {
      throw new Error(body.error || t('updates.download_failed'));
    }
    if (body.status === 'ready') {
      await installUpdate(true);
      return;
    }
    startUpdatePolling(true);
  } catch (e) {
    _updateRunning = false;
    _autoInstallWhenReady = false;
    const msg = e.message || t('updates.download_failed');
    setUpdateMessage(msg, 'error');
    setBannerText(msg);
    setBannerButtons(true);
    hideBannerProgress();
  }
}

export function dismissUpdateBanner() {
  if (_pendingUpdate?.latest_version) {
    try {
      localStorage.setItem(UPDATE_DISMISS_KEY, _pendingUpdate.latest_version);
    } catch { /* ignore */ }
  }
  document.getElementById('update-banner')?.classList.add('hidden');
}

export async function checkForUpdates() {
  setUpdateMessage(t('updates.checking'), 'info');
  setUpdateButtons({ check: true, download: false, install: false, oneClick: false });
  try {
    const data = await _fetchUpdateCheck();
    if (!data) {
      setUpdateMessage(t('updates.check_failed'), 'error');
      return;
    }
    if (data.update_available) {
      _pendingUpdate = data;
      showUpdateBanner(data);
    } else {
      hideUpdateBanner();
      _pendingUpdate = null;
    }
    syncUpdateUI(data);
  } catch {
    setUpdateMessage(t('updates.check_failed'), 'error');
  }
}

export async function downloadUpdate() {
  _autoInstallWhenReady = false;
  setUpdateMessage(t('updates.downloading'), 'info');
  showProgress(0);
  setUpdateButtons({ check: false, download: false, install: false, oneClick: false });
  try {
    const res = await fetch('/api/updates/download', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      setUpdateMessage(data.error || t('updates.download_failed'), 'error');
      hideProgress();
      syncUpdateUI(_pendingUpdate || data);
      return;
    }
    startUpdatePolling(false);
  } catch {
    setUpdateMessage(t('updates.download_failed'), 'error');
    hideProgress();
    setUpdateButtons({ check: true, download: true, install: false, oneClick: true });
  }
}

export async function installUpdate(skipConfirm = false) {
  if (!skipConfirm && !confirm(t('updates.install_confirm'))) return;
  setUpdateMessage(t('updates.installing'), 'info');
  setBannerText(t('updates.installing'));
  setUpdateButtons({ check: false, download: false, install: false, oneClick: false });
  setBannerButtons(false);
  try {
    const res = await fetch('/api/updates/install', { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || t('updates.install_failed'));
    }
    hideUpdateBanner();
    setUpdateMessage(t('updates.installing'), 'info');
    setBannerText(t('updates.installing'));
    // Backend also schedules quit; call shutdown so the helper can replace the .app.
    setTimeout(() => {
      fetch('/api/shutdown', { method: 'POST' }).catch(() => {});
    }, 500);
  } catch (e) {
    _updateRunning = false;
    _autoInstallWhenReady = false;
    const msg = e.message || t('updates.install_failed');
    setUpdateMessage(msg, 'error');
    setBannerText(msg);
    setBannerButtons(true);
    syncUpdateUI(_pendingUpdate || {});
  }
}

async function _fetchUpdateCheck() {
  const res = await fetch('/api/updates/check', { method: 'POST' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'check failed');
  return data;
}

function startUpdatePolling(autoInstall) {
  _autoInstallWhenReady = autoInstall;
  stopUpdatePolling();
  _pollTimer = setInterval(pollUpdateStatus, 900);
  pollUpdateStatus();
}

function stopUpdatePolling() {
  if (_pollTimer) {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }
}

async function pollUpdateStatus() {
  try {
    const res = await fetch('/api/updates/status');
    const data = await res.json();
    if (data.status === 'downloading') {
      showProgress(data.progress || 0);
      showBannerProgress(data.progress || 0);
      setUpdateMessage(t('updates.downloading'), 'info');
      setBannerText(t('updates.downloading'));
      return;
    }
    if (data.status === 'ready') {
      stopUpdatePolling();
      hideProgress();
      hideBannerProgress();
      const merged = {
        current_version: data.current_version,
        latest_version: data.latest_version,
        update_available: true,
        release_notes: data.release_notes,
        ready: true,
        can_install: data.can_install,
      };
      _pendingUpdate = merged;
      syncUpdateUI(merged);
      if (_autoInstallWhenReady) {
        await installUpdate(true);
      }
      return;
    }
    if (data.status === 'error') {
      stopUpdatePolling();
      hideProgress();
      hideBannerProgress();
      _updateRunning = false;
      _autoInstallWhenReady = false;
      setUpdateMessage(data.error || t('updates.download_failed'), 'error');
      setBannerText(data.error || t('updates.download_failed'));
      setBannerButtons(true);
      syncUpdateUI(_pendingUpdate || {});
    }
  } catch {
    /* keep polling */
  }
}

function syncUpdateUI(data) {
  if (!data) return;
  const notes = document.getElementById('update-release-notes');
  const box = document.querySelector('.update-release-box');
  if (notes) notes.textContent = data.release_notes || '';
  if (box) box.classList.toggle('hidden', !data.release_notes);

  if (!data.update_available) {
    setUpdateMessage(t('updates.up_to_date'), 'success');
    setUpdateButtons({ check: true, download: false, install: false, oneClick: false });
    return;
  }

  setUpdateMessage(t('updates.available', { version: data.latest_version }), 'success');

  const canInstall = data.can_install !== false;
  if (canInstall) {
    setUpdateButtons({
      check: true,
      download: false,
      install: false,
      oneClick: true,
    });
  } else if (data.ready) {
    setUpdateButtons({ check: true, download: false, install: false, oneClick: false });
  } else {
    setUpdateButtons({ check: true, download: false, install: false, oneClick: false });
  }
}

function showUpdateBanner(data) {
  const banner = document.getElementById('update-banner');
  if (!banner || !data?.update_available) return;
  banner.classList.remove('hidden');
  setBannerText(t('updates.banner', { version: data.latest_version }));
  setBannerButtons(true);
}

function hideUpdateBanner() {
  document.getElementById('update-banner')?.classList.add('hidden');
}

function setBannerText(text) {
  const el = document.getElementById('update-banner-text');
  if (el) el.textContent = text;
}

function setBannerButtons(show) {
  document.querySelectorAll('#update-banner .update-banner-actions button').forEach(btn => {
    btn.disabled = !show;
    btn.style.visibility = show ? 'visible' : 'hidden';
  });
}

function resetUpdateUI() {
  stopUpdatePolling();
  hideProgress();
  setUpdateMessage('', 'info');
  setUpdateButtons({ check: true, download: false, install: false, oneClick: false });
  const notes = document.getElementById('update-release-notes');
  if (notes) notes.textContent = '';
  document.querySelector('.update-release-box')?.classList.add('hidden');
}

function setUpdateMessage(text, kind) {
  const el = document.getElementById('update-status-msg');
  if (!el) return;
  el.textContent = text;
  el.className = 'update-status-msg';
  if (kind === 'error') el.classList.add('update-status-error');
  if (kind === 'success') el.classList.add('update-status-success');
}

function setUpdateButtons({ check, download, install, oneClick }) {
  const btnCheck = document.getElementById('btn-check-updates');
  const btnOne = document.getElementById('btn-update-now-settings');
  const btnDownload = document.getElementById('btn-download-update');
  const btnInstall = document.getElementById('btn-install-update');
  if (btnCheck) btnCheck.disabled = !check;
  if (btnOne) btnOne.classList.toggle('hidden', !oneClick);
  if (btnDownload) btnDownload.classList.toggle('hidden', !download);
  if (btnInstall) btnInstall.classList.toggle('hidden', !install);
}

function showProgress(pct) {
  const wrap = document.getElementById('update-progress-wrap');
  const bar = document.getElementById('update-progress-bar');
  if (wrap) wrap.classList.remove('hidden');
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
}

function hideProgress() {
  document.getElementById('update-progress-wrap')?.classList.add('hidden');
}

function showBannerProgress(pct) {
  const wrap = document.getElementById('update-banner-progress-wrap');
  const bar = document.getElementById('update-banner-progress-bar');
  if (wrap) wrap.classList.remove('hidden');
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
}

function hideBannerProgress() {
  document.getElementById('update-banner-progress-wrap')?.classList.add('hidden');
}

function toggleDevNotice(show) {
  document.getElementById('update-dev-notice')?.classList.toggle('hidden', !show);
}
