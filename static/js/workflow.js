/* Career workflow — step-by-step guide */
import { t, getLocale } from './i18n.js';
import { escHtml } from './helpers.js';
import { switchScreen } from './navigation.js';
import { checkLoginSessions } from './login.js';

let _state = { current_step: 1, completed_steps: [], analyses: {}, readiness: {} };
let _lastJobAnalysis = null;

export async function loadWorkflow() {
  try {
    const res = await fetch('/api/workflow/status');
    _state = await res.json();
    renderStepper();
    renderChecklist();
    showWorkflowStep(_state.current_step || 1);
    restoreAnalyses();
    checkLoginSessions();
  } catch (e) {
    console.warn('Workflow load failed:', e);
  }
}

function renderStepper() {
  const el = document.getElementById('workflow-stepper');
  if (!el) return;
  const labels = [
    t('workflow.step1_short'),
    t('workflow.step2_short'),
    t('workflow.step3_short'),
    t('workflow.step4_short'),
    t('workflow.step5_short'),
    t('workflow.step6_short'),
  ];
  el.innerHTML = labels.map((label, i) => {
    const n = i + 1;
    const done = _state.completed_steps?.includes(n);
    const active = n === (_state.current_step || 1);
    return `<button type="button" class="wf-step-btn${done ? ' done' : ''}${active ? ' active' : ''}"
      onclick="workflowGoStep(${n})" aria-selected="${active}">${n}. ${escHtml(label)}</button>`;
  }).join('');
}

function renderChecklist() {
  const el = document.getElementById('wf-checklist-1');
  if (!el) return;
  const r = _state.readiness || {};
  const items = [
    [r.has_profile, t('workflow.check_profile')],
    [r.has_cv, t('workflow.check_cv')],
    [r.has_experience, t('workflow.check_experience')],
    [r.has_languages, t('workflow.check_languages')],
    [r.ai_available, t('workflow.check_ai')],
  ];
  el.innerHTML = items.map(([ok, label]) =>
    `<li class="${ok ? 'ok' : 'pending'}">${ok ? '✓' : '○'} ${escHtml(label)}</li>`
  ).join('');
}

function showWorkflowStep(n) {
  document.querySelectorAll('.workflow-panel').forEach(p => {
    p.classList.toggle('hidden', parseInt(p.dataset.wfStep, 10) !== n);
  });
  _state.current_step = n;
  renderStepper();
}

export function workflowGoStep(n) {
  showWorkflowStep(n);
  fetch('/api/workflow/step', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step: n }),
  }).catch(() => {});
}

export async function workflowCompleteStep(n) {
  await fetch('/api/workflow/step', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step: n, complete: true }),
  });
  await loadWorkflow();
  if (n < 6) workflowGoStep(n + 1);
}

export async function workflowFinish() {
  await workflowCompleteStep(6);
  switchScreen('dashboard');
}

function restoreAnalyses() {
  const jobs = _state.analyses?.jobs;
  if (jobs) renderJobsResult(jobs);
  if (_state.analyses?.recruiters) renderMarkdownResult('wf-recruiters-result', _state.analyses.recruiters);
  if (_state.analyses?.references) renderMarkdownResult('wf-references-result', _state.analyses.references);
}

export async function workflowAnalyzeJobs() {
  const btn = document.getElementById('wf-analyze-jobs-btn');
  const out = document.getElementById('wf-jobs-result');
  if (btn) { btn.disabled = true; btn.textContent = t('workflow.analyzing'); }
  try {
    const res = await fetch(`/api/workflow/analyze/jobs?locale=${getLocale()}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'failed');
    renderJobsResult(data);
    _lastJobAnalysis = data;
  } catch (e) {
    if (out) {
      out.classList.remove('hidden');
      out.innerHTML = `<p class="text-error">${escHtml(t('workflow.analysis_error'))}</p>`;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = t('workflow.run_analysis'); }
  }
}

function renderJobsResult(data) {
  const out = document.getElementById('wf-jobs-result');
  if (!out) return;
  out.classList.remove('hidden');

  if (data.mode === 'manual') {
    out.innerHTML = `
      <p><strong>${escHtml(t('workflow.manual_mode'))}</strong></p>
      <p>${escHtml(t('workflow.manual_instructions'))}</p>`;
    const ta = document.createElement('textarea');
    ta.className = 'form-control';
    ta.rows = 12;
    ta.readOnly = true;
    ta.id = 'wf-manual-prompt';
    ta.value = data.prompt || '';
    out.appendChild(ta);
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-ghost btn-sm';
    copyBtn.style.marginTop = '8px';
    copyBtn.textContent = t('workflow.copy_prompt');
    copyBtn.onclick = () => workflowCopyPrompt();
    out.appendChild(copyBtn);
    return;
  }

  const c = data.content || {};
  _lastJobAnalysis = data;
  const sections = [];
  if (c.strengths?.length) {
    sections.push(`<h4>${escHtml(t('workflow.strengths'))}</h4><ul>${c.strengths.map(s => `<li>${escHtml(s)}</li>`).join('')}</ul>`);
  }
  if (c.gaps?.length) {
    sections.push(`<h4>${escHtml(t('workflow.gaps'))}</h4><ul>${c.gaps.map(s => `<li>${escHtml(s)}</li>`).join('')}</ul>`);
  }
  if (c.improvements?.length) {
    sections.push(`<h4>${escHtml(t('workflow.improvements'))}</h4><ul>${c.improvements.map(s => `<li>${escHtml(s)}</li>`).join('')}</ul>`);
  }
  if (c.suggested_titles?.length) {
    sections.push(`<h4>${escHtml(t('workflow.suggested_titles'))}</h4><p>${c.suggested_titles.map(escHtml).join(', ')}</p>`);
  }
  if (c.summary) {
    sections.push(`<div class="wf-summary">${formatMarkdown(c.summary)}</div>`);
  }
  out.innerHTML = sections.join('') || `<pre>${escHtml(data.raw || '')}</pre>`;
  renderSearchSuggestions(c);
}

function renderSearchSuggestions(c) {
  const el = document.getElementById('wf-search-suggestions');
  if (!el || !c) return;
  const titles = c.suggested_titles || [];
  const keywords = c.suggested_keywords || [];
  const locations = c.suggested_locations || [];
  if (!titles.length && !keywords.length) {
    el.classList.add('hidden');
    return;
  }
  el.classList.remove('hidden');
  el.innerHTML = `
    <h4>${escHtml(t('workflow.search_preview'))}</h4>
    ${titles.length ? `<p><strong>${escHtml(t('workflow.suggested_titles'))}:</strong> ${titles.map(escHtml).join(', ')}</p>` : ''}
    ${keywords.length ? `<p><strong>${escHtml(t('workflow.suggested_keywords'))}:</strong> ${keywords.map(escHtml).join(', ')}</p>` : ''}
    ${locations.length ? `<p><strong>${escHtml(t('workflow.suggested_locations'))}:</strong> ${locations.map(escHtml).join(', ')}</p>` : ''}`;
}

export async function workflowApplySearch() {
  const c = _lastJobAnalysis?.content || _state.analyses?.jobs?.content || {};
  const res = await fetch('/api/workflow/apply-search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      titles: c.suggested_titles || [],
      keywords: c.suggested_keywords || [],
      locations: c.suggested_locations || [],
    }),
  });
  const data = await res.json();
  const btn = document.getElementById('wf-apply-search-btn');
  if (res.ok && btn) {
    btn.textContent = t('workflow.applied_ok');
    btn.classList.add('btn-ghost');
    btn.classList.remove('btn-success');
  }
}

export async function workflowAnalyzeRecruiters() {
  await runAnalysis('/api/workflow/analyze/recruiters', 'wf-recruiters-result', t('workflow.run_recruiters'));
}

export async function workflowAnalyzeReferences() {
  await runAnalysis('/api/workflow/analyze/references', 'wf-references-result', t('workflow.run_references'));
}

async function runAnalysis(url, outId, btnLabel) {
  const out = document.getElementById(outId);
  if (out) { out.classList.remove('hidden'); out.innerHTML = `<p>${escHtml(t('workflow.analyzing'))}</p>`; }
  try {
    const res = await fetch(`${url}?locale=${getLocale()}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    renderMarkdownResult(outId, data);
  } catch {
    if (out) out.innerHTML = `<p class="text-error">${escHtml(t('workflow.analysis_error'))}</p>`;
  }
}

function renderMarkdownResult(outId, data) {
  const out = document.getElementById(outId);
  if (!out) return;
  out.classList.remove('hidden');
  if (data.mode === 'manual') {
    out.innerHTML = `
      <p><strong>${escHtml(t('workflow.manual_mode'))}</strong></p>
      <textarea class="form-control" rows="10" readonly>${escHtml(data.prompt || '')}</textarea>
      <button class="btn btn-ghost btn-sm" style="margin-top:8px" onclick="workflowCopyText(this.previousElementSibling.value)">${escHtml(t('workflow.copy_prompt'))}</button>`;
    return;
  }
  out.innerHTML = formatMarkdown(data.content || data.raw || '');
}

function formatMarkdown(text) {
  return escHtml(text)
    .replace(/^## (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h5>$1</h5>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}

export function workflowCopyPrompt() {
  const ta = document.getElementById('wf-manual-prompt');
  if (ta) workflowCopyText(ta.value);
}

export function workflowCopyText(text) {
  navigator.clipboard.writeText(text).catch(() => {});
}

export function isWorkflowIncomplete() {
  return !(_state.completed_steps?.length >= 6);
}
