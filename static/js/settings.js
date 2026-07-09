/* ═══════════════════════════════════════════════════════════════
   SETTINGS
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { setTags } from './tag-input.js';
import { checkLoginSessions, loadBrowserInfo } from './login.js';
import { t, getLocale, setLocale } from './i18n.js';
import { refreshHelp } from './help.js';
import { updateAIIndicators } from './ai-status.js';
import {
  populateFormFromExtracted,
  fetchCvImport,
  fetchLinkedInImport,
  fetchLinkedInZipImport,
  renderImportPreview,
  setImportStatus,
} from './profile-import.js';
import { showLoading, hideLoading, setButtonLoading } from './loading.js';

const LLM_DEFAULT_MODELS = {
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
  google: 'gemini-2.0-flash',
  deepseek: 'deepseek-chat',
  groq: 'llama-3.3-70b-versatile',
  openrouter: 'meta-llama/llama-3.3-70b-instruct:free',
  ollama: 'llama3.2',
};

const LLM_PROVIDER_LABELS = {
  anthropic: 'Anthropic (Claude)',
  openai: 'OpenAI (GPT)',
  google: 'Google (Gemini)',
  deepseek: 'DeepSeek',
  groq: 'Groq',
  openrouter: 'OpenRouter',
  ollama: 'Ollama (local)',
};

let llmProviders = [];
let llmActiveId = '';
let editingLlmId = null;

/** Human-readable names for locale codes (FR-134). */
const LOCALE_NAMES = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  pt: 'Português (Brasil)',
  ja: '日本語',
  zh: '中文',
  ko: '한국어',
};

export async function loadSettings() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    const p = cfg.profile || {};
    const pr = cfg.search_criteria || {};

    document.getElementById('set-first-name').value = p.first_name || '';
    document.getElementById('set-last-name').value  = p.last_name || '';
    document.getElementById('set-email').value      = p.email || '';
    document.getElementById('set-phone-code').value = p.phone_country_code || '+1';
    document.getElementById('set-phone').value      = p.phone || '';
    document.getElementById('set-address1').value   = p.address_line1 || '';
    document.getElementById('set-address2').value   = p.address_line2 || '';
    document.getElementById('set-city').value       = p.city || '';
    document.getElementById('set-state').value      = p.state || '';
    document.getElementById('set-zip').value        = p.zip_code || '';
    document.getElementById('set-country').value    = p.country || 'United States';
    document.getElementById('set-bio').value        = p.bio || '';
    document.getElementById('set-linkedin').value   = p.linkedin_url || '';
    document.getElementById('set-portfolio').value  = p.portfolio_url || '';
    _loadSpokenLanguages(p.spoken_languages);
    _loadJobLanguages((cfg.search_criteria || {}).job_languages);

    // Screening answers
    const sa = p.screening_answers || {};
    document.getElementById('set-work-authorization').value = sa.work_authorization || '';
    document.getElementById('set-visa-sponsorship').value   = sa.visa_sponsorship || '';
    document.getElementById('set-years-experience').value   = sa.years_experience || '';
    document.getElementById('set-desired-salary').value     = sa.desired_salary || '';
    document.getElementById('set-willing-relocate').value   = sa.willing_to_relocate || '';
    document.getElementById('set-start-date').value         = sa.start_date || '';
    document.getElementById('set-eeo-gender').value         = sa.gender || '';
    document.getElementById('set-eeo-ethnicity').value      = sa.ethnicity || '';
    document.getElementById('set-eeo-veteran').value        = sa.veteran_status || '';
    document.getElementById('set-eeo-disability').value     = sa.disability_status || '';

    // LLM config
    const llm = cfg.llm || {};
    llmProviders = Array.isArray(llm.providers) ? llm.providers.map(p => ({ ...p })) : [];
    llmActiveId = llm.active_id || (llmProviders[0] && llmProviders[0].id) || '';
    editingLlmId = null;
    _renderLLMProviders();
    _clearLLMForm();
    onLLMProviderChange();
    document.getElementById('set-ollama-fallback').checked = !!llm.ollama_fallback_enabled;
    document.getElementById('set-ollama-model').value = llm.ollama_model || '';

    const sync = cfg.sync || {};
    document.getElementById('set-sync-url').value = sync.sync_server_url || '';
    document.getElementById('set-sync-token').value = sync.sync_token || '';

    setTags('set-titles-tags',    pr.job_titles || []);
    setTags('set-locations-tags', pr.locations || []);
    document.getElementById('set-remote').checked = !!pr.remote_only;
    document.getElementById('set-salary').value   = pr.salary_min || '';
    setTags('set-include-tags', pr.keywords_include || []);
    setTags('set-exclude-tags', pr.keywords_exclude || []);

    document.querySelectorAll('.set-exp-level').forEach(cb => {
      cb.checked = (pr.experience_levels || []).includes(cb.value);
    });

    // Schedule
    const sched = (cfg.bot || {}).schedule || {};
    document.getElementById('set-schedule-enabled').checked = !!sched.enabled;
    const schedDays = sched.days_of_week || ['mon','tue','wed','thu','fri'];
    document.querySelectorAll('.set-schedule-day').forEach(cb => {
      cb.checked = schedDays.includes(cb.value);
    });
    document.getElementById('set-schedule-start').value = sched.start_time || '09:00';
    document.getElementById('set-schedule-end').value = sched.end_time || '17:00';
    updateScheduleUI();
    checkLoginSessions();
    loadBrowserInfo();
    _loadLocaleDropdown();
    initProfileImportButtons();
  } catch { }
}

/** Populate locale dropdown from GET /api/locales (FR-131). */
async function _loadLocaleDropdown() {
  const sel = document.getElementById('set-locale');
  if (!sel) return;
  try {
    const res = await fetch('/api/locales');
    const data = await res.json();
    sel.innerHTML = '';
    for (const code of data.available || []) {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = LOCALE_NAMES[code] || code;
      sel.appendChild(opt);
    }
    sel.value = getLocale();
  } catch {
    // If endpoint unavailable, show current locale only
    sel.innerHTML = `<option value="${getLocale()}">${LOCALE_NAMES[getLocale()] || getLocale()}</option>`;
  }
}

/** Handle locale dropdown change (FR-131, FR-132, FR-133). */
export async function onLocaleChange() {
  const sel = document.getElementById('set-locale');
  if (!sel) return;
  await setLocale(sel.value);
  refreshHelp();
}

function _collectScreeningAnswers() {
  const ans = {};
  const fields = {
    'set-work-authorization': 'work_authorization',
    'set-visa-sponsorship':   'visa_sponsorship',
    'set-years-experience':   'years_experience',
    'set-desired-salary':     'desired_salary',
    'set-willing-relocate':   'willing_to_relocate',
    'set-start-date':         'start_date',
    'set-eeo-gender':         'gender',
    'set-eeo-ethnicity':      'ethnicity',
    'set-eeo-veteran':        'veteran_status',
    'set-eeo-disability':     'disability_status',
  };
  for (const [id, key] of Object.entries(fields)) {
    const val = document.getElementById(id).value;
    if (val) ans[key] = val;
  }
  const langLine = _formatLanguagesLine(_collectSpokenLanguages());
  if (langLine) ans.languages = langLine;
  return ans;
}

const SPOKEN_LANG_IDS = [
  { code: 'pt', check: 'set-spoken-pt', level: 'set-level-pt' },
  { code: 'en', check: 'set-spoken-en', level: 'set-level-en' },
  { code: 'es', check: 'set-spoken-es', level: 'set-level-es' },
];

function _collectSpokenLanguages() {
  const out = [];
  for (const { code, check, level } of SPOKEN_LANG_IDS) {
    const cb = document.getElementById(check);
    if (cb && cb.checked) {
      out.push({ code, level: document.getElementById(level)?.value || 'fluent' });
    }
  }
  return out;
}

function _collectJobLanguages() {
  return [...document.querySelectorAll('.set-job-lang:checked')].map(c => c.value);
}

function _loadSpokenLanguages(spoken) {
  const map = {};
  for (const entry of spoken || []) map[entry.code] = entry.level || 'fluent';
  for (const { code, check, level } of SPOKEN_LANG_IDS) {
    const cb = document.getElementById(check);
    const sel = document.getElementById(level);
    if (!cb || !sel) continue;
    if (map[code]) {
      cb.checked = true;
      sel.value = map[code];
    } else {
      cb.checked = false;
    }
  }
}

function _loadJobLanguages(codes) {
  const set = new Set(codes || ['pt', 'en', 'es']);
  document.querySelectorAll('.set-job-lang').forEach(cb => {
    cb.checked = set.has(cb.value);
  });
}

function _formatLanguagesLine(spoken) {
  const names = { pt: 'Português', en: 'English', es: 'Español' };
  const levels = {
    native: 'Native', fluent: 'Fluent', intermediate: 'Intermediate', basic: 'Basic',
  };
  return spoken.map(s => `${names[s.code] || s.code} (${levels[s.level] || s.level})`).join(', ');
}

export async function saveSettings() {
  const saveBtn = document.querySelector('[onclick="saveSettings()"]');
  const config = {
    profile: {
      first_name:         document.getElementById('set-first-name').value,
      last_name:          document.getElementById('set-last-name').value,
      email:              document.getElementById('set-email').value,
      phone_country_code: document.getElementById('set-phone-code').value || '+1',
      phone:              document.getElementById('set-phone').value,
      address_line1:      document.getElementById('set-address1').value,
      address_line2:      document.getElementById('set-address2').value,
      city:               document.getElementById('set-city').value,
      state:              document.getElementById('set-state').value,
      zip_code:           document.getElementById('set-zip').value,
      country:            document.getElementById('set-country').value || 'United States',
      bio:                document.getElementById('set-bio').value,
      linkedin_url:       document.getElementById('set-linkedin').value,
      portfolio_url:      document.getElementById('set-portfolio').value,
      spoken_languages:   _collectSpokenLanguages(),
      screening_answers:  _collectScreeningAnswers(),
    },
    llm: {
      provider: llmActiveId ? (llmProviders.find(p => p.id === llmActiveId)?.provider || '') : document.getElementById('set-llm-provider').value,
      api_key:  llmActiveId ? (llmProviders.find(p => p.id === llmActiveId)?.api_key || '') : document.getElementById('set-llm-api-key').value,
      model:    llmActiveId ? (llmProviders.find(p => p.id === llmActiveId)?.model || '') : document.getElementById('set-llm-model').value,
      providers: llmProviders,
      active_id: llmActiveId,
      ollama_fallback_enabled: document.getElementById('set-ollama-fallback').checked,
      ollama_model: document.getElementById('set-ollama-model').value.trim(),
    },
    sync: {
      sync_server_url: document.getElementById('set-sync-url').value.trim(),
      sync_token: document.getElementById('set-sync-token').value.trim(),
    },
    search_criteria: {
      job_titles:        state.tagInputs['set-titles-tags'] || [],
      locations:         state.tagInputs['set-locations-tags'] || [],
      remote_only:       document.getElementById('set-remote').checked,
      salary_min:        parseInt(document.getElementById('set-salary').value) || null,
      keywords_include:  state.tagInputs['set-include-tags'] || [],
      keywords_exclude:  state.tagInputs['set-exclude-tags'] || [],
      experience_levels: [...document.querySelectorAll('.set-exp-level:checked')].map(c => c.value),
      job_languages:     _collectJobLanguages(),
    },
  };

  setButtonLoading(saveBtn, true);
  showLoading(t('loading.saving_settings'));
  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });

    // Save schedule separately via dedicated endpoint
    const schedData = {
      enabled:      document.getElementById('set-schedule-enabled').checked,
      days_of_week: [...document.querySelectorAll('.set-schedule-day:checked')].map(c => c.value),
      start_time:   document.getElementById('set-schedule-start').value,
      end_time:     document.getElementById('set-schedule-end').value,
    };
    await fetch('/api/bot/schedule', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(schedData),
    });
    updateScheduleUI();

    // Refresh AI availability indicator after config change
    try {
      const statusRes = await fetch('/api/setup/status');
      const statusData = await statusRes.json();
      state.aiAvailable = !!statusData.ai_available;
      updateAIIndicators();
      const banner = document.getElementById('ai-warning-banner');
      if (banner) banner.classList.toggle('hidden', state.aiAvailable);
    } catch { /* non-critical */ }

    const msg = document.getElementById('settings-saved-msg');
    msg.classList.remove('hidden');
    setTimeout(() => msg.classList.add('hidden'), 2500);
  } catch {
    alert(t('settings.save_error'));
  } finally {
    hideLoading();
    setButtonLoading(saveBtn, false);
  }
}

export function updateScheduleUI() {
  const enabled = document.getElementById('set-schedule-enabled').checked;
  const badge = document.getElementById('schedule-status-badge');
  if (enabled) {
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

export async function changeApplyMode(mode) {
  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot: { apply_mode: mode } }),
    });
  } catch (e) {
    console.warn('Could not save apply_mode:', e);
  }
}

export function initBotToggles() {
  const adaptive = document.getElementById('set-adaptive-resume');
  const coverLetter = document.getElementById('set-cover-letter');
  if (adaptive) {
    adaptive.addEventListener('change', () => {
      fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_reuse: { enabled: adaptive.checked } }),
      }).catch(e => console.warn('Could not save adaptive resume:', e));
    });
  }
  if (coverLetter) {
    coverLetter.addEventListener('change', () => {
      fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot: { cover_letter_enabled: coverLetter.checked } }),
      }).catch(e => console.warn('Could not save cover letter:', e));
    });
  }
}

export async function loadApplyMode() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    const mode = (cfg.bot && cfg.bot.apply_mode) || 'review';
    const sel = document.getElementById('apply-mode-select');
    if (sel) sel.value = mode;

    // Load bot toggles on dashboard
    const adaptive = document.getElementById('set-adaptive-resume');
    const coverLetter = document.getElementById('set-cover-letter');
    if (adaptive) adaptive.checked = (cfg.resume_reuse || {}).enabled !== false;
    if (coverLetter) coverLetter.checked = (cfg.bot || {}).cover_letter_enabled !== false;
  } catch { }
}

// ---------------------------------------------------------------------------
// Default Resume
// ---------------------------------------------------------------------------

export async function uploadDefaultResume(input) {
  const file = input.files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  try {
    const res = await fetch('/api/config/default-resume', { method: 'POST', body: form });
    const data = await res.json();
    if (data.success) {
      _updateDefaultResumeUI(data.filename);
    } else {
      alert(data.error || t('settings.upload_failed'));
    }
  } catch (e) {
    console.warn('Default resume upload failed:', e);
  }
  input.value = '';
}

export async function removeDefaultResume() {
  try {
    await fetch('/api/config/default-resume', { method: 'DELETE' });
    _updateDefaultResumeUI(null);
  } catch (e) {
    console.warn('Default resume remove failed:', e);
  }
}

export async function loadDefaultResume() {
  try {
    const res = await fetch('/api/config/default-resume');
    const data = await res.json();
    _updateDefaultResumeUI(data.filename);
  } catch { }
}

function _updateDefaultResumeUI(filename) {
  const nameEl = document.getElementById('default-resume-name');
  const removeBtn = document.getElementById('btn-remove-default-resume');
  if (nameEl) nameEl.textContent = filename || 'None';
  if (removeBtn) removeBtn.classList.toggle('hidden', !filename);
}

export function onLLMProviderChange() {
  const provider = document.getElementById('set-llm-provider').value;
  const modelInput = document.getElementById('set-llm-model');
  if (provider && !modelInput.value) {
    modelInput.placeholder = LLM_DEFAULT_MODELS[provider] || '';
  }
  document.getElementById('llm-key-status').textContent = '';
}

function _defaultLLMLabel(provider) {
  return LLM_PROVIDER_LABELS[provider] || provider || t('settings.ai_provider_default_label');
}

function _clearLLMForm() {
  document.getElementById('set-llm-label').value = '';
  document.getElementById('set-llm-provider').value = '';
  document.getElementById('set-llm-model').value = '';
  document.getElementById('set-llm-api-key').value = '';
  document.getElementById('llm-key-status').textContent = '';
  editingLlmId = null;
  const addBtn = document.getElementById('btn-add-llm-provider');
  if (addBtn) addBtn.textContent = t('settings.add_provider');
}

function _renderLLMProviders() {
  const list = document.getElementById('llm-providers-list');
  if (!list) return;

  if (!llmProviders.length) {
    list.innerHTML = `<p class="llm-providers-empty" style="font-size:.85rem;color:var(--text-dim);margin:0 0 12px;">${escHtml(t('settings.no_providers_yet'))}</p>`;
    return;
  }

  list.innerHTML = llmProviders.map(entry => {
    const active = entry.id === llmActiveId;
    const providerLabel = LLM_PROVIDER_LABELS[entry.provider] || entry.provider;
    const model = entry.model || LLM_DEFAULT_MODELS[entry.provider] || '';
  return `
      <div class="llm-provider-card${active ? ' llm-provider-card-active' : ''}" data-id="${escAttr(entry.id)}">
        <div class="llm-provider-card-main">
          <strong>${escHtml(entry.label || providerLabel)}</strong>
          ${active ? `<span class="status-badge ok" style="font-size:.75rem;margin-left:8px;">${escHtml(t('settings.active_provider'))}</span>` : ''}
          <div style="font-size:.8rem;color:var(--text-dim);margin-top:4px;">
            ${escHtml(providerLabel)}${model ? ` · ${escHtml(model)}` : ''}
          </div>
        </div>
        <div class="llm-provider-card-actions">
          ${active ? '' : `<button type="button" class="btn btn-ghost btn-sm" onclick="setActiveLLMProvider('${escAttr(entry.id)}')">${escHtml(t('settings.use_provider'))}</button>`}
          <button type="button" class="btn btn-ghost btn-sm" onclick="editLLMProvider('${escAttr(entry.id)}')">${escHtml(t('button.edit'))}</button>
          <button type="button" class="btn btn-ghost btn-sm" onclick="removeLLMProvider('${escAttr(entry.id)}')">${escHtml(t('button.delete'))}</button>
        </div>
      </div>`;
  }).join('');
}

function escHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escAttr(value) {
  return escHtml(value).replace(/'/g, '&#39;');
}

export function addLLMProvider() {
  const label = document.getElementById('set-llm-label').value.trim();
  const provider = document.getElementById('set-llm-provider').value;
  const model = document.getElementById('set-llm-model').value.trim();
  const apiKey = document.getElementById('set-llm-api-key').value.trim();
  const status = document.getElementById('llm-key-status');

  if (!provider) {
    status.textContent = t('settings.select_provider');
    status.style.color = '#f87171';
    return;
  }
  if (provider !== 'ollama' && !apiKey) {
    status.textContent = t('settings.enter_api_key');
    status.style.color = '#f87171';
    return;
  }

  const entry = {
    id: editingLlmId || crypto.randomUUID(),
    label: label || _defaultLLMLabel(provider),
    provider,
    model,
    api_key: apiKey,
  };

  const existingIdx = llmProviders.findIndex(p => p.id === entry.id);
  if (existingIdx >= 0) {
    llmProviders[existingIdx] = entry;
  } else {
    llmProviders.push(entry);
    if (!llmActiveId) llmActiveId = entry.id;
  }

  _renderLLMProviders();
  _clearLLMForm();
  status.textContent = t('settings.provider_added');
  status.style.color = '#34d399';
}

export function removeLLMProvider(id) {
  llmProviders = llmProviders.filter(p => p.id !== id);
  if (llmActiveId === id) {
    llmActiveId = llmProviders[0]?.id || '';
  }
  if (editingLlmId === id) _clearLLMForm();
  _renderLLMProviders();
}

export function setActiveLLMProvider(id) {
  llmActiveId = id;
  _renderLLMProviders();
}

export function editLLMProvider(id) {
  const entry = llmProviders.find(p => p.id === id);
  if (!entry) return;
  editingLlmId = id;
  document.getElementById('set-llm-label').value = entry.label || '';
  document.getElementById('set-llm-provider').value = entry.provider || '';
  document.getElementById('set-llm-model').value = entry.model || '';
  document.getElementById('set-llm-api-key').value = entry.api_key || '';
  document.getElementById('btn-add-llm-provider').textContent = t('settings.update_provider');
  onLLMProviderChange();
}

function _validationMessage(data) {
  if (data.message) return data.message;
  if (data.error_code === 'insufficient_balance') return t('settings.key_insufficient_balance');
  if (data.error_code === 'invalid_key') return t('settings.key_invalid');
  return t('settings.key_invalid');
}

export async function validateLLMKey() {
  const provider = document.getElementById('set-llm-provider').value;
  const apiKey   = document.getElementById('set-llm-api-key').value;
  const model    = document.getElementById('set-llm-model').value;
  const status   = document.getElementById('llm-key-status');
  const btn      = document.getElementById('btn-validate-key');

  if (!provider) { status.textContent = t('settings.select_provider'); status.style.color = '#f87171'; return; }
  if (provider !== 'ollama' && !apiKey) {
    status.textContent = t('settings.enter_api_key');
    status.style.color = '#f87171';
    return;
  }

  btn.disabled = true;
  btn.textContent = t('settings.validating');
  status.textContent = '';

  try {
    const res = await fetch('/api/ai/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        api_key: apiKey || 'ollama',
        model: model || undefined,
      }),
    });
    const data = await res.json();
    if (data.valid) {
      status.textContent = data.message || t('settings.key_valid');
      status.style.color = '#34d399';
      try {
        await fetch('/api/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            llm: {
              provider,
              api_key: apiKey,
              model: model || '',
              providers: llmProviders,
              active_id: llmActiveId,
            },
          }),
        });
        state.aiAvailable = true;
        updateAIIndicators();
        const banner = document.getElementById('ai-warning-banner');
        if (banner) banner.classList.toggle('hidden', true);
      } catch { /* save failed silently — user can still use main Save */ }
    } else {
      status.textContent = _validationMessage(data);
      status.style.color = '#f87171';
    }
  } catch {
    status.textContent = t('settings.validation_failed');
    status.style.color = '#f87171';
  } finally {
    btn.disabled = false;
    btn.textContent = t('button.validate');
  }
}

// ---------------------------------------------------------------------------
// Profile import (CV / LinkedIn)
// ---------------------------------------------------------------------------

const PENDING_IMPORT_KEY = 'autoapply_pending_profile_import';
let pendingProfileImport = null;

function _savePendingImport() {
  if (!pendingProfileImport) {
    sessionStorage.removeItem(PENDING_IMPORT_KEY);
    return;
  }
  try {
    sessionStorage.setItem(PENDING_IMPORT_KEY, JSON.stringify(pendingProfileImport));
  } catch { }
}

function _restorePendingImport() {
  if (pendingProfileImport) return pendingProfileImport;
  try {
    const raw = sessionStorage.getItem(PENDING_IMPORT_KEY);
    if (!raw) return null;
    pendingProfileImport = JSON.parse(raw);
    return pendingProfileImport;
  } catch {
    return null;
  }
}

function _scrollToProfileFields() {
  document.getElementById('set-first-name')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function _applyExtractedToSettingsForm(extracted) {
  populateFormFromExtracted(extracted, 'set');
  _scrollToProfileFields();
}

export async function importFromCV(input) {
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;

  setImportStatus('profile-import-status', t('settings.importing'));
  pendingProfileImport = null;
  document.getElementById('profile-import-preview')?.classList.add('hidden');
  document.getElementById('profile-import-actions')?.classList.add('hidden');

  try {
    const data = await fetchCvImport(file, null, true);
    await _finishSettingsImport(data, data.source || 'cv');
  } catch (e) {
    setImportStatus('profile-import-status', e.message || t('settings.import_failed'), true);
  }
}

export async function importFromLinkedIn() {
  if (!state.aiAvailable) {
    setImportStatus('profile-import-status', t('wizard.import_ai_required'), true);
    return;
  }

  try {
    const sessionsRes = await fetch('/api/login/sessions');
    const sessions = sessionsRes.ok ? await sessionsRes.json() : {};
    if (!sessions.linkedin) {
      setImportStatus('profile-import-status', t('settings.linkedin_connect_first'), true);
      return;
    }
  } catch {
    setImportStatus('profile-import-status', t('settings.linkedin_connect_first'), true);
    return;
  }

  const btn = document.getElementById('btn-import-linkedin');
  if (btn) { btn.disabled = true; btn.textContent = t('settings.importing'); }

  setImportStatus('profile-import-status', t('settings.linkedin_importing'));
  pendingProfileImport = null;

  try {
    const data = await fetchLinkedInImport(null, true);
    await _finishSettingsImport(data, data.source || 'linkedin');
  } catch (e) {
    setImportStatus('profile-import-status', e.message || t('settings.import_failed'), true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = t('settings.import_from_linkedin'); }
  }
}

export async function importLinkedInZip(input) {
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;

  setImportStatus('profile-import-status', t('settings.importing'));
  pendingProfileImport = null;

  try {
    const data = await fetchLinkedInZipImport(file);
    await _finishSettingsImport(data, data.source || 'linkedin_zip');
  } catch (e) {
    setImportStatus('profile-import-status', e.message || t('settings.import_failed'), true);
  }
}

async function _finishSettingsImport(data, source) {
  if (!data?.extracted) {
    setImportStatus('profile-import-status', t('settings.import_failed'), true);
    return;
  }
  pendingProfileImport = { extracted: data.extracted, source };
  _savePendingImport();
  renderImportPreview(data.extracted, 'profile-import-preview', 'profile-import-actions');
  _applyExtractedToSettingsForm(data.extracted);
  setImportStatus('profile-import-status', t('settings.import_applied'));
}

export async function applyImportedProfile() {
  if (!pendingProfileImport) {
    _restorePendingImport();
  }
  if (!pendingProfileImport?.extracted) {
    setImportStatus('profile-import-status', t('settings.import_nothing_pending'), true);
    return;
  }

  setImportStatus('profile-import-status', t('settings.applying_import'));
  try {
    const res = await fetch('/api/profile/apply-import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pendingProfileImport),
    });
    const data = await res.json();
    if (!res.ok) {
      setImportStatus('profile-import-status', data.error || t('settings.import_failed'), true);
      return;
    }
    _applyExtractedToSettingsForm(pendingProfileImport.extracted);
    pendingProfileImport = null;
    _savePendingImport();
    document.getElementById('profile-import-preview')?.classList.add('hidden');
    document.getElementById('profile-import-actions')?.classList.add('hidden');
    if (data.experience_file) {
      setImportStatus('profile-import-status', t('settings.import_applied_with_file', { file: data.experience_file }));
    } else {
      setImportStatus('profile-import-status', t('settings.import_applied'));
    }
  } catch {
    setImportStatus('profile-import-status', t('settings.import_failed'), true);
  }
}

export function clearProfileImport() {
  pendingProfileImport = null;
  _savePendingImport();
  document.getElementById('profile-import-preview')?.classList.add('hidden');
  document.getElementById('profile-import-actions')?.classList.add('hidden');
  setImportStatus('profile-import-status', '');
}

/** Wire import/apply buttons via JS (backup for inline onclick). */
export function initProfileImportButtons() {
  const applyBtn = document.querySelector('#profile-import-actions button[data-i18n="settings.apply_import"]')
    || document.querySelector('#profile-import-actions .btn-primary');
  if (applyBtn && !applyBtn.dataset.importBound) {
    applyBtn.dataset.importBound = '1';
    applyBtn.addEventListener('click', (e) => {
      e.preventDefault();
      applyImportedProfile();
    });
  }
  const linkedinBtn = document.getElementById('btn-import-linkedin');
  if (linkedinBtn && !linkedinBtn.dataset.importBound) {
    linkedinBtn.dataset.importBound = '1';
    linkedinBtn.addEventListener('click', (e) => {
      e.preventDefault();
      importFromLinkedIn();
    });
  }
  _restorePendingImport();
  if (pendingProfileImport?.extracted) {
    renderImportPreview(
      pendingProfileImport.extracted,
      'profile-import-preview',
      'profile-import-actions',
    );
  }
}

export async function testSyncConnection() {
  const status = document.getElementById('sync-import-status');
  const btn = document.getElementById('btn-test-sync');
  setButtonLoading(btn, true);
  status.textContent = t('settings.sync_testing');
  status.style.color = 'var(--text-dim)';
  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sync: {
          sync_server_url: document.getElementById('set-sync-url').value.trim(),
          sync_token: document.getElementById('set-sync-token').value.trim(),
        },
      }),
    });
    const res = await fetch('/api/sync/test', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || t('settings.sync_failed'));
    status.textContent = t('settings.sync_ok');
    status.style.color = '#34d399';
  } catch (e) {
    status.textContent = e.message || t('settings.sync_failed');
    status.style.color = '#f87171';
  } finally {
    setButtonLoading(btn, false);
  }
}

export async function importJobsFromServer() {
  const status = document.getElementById('sync-import-status');
  const btn = document.getElementById('btn-import-jobs');
  setButtonLoading(btn, true);
  showLoading(t('settings.sync_importing'));
  status.textContent = '';
  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sync: {
          sync_server_url: document.getElementById('set-sync-url').value.trim(),
          sync_token: document.getElementById('set-sync-token').value.trim(),
        },
      }),
    });
    const res = await fetch('/api/sync/import', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || t('settings.sync_failed'));
    status.textContent = t('settings.sync_import_result', {
      imported: data.imported || 0,
      skipped: data.skipped || 0,
    });
    status.style.color = '#34d399';
  } catch (e) {
    status.textContent = e.message || t('settings.sync_failed');
    status.style.color = '#f87171';
  } finally {
    hideLoading();
    setButtonLoading(btn, false);
  }
}
