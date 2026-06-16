/* Help center, contextual tooltips, and guided tour */
import { t } from './i18n.js';
import { switchScreen } from './navigation.js';
import { openModal, closeModal } from './modals.js';

const TOUR_STORAGE_KEY = 'jobapply_tour_completed';

const FAQ_ITEMS = [
  { id: 1, cat: 'start' },
  { id: 2, cat: 'start' },
  { id: 3, cat: 'workflow' },
  { id: 4, cat: 'workflow' },
  { id: 5, cat: 'apply' },
  { id: 6, cat: 'apply' },
  { id: 7, cat: 'settings' },
  { id: 8, cat: 'languages' },
  { id: 9, cat: 'languages' },
  { id: 10, cat: 'troubleshoot' },
  { id: 11, cat: 'troubleshoot' },
  { id: 12, cat: 'troubleshoot' },
];

const TOUR_STEPS = [
  { screen: 'workflow', selector: '.workflow-header', title: 'help.tour1_title', body: 'help.tour1_body', example: 'help.tour1_example' },
  { screen: 'workflow', selector: '#wf-checklist-1', before: 'workflowStep1', title: 'help.tour2_title', body: 'help.tour2_body', example: 'help.tour2_example' },
  { screen: 'settings', selector: '#set-spoken-languages', title: 'help.tour3_title', body: 'help.tour3_body', example: 'help.tour3_example' },
  { screen: 'dashboard', selector: '#apply-mode-select', title: 'help.tour4_title', body: 'help.tour4_body', example: 'help.tour4_example' },
  { screen: 'dashboard', selector: '#btn-start', title: 'help.tour5_title', body: 'help.tour5_body', example: 'help.tour5_example' },
  { screen: 'dashboard', demo: 'review', title: 'help.tour6_title', body: 'help.tour6_body', example: 'help.tour6_example' },
  { screen: 'applications', selector: '#screen-applications h2', title: 'help.tour7_title', body: 'help.tour7_body', example: 'help.tour7_example' },
  { screen: 'settings', selector: '#tour-job-titles-section', title: 'help.tour8_title', body: 'help.tour8_body', example: 'help.tour8_example' },
];

let _tourIndex = 0;
let _tourActive = false;
let _tooltipEl = null;
let _tourResizeHandler = null;
const TOUR_PAD = 16;
const TOUR_GAP = 12;

export function initHelp() {
  initTooltips();
  renderHelpCenter();
  bindHelpSearch();
}

export function refreshHelp() {
  initTooltips();
  renderHelpCenter();
  if (_tourActive) showTourStep(_tourIndex);
}

export function openHelpCenter() {
  renderHelpCenter();
  openModal('modal-help-center');
}

export function closeHelpCenter() {
  closeModal('modal-help-center');
}

export function startHelpTour(fromHelpCenter = false) {
  if (fromHelpCenter) closeHelpCenter();
  _tourIndex = 0;
  _tourActive = true;
  document.getElementById('tour-overlay')?.classList.remove('hidden');
  if (!_tourResizeHandler) {
    _tourResizeHandler = () => { if (_tourActive) relayoutTourStep(); };
    window.addEventListener('resize', _tourResizeHandler);
  }
  showTourStep(0);
}

export function endTour(completed = true) {
  _tourActive = false;
  hideAllTourDemos();
  document.getElementById('tour-overlay')?.classList.add('hidden');
  document.querySelectorAll('.tour-highlight').forEach(el => el.classList.remove('tour-highlight'));
  if (completed) {
    try { localStorage.setItem(TOUR_STORAGE_KEY, '1'); } catch { /* ignore */ }
  }
}

export function maybeStartTourOnFirstVisit() {
  try {
    if (localStorage.getItem(TOUR_STORAGE_KEY)) return;
  } catch { return; }
  setTimeout(() => {
    if (!document.getElementById('wizard-overlay')?.classList.contains('hidden')) return;
    startHelpTour(false);
  }, 1200);
}

function bindHelpSearch() {
  const input = document.getElementById('help-search');
  if (!input || input.dataset.bound) return;
  input.dataset.bound = '1';
  input.addEventListener('input', () => renderHelpCenter(input.value.trim().toLowerCase()));
}

function renderHelpCenter(filter = '') {
  const list = document.getElementById('help-faq-list');
  if (!list) return;
  const catSel = document.getElementById('help-category-filter');
  const cat = catSel?.value || 'all';

  list.innerHTML = '';
  for (const item of FAQ_ITEMS) {
    const q = t(`help.faq${item.id}_q`);
    const a = t(`help.faq${item.id}_a`);
    const catLabel = t(`help.category_${item.cat}`);
    if (cat !== 'all' && item.cat !== cat) continue;
    if (filter && !q.toLowerCase().includes(filter) && !a.toLowerCase().includes(filter)) continue;

    const details = document.createElement('details');
    details.className = 'help-faq-item';
    details.innerHTML = `
      <summary><span class="help-faq-cat">${catLabel}</span> ${escapeHtml(q)}</summary>
      <div class="help-faq-body">${formatHelpText(a)}</div>`;
    list.appendChild(details);
  }
  if (!list.children.length) {
    list.innerHTML = `<p class="text-dim">${escapeHtml(t('help.no_results'))}</p>`;
  }
}

function formatHelpText(text) {
  return escapeHtml(text)
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function initTooltips() {
  document.querySelectorAll('[data-tip-key]').forEach(el => {
    if (el.querySelector('.tip-trigger')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tip-trigger';
    btn.setAttribute('aria-label', t('help.tip_label'));
    btn.textContent = '?';
    btn.addEventListener('mouseenter', () => showTooltip(btn, t(el.dataset.tipKey)));
    btn.addEventListener('focus', () => showTooltip(btn, t(el.dataset.tipKey)));
    btn.addEventListener('mouseleave', hideTooltip);
    btn.addEventListener('blur', hideTooltip);
    el.classList.add('has-tip-wrap');
    el.appendChild(btn);
  });
}

function showTooltip(anchor, text) {
  if (!text || text.startsWith('help.')) return;
  hideTooltip();
  _tooltipEl = document.createElement('div');
  _tooltipEl.className = 'help-tooltip';
  _tooltipEl.setAttribute('role', 'tooltip');
  _tooltipEl.textContent = text;
  document.body.appendChild(_tooltipEl);
  const rect = anchor.getBoundingClientRect();
  _tooltipEl.style.top = `${rect.bottom + window.scrollY + 8}px`;
  _tooltipEl.style.left = `${Math.max(8, rect.left + window.scrollX - 20)}px`;
}

function hideTooltip() {
  _tooltipEl?.remove();
  _tooltipEl = null;
}

function getActiveTourSteps() {
  return TOUR_STEPS;
}

function isTourTargetVisible(el) {
  if (!el || el.classList.contains('hidden')) return false;
  if (el.closest('.hidden:not(.screen)')) return false;
  const r = el.getBoundingClientRect();
  return r.width > 4 && r.height > 4;
}

function hideAllTourDemos() {
  document.getElementById('tour-review-demo')?.classList.add('hidden');
}

function prepareTourStep(step) {
  hideAllTourDemos();
  if (step.before === 'workflowStep1' && typeof window.workflowGoStep === 'function') {
    window.workflowGoStep(1);
  }
  if (step.demo === 'review') {
    const live = document.getElementById('review-card');
    if (!isTourTargetVisible(live)) {
      const demo = document.getElementById('tour-review-demo');
      demo?.classList.remove('hidden');
      demo?.setAttribute('aria-hidden', 'false');
    }
  }
}

function resolveTourTarget(step) {
  if (step.demo === 'review') {
    const live = document.getElementById('review-card');
    if (isTourTargetVisible(live)) return live;
    return document.getElementById('tour-review-demo');
  }
  if (!step.selector) return null;
  return document.querySelector(step.selector);
}

async function waitForTourTarget(step, maxMs = 900) {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    prepareTourStep(step);
    const target = resolveTourTarget(step);
    if (target && isTourTargetVisible(target)) return target;
    await new Promise(r => setTimeout(r, 60));
  }
  prepareTourStep(step);
  return resolveTourTarget(step);
}

function tourStepDelay(step) {
  if (step.demo === 'review') return 80;
  if (step.screen === 'settings') return 160;
  if (step.before === 'workflowStep1') return 120;
  return 50;
}

function scrollTourTargetIntoView(target) {
  const margin = TOUR_PAD + 40;
  const scrollBy = (y) => {
    try {
      window.scrollBy({ top: y, behavior: 'instant' });
    } catch {
      window.scrollBy(0, y);
    }
  };

  let r = target.getBoundingClientRect();
  if (r.top < margin) {
    scrollBy(r.top - margin);
  } else if (r.bottom > window.innerHeight - margin) {
    scrollBy(r.bottom - window.innerHeight + margin);
  }

  r = target.getBoundingClientRect();
  const centerOffset = r.top + r.height / 2 - window.innerHeight / 2;
  if (Math.abs(centerOffset) > 24) {
    scrollBy(centerOffset);
  }
}

function layoutTourBackdrop(target, backdrop) {
  if (!backdrop) return;
  const r = target.getBoundingClientRect();
  if (r.width < 4 || r.height < 4) {
    backdrop.style.width = '0';
    backdrop.style.height = '0';
    return;
  }
  const pad = 8;
  const edge = TOUR_PAD;
  let top = r.top - pad;
  let left = r.left - pad;
  let width = r.width + pad * 2;
  let height = r.height + pad * 2;

  if (top < edge) {
    height -= edge - top;
    top = edge;
  }
  if (left < edge) {
    width -= edge - left;
    left = edge;
  }
  if (top + height > window.innerHeight - edge) {
    height = window.innerHeight - edge - top;
  }
  if (left + width > window.innerWidth - edge) {
    width = window.innerWidth - edge - left;
  }

  backdrop.style.top = `${top}px`;
  backdrop.style.left = `${left}px`;
  backdrop.style.width = `${Math.max(32, width)}px`;
  backdrop.style.height = `${Math.max(24, height)}px`;
}

function layoutTourPopover(target, pop) {
  pop.classList.remove('tour-popover-docked');
  pop.style.top = '0';
  pop.style.left = '0';
  pop.style.bottom = '';
  pop.style.right = '';
  pop.style.width = '';

  const popH = pop.offsetHeight;
  const popW = pop.offsetWidth;
  const r = target.getBoundingClientRect();
  const vh = window.innerHeight;
  const vw = window.innerWidth;

  const spaceBelow = vh - r.bottom - TOUR_GAP - TOUR_PAD;
  const spaceAbove = r.top - TOUR_GAP - TOUR_PAD;
  let top;

  if (popH <= spaceBelow || spaceBelow >= spaceAbove) {
    top = r.bottom + TOUR_GAP;
  } else {
    top = r.top - TOUR_GAP - popH;
  }

  const fitsVertically = top >= TOUR_PAD && top + popH <= vh - TOUR_PAD;
  if (!fitsVertically) {
    pop.classList.add('tour-popover-docked');
    pop.style.top = 'auto';
    pop.style.bottom = `${TOUR_PAD}px`;
    pop.style.left = `${TOUR_PAD}px`;
    pop.style.right = `${TOUR_PAD}px`;
    return;
  }

  const left = Math.max(TOUR_PAD, Math.min(r.left, vw - popW - TOUR_PAD));
  pop.style.top = `${top}px`;
  pop.style.left = `${left}px`;
}

function updateTourPopoverContent(index, steps, step) {
  document.getElementById('tour-step-num').textContent = `${index + 1} / ${steps.length}`;
  document.getElementById('tour-title').textContent = t(step.title);
  document.getElementById('tour-body').textContent = t(step.body);

  const exEl = document.getElementById('tour-example');
  const exText = t(step.example);
  if (exEl) {
    exEl.textContent = exText.startsWith('help.') ? '' : exText;
    exEl.parentElement.classList.toggle('hidden', !exEl.textContent);
  }

  const nextBtn = document.getElementById('tour-next-btn');
  if (nextBtn) {
    nextBtn.textContent = index >= steps.length - 1 ? t('help.tour_finish') : t('help.tour_next');
  }
}

function relayoutTourStep() {
  const steps = getActiveTourSteps();
  const step = steps[_tourIndex];
  if (!step) return;
  const target = resolveTourTarget(step);
  const pop = document.getElementById('tour-popover');
  const backdrop = document.getElementById('tour-backdrop');
  if (!target || !pop || !isTourTargetVisible(target)) return;
  scrollTourTargetIntoView(target);
  layoutTourBackdrop(target, backdrop);
  layoutTourPopover(target, pop);
  requestAnimationFrame(() => layoutTourPopover(target, pop));
}

async function applyTourStepLayout(index, steps, step) {
  document.querySelectorAll('.tour-highlight').forEach(el => el.classList.remove('tour-highlight'));
  const target = await waitForTourTarget(step);
  const pop = document.getElementById('tour-popover');
  const backdrop = document.getElementById('tour-backdrop');
  if (!target || !pop || !isTourTargetVisible(target)) {
    showTourStep(index + 1);
    return;
  }

  target.classList.add('tour-highlight');
  scrollTourTargetIntoView(target);
  updateTourPopoverContent(index, steps, step);

  requestAnimationFrame(() => {
    layoutTourBackdrop(target, backdrop);
    layoutTourPopover(target, pop);
    requestAnimationFrame(() => layoutTourPopover(target, pop));
  });

  if (step.screen === 'settings' || step.demo === 'review') {
    setTimeout(() => relayoutTourStep(), 280);
  }
}

function showTourStep(index) {
  const steps = getActiveTourSteps();
  if (index >= steps.length) {
    endTour(true);
    return;
  }
  if (index >= 0 && index !== _tourIndex) {
    hideAllTourDemos();
  }
  _tourIndex = index;
  const step = steps[index];
  switchScreen(step.screen);
  prepareTourStep(step);

  setTimeout(() => applyTourStepLayout(index, steps, step), tourStepDelay(step));
}

export function tourNext() {
  showTourStep(_tourIndex + 1);
}

export function tourPrev() {
  if (_tourIndex > 0) showTourStep(_tourIndex - 1);
}

export function tourSkip() {
  endTour(false);
}

export function filterHelpCategory() {
  const input = document.getElementById('help-search');
  renderHelpCenter(input?.value.trim().toLowerCase() || '');
}
