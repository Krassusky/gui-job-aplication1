"""Self-contained HTML dashboard for the Job Hunter sync server."""

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
    --ok: #34d399; --warn: #fbbf24; --muted: #64748b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text); padding: 20px;
  }
  h1 { margin: 0 0 4px; font-size: 1.5rem; color: var(--accent); }
  .sub { color: var(--dim); font-size: .9rem; margin-bottom: 20px; }
  .stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin-bottom: 20px;
  }
  .stat {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px; text-align: center;
  }
  .stat .num { font-size: 1.8rem; font-weight: 700; }
  .stat .lbl { font-size: .75rem; color: var(--dim); text-transform: uppercase; }
  .panel {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; overflow: hidden;
  }
  .panel h2 {
    margin: 0; padding: 12px 16px; font-size: .95rem;
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
  }
  .feed { max-height: 65vh; overflow-y: auto; }
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
  .time { color: var(--muted); font-size: .75rem; }
  .empty { padding: 40px; text-align: center; color: var(--dim); }
  .pending a { color: var(--accent); }
  @media (max-width: 700px) {
    .row { grid-template-columns: 1fr; gap: 4px; }
  }
</style>
</head>
<body>
  <h1>Job Hunter Dashboard</h1>
  <p class="sub">Live search activity on this machine. Auto-refreshes every 10s.</p>

  <div class="stats" id="stats"></div>

  <div class="panel" style="margin-bottom:16px;">
    <h2>Pending for Mac sync <span class="pending" id="pending-count"></span></h2>
    <div id="pending-list" class="feed"></div>
  </div>

  <div class="panel">
    <h2>Activity feed <span class="time" id="last-refresh"></span></h2>
    <div id="feed" class="feed"></div>
  </div>

<script>
const TYPE_CLASS = {
  found: 'badge-found', filtered: 'badge-filtered', saved: 'badge-saved',
  cycle: 'badge-cycle', error: 'badge-error',
};

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

function renderFeed(events) {
  const el = document.getElementById('feed');
  if (!events.length) {
    el.innerHTML = '<div class="empty">No activity yet. The hunter is searching...</div>';
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

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function refresh() {
  try {
    const res = await fetch('/api/hunter/dashboard');
    const data = await res.json();
    renderStats(data.stats);
    renderFeed(data.activity || []);
    renderPending(data.pending_jobs || []);
    document.getElementById('last-refresh').textContent = 'updated ' + new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById('feed').innerHTML =
      '<div class="empty">Could not load dashboard. Is the Job Hunter running?</div>';
  }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""
