/* ═══════════════════════════════════════════════════════════════
   WIZARD
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { escHtml } from './helpers.js';
import { showApp } from './navigation.js';
import { checkLoginSessions, closeLoginBrowser } from './login.js';
import { t } from './i18n.js';
import {
  populateFormFromExtracted,
  fetchCvImport,
  fetchLinkedInImport,
  fetchLinkedInZipImport,
  setImportStatus,
} from './profile-import.js';

export function showWizard(setupData) {
  document.getElementById('wizard-overlay').classList.remove('hidden');
  document.getElementById('navbar').classList.add('hidden');
  document.getElementById('app-screens').classList.add('hidden');

  state.aiAvailable = !!(setupData && setupData.ai_available);
  state.wizardData.imported_experience_text = null;
  state.wizardData.llm = null;

  // AI status badge
  const badge = document.getElementById('wizard-ai-status');
  if (setupData && setupData.ai_available) {
    badge.className = 'status-badge ok';
    badge.innerHTML = '<span class="dot dot-green"></span> ' + t('wizard.ai_configured');
  } else {
    badge.className = 'status-badge warn';
    badge.innerHTML = '<span class="dot dot-yellow"></span> ' + t('wizard.ai_not_configured');
  }

  // Build progress dots
  const prog = document.getElementById('wizard-progress');
  prog.innerHTML = '';
  for (let i = 0; i < 7; i++) {
    const d = document.createElement('div');
    d.className = 'step-dot' + (i === 0 ? ' active' : '');
    prog.appendChild(d);
  }

  setWizardStep(0);
  wizardRefreshFiles();
}

export function setWizardStep(n) {
  state.wizardStep = n;
  document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
  const step = document.querySelector(`.wizard-step[data-step="${n}"]`);
  if (step) step.classList.add('active');

  // Update progress dots and aria
  const progress = document.getElementById('wizard-progress');
  if (progress) progress.setAttribute('aria-valuenow', n + 1);
  document.querySelectorAll('.wizard-progress .step-dot').forEach((d, i) => {
    d.className = 'step-dot' + (i < n ? ' done' : '') + (i === n ? ' active' : '');
  });

  // Build summary on last step
  if (n === 6) buildWizardSummary();
  // Check login sessions when entering Platform Login step
  if (n === 1) checkLoginSessions();
  // Refresh import hint when entering profile step
  if (n === 3) _updateWizardImportHint();
}

function _updateWizardImportHint() {
  const hint = document.getElementById('wizard-import-ai-hint');
  if (!hint) return;
  hint.textContent = state.aiAvailable
    ? t('wizard.import_ai_ready')
    : t('wizard.import_ai_required');
}

function _applyWizardExtracted(extracted) {
  const expText = populateFormFromExtracted(extracted, 'wiz');
  if (expText) {
    state.wizardData.imported_experience_text = expText;
  }
}

export async function wizardImportFromCV(input) {
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;

  if (!state.aiAvailable) {
    setImportStatus('wizard-import-status', t('wizard.import_ai_required'), true);
    return;
  }

  setImportStatus('wizard-import-status', t('settings.importing'));
  try {
    const data = await fetchCvImport(file, state.wizardData.llm);
    _applyWizardExtracted(data.extracted);
    setImportStatus('wizard-import-status', t('wizard.import_applied_short'));
    await wizardRefreshFiles();
  } catch (e) {
    setImportStatus('wizard-import-status', e.message || t('settings.import_failed'), true);
  }
}

export async function wizardImportFromLinkedIn() {
  if (!state.aiAvailable) {
    setImportStatus('wizard-import-status', t('wizard.import_ai_required'), true);
    return;
  }

  try {
    const sessionsRes = await fetch('/api/login/sessions');
    const sessions = sessionsRes.ok ? await sessionsRes.json() : {};
    if (!sessions.linkedin) {
      setImportStatus('wizard-import-status', t('settings.linkedin_connect_first'), true);
      return;
    }
  } catch {
    setImportStatus('wizard-import-status', t('settings.linkedin_connect_first'), true);
    return;
  }

  const btn = document.getElementById('wizard-btn-import-linkedin');
  if (btn) { btn.disabled = true; btn.textContent = t('settings.importing'); }
  setImportStatus('wizard-import-status', t('settings.linkedin_importing'));

  try {
    const data = await fetchLinkedInImport(state.wizardData.llm);
    _applyWizardExtracted(data.extracted);
    setImportStatus('wizard-import-status', t('wizard.import_applied_short'));
    await wizardRefreshFiles();
  } catch (e) {
    setImportStatus('wizard-import-status', e.message || t('settings.import_failed'), true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = t('settings.import_from_linkedin'); }
  }
}

export async function wizardImportLinkedInZip(input) {
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;

  if (!state.aiAvailable) {
    setImportStatus('wizard-import-status', t('wizard.import_ai_required'), true);
    return;
  }

  setImportStatus('wizard-import-status', t('settings.importing'));
  try {
    const data = await fetchLinkedInZipImport(file, state.wizardData.llm);
    _applyWizardExtracted(data.extracted);
    setImportStatus('wizard-import-status', t('wizard.import_applied_short'));
    await wizardRefreshFiles();
  } catch (e) {
    setImportStatus('wizard-import-status', e.message || t('settings.import_failed'), true);
  }
}

/** Auto-fill wizard from a resume file (used on fallback resume step). */
export async function wizardAutoFillFromResume(file) {
  if (!state.aiAvailable || !file) return;
  setImportStatus('wizard-resume-import-status', t('wizard.resume_autofill'));
  try {
    const data = await fetchCvImport(file, state.wizardData.llm);
    _applyWizardExtracted(data.extracted);
    setImportStatus('wizard-resume-import-status', t('wizard.resume_autofill_done'));
  } catch (e) {
    setImportStatus('wizard-resume-import-status', e.message || t('settings.import_failed'), true);
  }
}

const WIZARD_LLM_DEFAULTS = {
  google: 'gemini-2.0-flash',
  groq: 'llama-3.3-70b-versatile',
  openrouter: 'meta-llama/llama-3.3-70b-instruct:free',
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
  deepseek: 'deepseek-chat',
};

export async function wizardValidateLLMKey() {
  const provider = document.getElementById('wiz-llm-provider')?.value;
  const apiKey = document.getElementById('wiz-llm-api-key')?.value;
  const status = document.getElementById('wizard-llm-key-status');
  const btn = document.getElementById('btn-wizard-validate-key');

  if (!provider) {
    if (status) { status.textContent = t('settings.select_provider'); status.style.color = '#f87171'; }
    return;
  }
  if (!apiKey) {
    if (status) { status.textContent = t('settings.enter_api_key'); status.style.color = '#f87171'; }
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = t('settings.validating'); }
  if (status) status.textContent = '';

  const model = WIZARD_LLM_DEFAULTS[provider] || '';
  try {
    const res = await fetch('/api/ai/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: apiKey, model }),
    });
    const data = await res.json();
    if (data.valid) {
      state.wizardData.llm = { provider, api_key: apiKey, model };
      state.aiAvailable = true;
      _updateWizardImportHint();
      if (status) {
        status.textContent = data.message || t('settings.key_valid');
        status.style.color = '#34d399';
      }
    } else {
      if (status) {
        status.textContent = data.message || t('settings.key_invalid');
        status.style.color = '#f87171';
      }
    }
  } catch {
    if (status) {
      status.textContent = t('settings.validation_failed');
      status.style.color = '#f87171';
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = t('button.validate'); }
  }
}

export function wizardNext() {
  if (state.wizardStep < 6) setWizardStep(state.wizardStep + 1);
}

export function wizardPrev() {
  if (state.wizardStep > 0) setWizardStep(state.wizardStep - 1);
}

export async function wizardRefreshFiles() {
  try {
    const res = await fetch('/api/profile/status');
    const data = await res.json();
    document.getElementById('wizard-file-count').textContent = data.file_count || 0;
  } catch { }
}

function buildWizardSummary() {
  const first = document.getElementById('wiz-first-name').value;
  const last = document.getElementById('wiz-last-name').value;
  const name = (first + ' ' + last).trim() || t('wizard.not_set');
  const email = document.getElementById('wiz-email').value || t('wizard.not_set');
  const city = document.getElementById('wiz-city').value;
  const st = document.getElementById('wiz-state').value;
  const loc = [city, st].filter(Boolean).join(', ') || t('wizard.not_set');
  const titles = state.tagInputs['wiz-titles-tags'] || [];
  const locations = state.tagInputs['wiz-locations-tags'] || [];
  const remote = document.getElementById('wiz-remote').checked;
  const levels = [...document.querySelectorAll('.wiz-exp-level:checked')].map(c => c.value);
  const hasResume = !!state.wizardData.resume_file;

  document.getElementById('wizard-summary').innerHTML = `
    <div><strong>${t('wizard.summary_name')}</strong> ${escHtml(name)}</div>
    <div><strong>${t('wizard.summary_email')}</strong> ${escHtml(email)}</div>
    <div><strong>${t('wizard.summary_location')}</strong> ${escHtml(loc)}</div>
    <div><strong>${t('wizard.summary_titles')}</strong> ${titles.length ? escHtml(titles.join(', ')) : t('wizard.none')}</div>
    <div><strong>${t('wizard.summary_locations')}</strong> ${locations.length ? escHtml(locations.join(', ')) : t('wizard.none')}</div>
    <div><strong>${t('wizard.summary_remote')}</strong> ${remote ? t('wizard.yes') : t('wizard.no')}</div>
    <div><strong>${t('wizard.summary_experience')}</strong> ${levels.length ? levels.join(', ') : t('wizard.none')}</div>
    <div><strong>${t('wizard.summary_resume')}</strong> ${hasResume ? t('wizard.uploaded') : t('wizard.skipped')}</div>
  `;
}

function _collectWizardScreeningAnswers() {
  const ans = {};
  const fields = {
    'wiz-work-authorization': 'work_authorization',
    'wiz-visa-sponsorship':   'visa_sponsorship',
    'wiz-years-experience':   'years_experience',
    'wiz-desired-salary':     'desired_salary',
    'wiz-willing-relocate':   'willing_to_relocate',
    'wiz-start-date':         'start_date',
  };
  for (const [id, key] of Object.entries(fields)) {
    const el = document.getElementById(id);
    if (el && el.value) ans[key] = el.value;
  }
  return ans;
}

export async function wizardFinish() {
  const config = {
    profile: {
      first_name:         document.getElementById('wiz-first-name').value,
      last_name:          document.getElementById('wiz-last-name').value,
      email:              document.getElementById('wiz-email').value,
      phone_country_code: document.getElementById('wiz-phone-code').value || '+1',
      phone:              document.getElementById('wiz-phone').value,
      address_line1:      document.getElementById('wiz-address1').value,
      address_line2:      document.getElementById('wiz-address2').value,
      city:               document.getElementById('wiz-city').value,
      state:              document.getElementById('wiz-state').value,
      zip_code:           document.getElementById('wiz-zip').value,
      country:            document.getElementById('wiz-country').value || 'United States',
      bio:                document.getElementById('wiz-bio').value,
      linkedin_url:       document.getElementById('wiz-linkedin').value,
      portfolio_url:      document.getElementById('wiz-portfolio').value,
      screening_answers:  _collectWizardScreeningAnswers(),
    },
    search_criteria: {
      job_titles:        state.tagInputs['wiz-titles-tags'] || [],
      locations:         state.tagInputs['wiz-locations-tags'] || [],
      remote_only:       document.getElementById('wiz-remote').checked,
      salary_min:        parseInt(document.getElementById('wiz-salary').value) || null,
      keywords_include:  state.tagInputs['wiz-include-tags'] || [],
      keywords_exclude:  state.tagInputs['wiz-exclude-tags'] || [],
      experience_levels: [...document.querySelectorAll('.wiz-exp-level:checked')].map(c => c.value),
    },
  };

  if (state.wizardData.llm) {
    config.llm = state.wizardData.llm;
  }

  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
  } catch (e) {
    console.warn('Could not save config:', e);
  }

  // Upload resume if present
  if (state.wizardData.resume_file) {
    try {
      const fd = new FormData();
      fd.append('file', state.wizardData.resume_file);
      await fetch('/api/config/default-resume', { method: 'POST', body: fd });
    } catch (e) {
      console.warn('Could not upload resume:', e);
    }
  }

  // Save imported experience text as an experience file
  if (state.wizardData.imported_experience_text) {
    try {
      await fetch('/api/profile/experiences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'imported_profile.txt',
          content: state.wizardData.imported_experience_text,
        }),
      });
    } catch (e) {
      console.warn('Could not save imported experience file:', e);
    }
  }

  showApp();
}
