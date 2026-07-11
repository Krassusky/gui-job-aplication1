"""Self-contained HTML dashboard for the Job Hunter sync server.

Includes login gate, Start/Stop + thermal view, and editable shared settings
(profile / search / bot filters) persisted to ~/.autoapply/config.json.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Hunter Dashboard</title>
<style>
  :root {
    --bg: #0f1923; --card: #1a2736; --border: #2d3f54;
    --text: #e2e8f0; --dim: #94a3b8; --accent: #60a5fa;
    --ok: #34d399; --warn: #fbbf24; --danger: #f87171; --muted: #64748b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text); padding: 20px;
  }
  h1 { margin: 0 0 4px; font-size: 1.5rem; color: var(--accent); }
  h2 { margin: 0 0 12px; font-size: 1.1rem; }
  h3 { margin: 16px 0 8px; font-size: .95rem; color: var(--dim); }
  .sub { color: var(--dim); font-size: .9rem; margin-bottom: 16px; }
  .hidden { display: none !important; }
  .controls {
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
    margin-bottom: 16px;
  }
  .btn {
    border: 0; border-radius: 8px; padding: 10px 18px; font-weight: 600;
    cursor: pointer; font-size: .9rem;
  }
  .btn:disabled { opacity: .45; cursor: not-allowed; }
  .btn-start { background: #059669; color: #fff; }
  .btn-stop { background: #dc2626; color: #fff; }
  .btn-primary { background: var(--accent); color: #0b1220; }
  .btn-ghost { background: transparent; color: var(--text); border: 1px solid var(--border); }
  .btn-sm { padding: 6px 12px; font-size: .8rem; }
  .state-pill {
    display: inline-flex; align-items: center; gap: 8px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 999px; padding: 8px 14px; font-size: .85rem;
  }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--muted); }
  .dot-running { background: var(--ok); }
  .dot-paused { background: var(--warn); }
  .dot-stopped { background: var(--muted); }
  .dot-stopping { background: var(--danger); }
  .temps { color: var(--dim); font-size: .85rem; }
  .login-card, .panel, .stat {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  }
  .login-card { max-width: 380px; margin: 40px auto; padding: 24px; }
  .login-card label { display: block; font-size: .8rem; color: var(--dim); margin: 10px 0 4px; }
  input, select, textarea {
    width: 100%; padding: 8px 10px; border-radius: 8px;
    border: 1px solid var(--border); background: #0b1220; color: var(--text);
    font: inherit;
  }
  textarea { min-height: 72px; resize: vertical; }
  .stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin-bottom: 20px;
  }
  .stat { padding: 14px; text-align: center; }
  .stat .num { font-size: 1.8rem; font-weight: 700; }
  .stat .lbl { font-size: .75rem; color: var(--dim); text-transform: uppercase; }
  .panel { overflow: hidden; margin-bottom: 16px; }
  .panel > h2, .panel-head {
    margin: 0; padding: 12px 16px; font-size: .95rem;
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
  }
  .feed { max-height: 50vh; overflow-y: auto; }
  .row {
    padding: 10px 16px; border-bottom: 1px solid var(--border);
    font-size: .88rem; display: grid;
    grid-template-columns: 72px 72px 1fr auto; gap: 10px; align-items: start;
  }
  .row:last-child { border-bottom: none; }
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: .7rem; font-weight: 600; text-transform: uppercase;
  }
  .badge-found { background: #1e3a5f; color: #93c5fd; }
  .badge-filtered { background: #3f3f1a; color: #fde047; }
  .badge-saved { background: #14532d; color: #86efac; }
  .badge-cycle { background: #312e81; color: #c4b5fd; }
  .badge-error { background: #450a0a; color: #fca5a5; }
  .badge-status { background: #1e293b; color: #cbd5e1; }
  .badge-thermal { background: #7c2d12; color: #fdba74; }
  .time { color: var(--muted); font-size: .75rem; }
  .empty { padding: 40px; text-align: center; color: var(--dim); }
  .pending a { color: var(--accent); }
  .msg { color: var(--warn); font-size: .85rem; min-height: 1.2em; margin-bottom: 8px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
  .tab {
    background: transparent; border: 1px solid var(--border); color: var(--dim);
    border-radius: 8px; padding: 8px 14px; cursor: pointer; font-weight: 600;
  }
  .tab.active { background: var(--accent); color: #0b1220; border-color: var(--accent); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .field { margin-bottom: 10px; }
  .field label { display: block; font-size: .78rem; color: var(--dim); margin-bottom: 4px; }
  .check-row { display: flex; flex-wrap: wrap; gap: 12px; font-size: .85rem; }
  .settings-body { padding: 16px; }
  .settings-readonly input,
  .settings-readonly select,
  .settings-readonly textarea {
    opacity: .72; background: #15202b; cursor: default;
  }
  .user-bar { color: var(--dim); font-size: .85rem; margin-left: auto; }
  @media (max-width: 700px) {
    .row { grid-template-columns: 1fr; gap: 4px; }
    .grid2 { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
  <div id="login-view" class="hidden">
    <div class="login-card">
      <h1>Job Hunter</h1>
      <p class="sub">Sign in to control search and edit shared settings.</p>
      <div id="login-userpass">
        <label for="login-user">Username</label>
        <input id="login-user" autocomplete="username" value="admin">
        <label for="login-pass">Password</label>
        <input id="login-pass" type="password" autocomplete="current-password">
      </div>
      <div id="login-token-wrap" class="hidden">
        <label for="login-token">Sync token</label>
        <input id="login-token" type="password" autocomplete="off" placeholder="AUTOAPPLY_SYNC_TOKEN">
      </div>
      <div class="msg" id="login-msg"></div>
      <button class="btn btn-primary" style="width:100%;margin-top:12px;" onclick="doLogin()">Sign in</button>
      <p class="sub" style="margin-top:14px;font-size:.75rem;">
        Prefer AUTOAPPLY_HUNTER_USER + AUTOAPPLY_HUNTER_PASSWORD_HASH (or ~/.autoapply/hunter_auth.json).
        Until then, sign in with the same Bearer sync token the Mac uses.
      </p>
    </div>
  </div>

  <div id="app-view" class="hidden">
    <div class="controls">
      <h1 style="margin:0;flex:1;">Job Hunter Dashboard</h1>
      <span class="user-bar" id="user-bar"></span>
      <button class="btn btn-ghost btn-sm" onclick="doLogout()">Log out</button>
    </div>
    <p class="sub">Search worker · thermal pause · shared profile/search for Mac clients. Auto-refresh 5s.</p>

    <div class="tabs">
      <button class="tab active" id="tab-dash" onclick="showTab('dash')">Dashboard</button>
      <button class="tab" id="tab-settings" onclick="showTab('settings')">Shared settings</button>
    </div>

    <div id="view-dash">
      <div class="controls">
        <button class="btn btn-start" id="btn-start" onclick="startHunt()">Start search</button>
        <button class="btn btn-stop" id="btn-stop" onclick="stopHunt()">Stop search</button>
        <span class="state-pill"><span class="dot" id="state-dot"></span><span id="state-label">—</span></span>
        <span class="temps" id="temps"></span>
      </div>
      <div class="msg" id="control-msg"></div>
      <div class="stats" id="stats"></div>
      <div class="panel">
        <h2>Pending for Mac sync <span class="pending" id="pending-count"></span></h2>
        <div id="pending-list" class="feed"></div>
      </div>
      <div class="panel">
        <h2>Activity feed <span class="time" id="last-refresh"></span></h2>
        <div id="feed" class="feed"></div>
      </div>
    </div>

    <div id="view-settings" class="hidden">
      <div class="panel" id="settings-panel">
        <div class="panel-head">
          <span>Shared profile &amp; search (synced to Mac)</span>
          <div>
            <button class="btn btn-ghost btn-sm" id="btn-edit-settings" onclick="unlockSettings()">Edit</button>
            <button class="btn btn-primary btn-sm hidden" id="btn-save-settings" onclick="saveSettings()">Save</button>
            <button class="btn btn-ghost btn-sm hidden" id="btn-cancel-settings" onclick="lockSettings(true)">Cancel</button>
          </div>
        </div>
        <div class="settings-body settings-readonly" id="settings-form">
          <h3>Profile</h3>
          <div class="grid2">
            <div class="field"><label>First name</label><input id="cfg-first-name"></div>
            <div class="field"><label>Last name</label><input id="cfg-last-name"></div>
            <div class="field"><label>Email</label><input id="cfg-email" type="email"></div>
            <div class="field"><label>Phone</label>
              <div style="display:flex;gap:8px;">
                <input id="cfg-phone-code" style="width:80px;" value="+1">
                <input id="cfg-phone" style="flex:1;">
              </div>
            </div>
            <div class="field"><label>City</label><input id="cfg-city"></div>
            <div class="field"><label>State</label><input id="cfg-state"></div>
            <div class="field"><label>Country</label><input id="cfg-country"></div>
            <div class="field"><label>ZIP</label><input id="cfg-zip"></div>
          </div>
          <div class="field"><label>Address line 1</label><input id="cfg-address1"></div>
          <div class="field"><label>Address line 2</label><input id="cfg-address2"></div>
          <div class="field"><label>Bio</label><textarea id="cfg-bio"></textarea></div>
          <div class="grid2">
            <div class="field"><label>LinkedIn URL</label><input id="cfg-linkedin"></div>
            <div class="field"><label>Portfolio URL</label><input id="cfg-portfolio"></div>
          </div>

          <h3>Search criteria</h3>
          <div class="field"><label>Job titles (comma-separated)</label><input id="cfg-titles" placeholder="Software Engineer, Backend"></div>
          <div class="field"><label>Locations (comma-separated)</label><input id="cfg-locations" placeholder="Remote, São Paulo"></div>
          <div class="grid2">
            <div class="field"><label>Keywords include</label><input id="cfg-include"></div>
            <div class="field"><label>Keywords exclude</label><input id="cfg-exclude"></div>
            <div class="field"><label>Min salary</label><input id="cfg-salary" type="number"></div>
            <div class="field"><label>Job languages (pt,en,es)</label><input id="cfg-job-langs" value="pt,en,es"></div>
          </div>
          <div class="field check-row">
            <label><input type="checkbox" id="cfg-remote"> Remote only</label>
          </div>
          <div class="field"><label>Experience levels</label>
            <div class="check-row">
              <label><input type="checkbox" class="cfg-exp" value="entry"> Entry</label>
              <label><input type="checkbox" class="cfg-exp" value="mid"> Mid</label>
              <label><input type="checkbox" class="cfg-exp" value="senior"> Senior</label>
              <label><input type="checkbox" class="cfg-exp" value="lead"> Lead</label>
            </div>
          </div>

          <h3>Bot filters</h3>
          <div class="grid2">
            <div class="field"><label>Min match score</label><input id="cfg-min-score" type="number" min="0" max="100"></div>
            <div class="field"><label>Search interval (seconds)</label><input id="cfg-interval" type="number"></div>
            <div class="field"><label>Max applications / day</label><input id="cfg-max-apps" type="number"></div>
            <div class="field"><label>Delay between apps (sec)</label><input id="cfg-delay" type="number"></div>
            <div class="field"><label>Enabled platforms (comma)</label><input id="cfg-platforms" placeholder="linkedin"></div>
          </div>
          <div class="msg" id="settings-msg"></div>
        </div>
      </div>
    </div>
  </div>

<script>
const TYPE_CLASS = {
  found: 'badge-found', filtered: 'badge-filtered', saved: 'badge-saved',
  cycle: 'badge-cycle', error: 'badge-error', status: 'badge-status', thermal: 'badge-thermal',
};

let settingsEdit = false;
let settingsCache = null;

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function csv(list) { return (list || []).join(', '); }
function splitCsv(s) {
  return String(s || '').split(',').map(x => x.trim()).filter(Boolean);
}
function setMsg(el, text) { document.getElementById(el).textContent = text || ''; }

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

async function checkSession() {
  const s = await api('/api/hunter/session');
  const tokenWrap = document.getElementById('login-token-wrap');
  const userPass = document.getElementById('login-userpass');
  if (!s.credentials_configured && s.auth_required) {
    tokenWrap.classList.remove('hidden');
    userPass.classList.add('hidden');
  } else {
    tokenWrap.classList.add('hidden');
    userPass.classList.remove('hidden');
  }
  if (s.authenticated) {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('app-view').classList.remove('hidden');
    document.getElementById('user-bar').textContent = s.username ? ('Signed in as ' + s.username) : '';
    refresh();
    loadSettings();
  } else if (s.auth_required || s.credentials_configured) {
    document.getElementById('login-view').classList.remove('hidden');
    document.getElementById('app-view').classList.add('hidden');
  } else {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('app-view').classList.remove('hidden');
    document.getElementById('user-bar').textContent = 'Local access (set hunter password for public URL)';
    refresh();
    loadSettings();
  }
}

async function doLogin() {
  setMsg('login-msg', 'Signing in…');
  try {
    const token = document.getElementById('login-token').value.trim();
    const body = token
      ? { token }
      : {
          username: document.getElementById('login-user').value.trim(),
          password: document.getElementById('login-pass').value,
        };
    await api('/api/hunter/login', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    setMsg('login-msg', '');
    await checkSession();
  } catch (e) {
    setMsg('login-msg', e.message || 'Login failed');
  }
}

async function doLogout() {
  try { await api('/api/hunter/logout', { method: 'POST', body: '{}' }); } catch {}
  location.reload();
}

function showTab(name) {
  document.getElementById('view-dash').classList.toggle('hidden', name !== 'dash');
  document.getElementById('view-settings').classList.toggle('hidden', name !== 'settings');
  document.getElementById('tab-dash').classList.toggle('active', name === 'dash');
  document.getElementById('tab-settings').classList.toggle('active', name === 'settings');
}

function fmtTime(iso) {
  if (!iso) return '--';
  try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
}

function renderStats(s) {
  const items = [
    ['Cycles', s.cycles_completed],
    ['Found', s.found_total],
    ['Filtered', s.filtered_total],
    ['Saved', s.saved_total],
    ['Last cycle', s.last_cycle_saved + ' saved'],
    ['Pending sync', s.pending_sync],
  ];
  document.getElementById('stats').innerHTML = items.map(([lbl, n]) =>
    `<div class="stat"><div class="num">${n}</div><div class="lbl">${lbl}</div></div>`
  ).join('');
}

function renderState(s, sensors) {
  const state = s.run_state || 'stopped';
  const dot = document.getElementById('state-dot');
  const label = document.getElementById('state-label');
  dot.className = 'dot dot-' + (state === 'paused_thermal' ? 'paused' : state);
  label.textContent = state + (s.pause_reason ? ' — ' + s.pause_reason : '');
  const sens = sensors || s.sensors || {};
  document.getElementById('temps').textContent =
    `CPU ${sens.cpu_c ?? '?'}°C · SMC ${sens.smc_c ?? '?'}°C · Fan ${sens.fan_rpm ?? '?'} RPM`;
  document.getElementById('btn-start').disabled = state === 'running' || state === 'paused_thermal' || state === 'stopping';
  document.getElementById('btn-stop').disabled = state === 'stopped';
}

function renderFeed(events) {
  const el = document.getElementById('feed');
  if (!events.length) {
    el.innerHTML = '<div class="empty">No activity yet. Click Start search.</div>';
    return;
  }
  el.innerHTML = events.map(e => {
    const title = e.job_title || e.message || '';
    const sub = e.company ? `${e.company}${e.platform ? ' · ' + e.platform : ''}` : '';
    const extra = e.type === 'filtered' ? (e.reason || '') :
      e.type === 'saved' ? `score ${e.score} · id ${e.job_id}` :
      e.score != null ? `score ${e.score}` : '';
    return `<div class="row">
      <span class="time">${fmtTime(e.ts)}</span>
      <span><span class="badge ${TYPE_CLASS[e.type] || ''}">${e.type}</span></span>
      <span><strong>${escapeHtml(title)}</strong><br><span class="time">${escapeHtml(sub)}</span></span>
      <span class="time">${escapeHtml(extra)}</span>
    </div>`;
  }).join('');
}

function renderPending(jobs) {
  document.getElementById('pending-count').textContent = `(${jobs.length})`;
  const el = document.getElementById('pending-list');
  if (!jobs.length) {
    el.innerHTML = '<div class="empty">No jobs waiting for Mac import yet.</div>';
    return;
  }
  el.innerHTML = jobs.slice(0, 30).map(j =>
    `<div class="row" style="grid-template-columns:1fr auto auto;">
      <span><strong>${escapeHtml(j.job_title)}</strong><br>
        <span class="time">${escapeHtml(j.company)} · score ${j.match_score}</span></span>
      <span class="time">${escapeHtml(j.location || '')}</span>
      <a href="${escapeHtml(j.apply_url)}" target="_blank" rel="noopener">Open</a>
    </div>`
  ).join('');
}

async function control(path) {
  return api(path, { method: 'POST', body: '{}' });
}

async function startHunt() {
  setMsg('control-msg', 'Starting…');
  try {
    await control('/api/hunter/start');
    setMsg('control-msg', 'Search started');
    refresh();
  } catch (e) {
    setMsg('control-msg', e.message || 'Start failed');
  }
}

async function stopHunt() {
  setMsg('control-msg', 'Stopping…');
  try {
    await control('/api/hunter/stop');
    setMsg('control-msg', 'Stop requested');
    refresh();
  } catch (e) {
    setMsg('control-msg', e.message || 'Stop failed');
  }
}

async function refresh() {
  try {
    const data = await api('/api/hunter/dashboard');
    renderStats(data.stats);
    renderState(data.stats || {}, data.sensors);
    renderFeed(data.activity || []);
    renderPending(data.pending_jobs || []);
    document.getElementById('last-refresh').textContent = 'updated ' + new Date().toLocaleTimeString();
  } catch (e) {
    if (String(e.message).includes('Unauthorized')) {
      document.getElementById('login-view').classList.remove('hidden');
      document.getElementById('app-view').classList.add('hidden');
      return;
    }
    document.getElementById('feed').innerHTML =
      '<div class="empty">Could not load dashboard. Is the Job Hunter running?</div>';
  }
}

function fillSettings(cfg) {
  const p = cfg.profile || {};
  const s = cfg.search_criteria || {};
  const b = cfg.bot || {};
  document.getElementById('cfg-first-name').value = p.first_name || '';
  document.getElementById('cfg-last-name').value = p.last_name || '';
  document.getElementById('cfg-email').value = p.email || '';
  document.getElementById('cfg-phone-code').value = p.phone_country_code || '+1';
  document.getElementById('cfg-phone').value = p.phone || '';
  document.getElementById('cfg-city').value = p.city || '';
  document.getElementById('cfg-state').value = p.state || '';
  document.getElementById('cfg-country').value = p.country || '';
  document.getElementById('cfg-zip').value = p.zip_code || '';
  document.getElementById('cfg-address1').value = p.address_line1 || '';
  document.getElementById('cfg-address2').value = p.address_line2 || '';
  document.getElementById('cfg-bio').value = p.bio || '';
  document.getElementById('cfg-linkedin').value = p.linkedin_url || '';
  document.getElementById('cfg-portfolio').value = p.portfolio_url || '';
  document.getElementById('cfg-titles').value = csv(s.job_titles);
  document.getElementById('cfg-locations').value = csv(s.locations);
  document.getElementById('cfg-include').value = csv(s.keywords_include);
  document.getElementById('cfg-exclude').value = csv(s.keywords_exclude);
  document.getElementById('cfg-salary').value = s.salary_min ?? '';
  document.getElementById('cfg-job-langs').value = csv(s.job_languages || ['pt','en','es']);
  document.getElementById('cfg-remote').checked = !!s.remote_only;
  const levels = s.experience_levels || [];
  document.querySelectorAll('.cfg-exp').forEach(cb => { cb.checked = levels.includes(cb.value); });
  document.getElementById('cfg-min-score').value = b.min_match_score ?? 75;
  document.getElementById('cfg-interval').value = b.search_interval_seconds ?? 1800;
  document.getElementById('cfg-max-apps').value = b.max_applications_per_day ?? 15;
  document.getElementById('cfg-delay').value = b.delay_between_applications_seconds ?? 60;
  document.getElementById('cfg-platforms').value = csv(b.enabled_platforms || ['linkedin']);
}

function collectSettings() {
  return {
    profile: {
      first_name: document.getElementById('cfg-first-name').value.trim(),
      last_name: document.getElementById('cfg-last-name').value.trim(),
      email: document.getElementById('cfg-email').value.trim(),
      phone_country_code: document.getElementById('cfg-phone-code').value.trim() || '+1',
      phone: document.getElementById('cfg-phone').value.trim(),
      city: document.getElementById('cfg-city').value.trim(),
      state: document.getElementById('cfg-state').value.trim(),
      country: document.getElementById('cfg-country').value.trim() || 'United States',
      zip_code: document.getElementById('cfg-zip').value.trim(),
      address_line1: document.getElementById('cfg-address1').value.trim(),
      address_line2: document.getElementById('cfg-address2').value.trim(),
      bio: document.getElementById('cfg-bio').value,
      linkedin_url: document.getElementById('cfg-linkedin').value.trim() || null,
      portfolio_url: document.getElementById('cfg-portfolio').value.trim() || null,
    },
    search_criteria: {
      job_titles: splitCsv(document.getElementById('cfg-titles').value),
      locations: splitCsv(document.getElementById('cfg-locations').value),
      keywords_include: splitCsv(document.getElementById('cfg-include').value),
      keywords_exclude: splitCsv(document.getElementById('cfg-exclude').value),
      salary_min: parseInt(document.getElementById('cfg-salary').value, 10) || null,
      remote_only: document.getElementById('cfg-remote').checked,
      experience_levels: [...document.querySelectorAll('.cfg-exp:checked')].map(c => c.value),
      job_languages: splitCsv(document.getElementById('cfg-job-langs').value),
    },
    bot: {
      min_match_score: parseInt(document.getElementById('cfg-min-score').value, 10) || 75,
      search_interval_seconds: parseInt(document.getElementById('cfg-interval').value, 10) || 1800,
      max_applications_per_day: parseInt(document.getElementById('cfg-max-apps').value, 10) || 15,
      delay_between_applications_seconds: parseInt(document.getElementById('cfg-delay').value, 10) || 60,
      enabled_platforms: splitCsv(document.getElementById('cfg-platforms').value),
    },
  };
}

function setSettingsEditable(on) {
  settingsEdit = on;
  const form = document.getElementById('settings-form');
  form.classList.toggle('settings-readonly', !on);
  form.querySelectorAll('input, select, textarea').forEach(el => {
    el.disabled = !on;
    if (el.type !== 'checkbox') el.readOnly = !on;
  });
  document.getElementById('btn-edit-settings').classList.toggle('hidden', on);
  document.getElementById('btn-save-settings').classList.toggle('hidden', !on);
  document.getElementById('btn-cancel-settings').classList.toggle('hidden', !on);
}

function unlockSettings() { setSettingsEditable(true); }
function lockSettings(reload) {
  setSettingsEditable(false);
  if (reload && settingsCache) fillSettings(settingsCache);
}

async function loadSettings() {
  try {
    settingsCache = await api('/api/hunter/config');
    fillSettings(settingsCache);
    setSettingsEditable(false);
  } catch (e) {
    setMsg('settings-msg', e.message || 'Could not load settings');
  }
}

async function saveSettings() {
  setMsg('settings-msg', 'Saving…');
  try {
    const payload = collectSettings();
    const res = await api('/api/hunter/config', { method: 'PUT', body: JSON.stringify(payload) });
    settingsCache = res.config || payload;
    fillSettings(settingsCache);
    setSettingsEditable(false);
    setMsg('settings-msg', 'Saved to ~/.autoapply/config.json — Mac can pull via GET /api/sync/config');
  } catch (e) {
    setMsg('settings-msg', e.message || 'Save failed');
  }
}

document.getElementById('login-pass').addEventListener('keydown', e => {
  if (e.key === 'Enter') doLogin();
});

checkSession();
setInterval(() => {
  if (!document.getElementById('app-view').classList.contains('hidden')) refresh();
}, 5000);
</script>
</body>
</html>
"""
