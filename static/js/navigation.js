/* ═══════════════════════════════════════════════════════════════
   NAV TABS — with ARIA tablist keyboard navigation (WCAG 2.1 §2.1.1)
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { loadFeedHistory } from './feed.js';
import { loadApplications } from './applications.js';
import { loadProfileFiles } from './profile.js';
import { loadAnalytics } from './analytics.js';
import { loadResumes } from './resumes.js';
import { loadKnowledgeBase } from './knowledge-base.js';
import { loadSettings, loadApplyMode, loadDefaultResume } from './settings.js';
import { loadWorkflow } from './workflow.js';
import { loadUpdatePanel, maybeAutoCheckUpdates } from './updates.js';
import { loadShortcutsPanel, maybeShowShortcutsPrompt } from './shortcuts.js';
import { initHelp, maybeStartTourOnFirstVisit } from './help.js';
import { showNavLoading, hideNavLoading } from './loading.js';
import { onReady } from './i18n.js';

/** Screens hidden in Mac/apply client mode (split architecture). */
const CLIENT_HIDDEN_SCREENS = new Set(['workflow', 'dashboard', 'analytics', 'resumes']);

export function initNavTabs() {
  applyClientModeNav();
  const tabs = document.querySelectorAll('#navbar .nav-tabs a[role="tab"]');
  tabs.forEach(a => {
    a.addEventListener('click', () => switchScreen(a.dataset.screen));
    a.addEventListener('keydown', e => {
      const tabArr = visibleNavTabs();
      const idx = tabArr.indexOf(a);
      if (idx < 0) return;
      let newIdx = -1;
      if (e.key === 'ArrowRight') newIdx = (idx + 1) % tabArr.length;
      else if (e.key === 'ArrowLeft') newIdx = (idx - 1 + tabArr.length) % tabArr.length;
      else if (e.key === 'Home') newIdx = 0;
      else if (e.key === 'End') newIdx = tabArr.length - 1;
      if (newIdx >= 0) {
        e.preventDefault();
        tabArr[newIdx].focus();
        switchScreen(tabArr[newIdx].dataset.screen);
      }
    });
  });
}

function visibleNavTabs() {
  return [...document.querySelectorAll('#navbar .nav-tabs a[role="tab"]')]
    .filter(a => a.closest('li') && !a.closest('li').classList.contains('hidden'));
}

export function applyClientModeNav() {
  const clientMode = !!state.clientMode;
  document.body.classList.toggle('client-mode', clientMode);
  document.querySelectorAll('#navbar .nav-tabs li[data-client-hide]').forEach(li => {
    li.classList.toggle('hidden', clientMode);
  });
}

export async function switchScreen(name) {
  if (state.clientMode && CLIENT_HIDDEN_SCREENS.has(name)) {
    name = 'applications';
  }
  state.currentScreen = name;
  document.querySelectorAll('#navbar .nav-tabs a[role="tab"]').forEach(a => {
    const isActive = a.dataset.screen === name;
    a.classList.toggle('active', isActive);
    a.setAttribute('aria-selected', isActive ? 'true' : 'false');
    a.tabIndex = isActive ? 0 : -1;
  });
  document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
  const el = document.getElementById('screen-' + name);
  if (el) el.classList.remove('hidden');

  const loaders = [];
  if (name === 'workflow') loaders.push(loadWorkflow());
  if (name === 'dashboard') {
    loaders.push(loadFeedHistory(), loadApplyMode(), loadDefaultResume());
  }
  if (name === 'applications') loaders.push(loadApplications());
  if (name === 'profile') loaders.push(loadProfileFiles());
  if (name === 'analytics') loaders.push(loadAnalytics());
  if (name === 'resumes') loaders.push(loadResumes());
  if (name === 'knowledge-base') loaders.push(loadKnowledgeBase());
  if (name === 'settings') {
    loaders.push(loadSettings(), loadShortcutsPanel(), loadUpdatePanel());
  }

  if (loaders.length) {
    showNavLoading();
    try {
      await Promise.allSettled(loaders);
    } finally {
      hideNavLoading();
    }
  }
}

export function showApp() {
  document.getElementById('wizard-overlay').classList.add('hidden');
  document.getElementById('navbar').classList.remove('hidden');
  document.getElementById('app-screens').classList.remove('hidden');
  applyClientModeNav();
  const home = state.clientMode ? 'applications' : 'workflow';
  switchScreen(home);
  if (!state.clientMode) loadWorkflow();
  onReady(() => {
    initHelp();
    if (!state.clientMode) maybeStartTourOnFirstVisit();
    setTimeout(() => maybeAutoCheckUpdates(), 2500);
    maybeShowShortcutsPrompt();
  });
}

export async function detectClientMode() {
  try {
    const res = await fetch('/api/setup/status');
    const data = await res.json();
    state.clientMode = !!data.client_mode;
  } catch {
    state.clientMode = false;
  }
  applyClientModeNav();
  return state.clientMode;
}
