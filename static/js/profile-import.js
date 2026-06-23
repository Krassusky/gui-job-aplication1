/* ═══════════════════════════════════════════════════════════════
   PROFILE IMPORT — shared CV / LinkedIn extraction helpers
   ═══════════════════════════════════════════════════════════════ */
import { setTags } from './tag-input.js';
import { escHtml } from './helpers.js';
import { t } from './i18n.js';

/**
 * Populate profile + search form fields from extracted data.
 * @param {object} extracted - API extraction result
 * @param {'wiz'|'set'} prefix - wizard or settings field prefix
 */
export function populateFormFromExtracted(extracted, prefix = 'set') {
  const p = extracted.profile || {};
  const sc = extracted.search_criteria || {};
  const sa = extracted.screening_answers || {};

  const setVal = (suffix, val) => {
    const el = document.getElementById(`${prefix}-${suffix}`);
    if (el && val) el.value = val;
  };

  setVal('first-name', p.first_name);
  setVal('last-name', p.last_name);
  setVal('email', p.email);
  setVal('phone-code', p.phone_country_code);
  setVal('phone', p.phone);
  setVal('address1', p.address_line1);
  setVal('address2', p.address_line2);
  setVal('city', p.city);
  setVal('state', p.state);
  setVal('zip', p.zip_code);
  setVal('country', p.country);
  setVal('bio', p.bio);
  setVal('linkedin', p.linkedin_url);
  setVal('portfolio', p.portfolio_url);
  setVal('years-experience', sa.years_experience);

  if (sc.job_titles?.length) {
    setTags(`${prefix}-titles-tags`, sc.job_titles);
  }
  if (sc.keywords_include?.length) {
    setTags(`${prefix}-include-tags`, sc.keywords_include);
  }
  if (sc.keywords_exclude?.length) {
    setTags(`${prefix}-exclude-tags`, sc.keywords_exclude);
  }
  if (sc.experience_levels?.length) {
    document.querySelectorAll(`.${prefix}-exp-level`).forEach(cb => {
      cb.checked = sc.experience_levels.includes(cb.value);
    });
  }

  return extracted.experience_text || '';
}

export async function fetchCvImport(file, llm = null, apply = false) {
  const form = new FormData();
  form.append('file', file);
  if (llm?.provider && llm?.api_key) {
    form.append('provider', llm.provider);
    form.append('api_key', llm.api_key);
    if (llm.model) form.append('model', llm.model);
  }
  const qs = apply ? '?apply=true' : '';
  const res = await fetch(`/api/profile/import-cv${qs}`, { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || t('settings.import_failed'));
  }
  return data;
}

export async function fetchLinkedInImport(llm = null, apply = false) {
  const res = await fetch('/api/profile/import-linkedin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apply, llm: llm || undefined }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || t('settings.import_failed'));
  }
  return data;
}

export async function fetchLinkedInZipImport(file, llm = null) {
  const form = new FormData();
  form.append('file', file);
  if (llm?.provider && llm?.api_key) {
    form.append('provider', llm.provider);
    form.append('api_key', llm.api_key);
    if (llm.model) form.append('model', llm.model);
  }
  const res = await fetch('/api/profile/import-linkedin-zip', { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || t('settings.import_failed'));
  }
  return data;
}

export function renderImportPreview(extracted, previewId, actionsId) {
  const preview = document.getElementById(previewId);
  const actions = actionsId ? document.getElementById(actionsId) : null;
  if (!preview) return;

  const p = extracted.profile || {};
  const sc = extracted.search_criteria || {};
  const lines = [
    p.first_name || p.last_name
      ? `<strong>${escHtml([p.first_name, p.last_name].filter(Boolean).join(' '))}</strong>`
      : '',
    p.email ? escHtml(p.email) : '',
    p.phone ? escHtml(`${p.phone_country_code || ''}${p.phone}`) : '',
    p.city || p.country ? escHtml([p.city, p.state, p.country].filter(Boolean).join(', ')) : '',
    p.bio ? escHtml(p.bio.slice(0, 180) + (p.bio.length > 180 ? '…' : '')) : '',
    sc.job_titles?.length
      ? `<em>${escHtml(t('settings.preview_job_titles'))}:</em> ${escHtml(sc.job_titles.slice(0, 5).join(', '))}`
      : '',
    sc.keywords_include?.length
      ? `<em>${escHtml(t('settings.preview_skills'))}:</em> ${escHtml(sc.keywords_include.slice(0, 8).join(', '))}`
      : '',
  ].filter(Boolean);

  preview.innerHTML = lines.join('<br>');
  preview.classList.toggle('hidden', lines.length === 0);
  if (actions) actions.classList.toggle('hidden', lines.length === 0);
}

export function setImportStatus(statusId, message, isError = false) {
  const el = document.getElementById(statusId);
  if (!el) return;
  el.textContent = message;
  el.style.color = isError ? '#f87171' : (message ? '#34d399' : '');
}
