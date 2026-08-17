import { api } from '/js/api.js';
import { renderNav } from '/js/components/nav.js';
import { flash } from '/js/components/flash.js';

// Order is the nav order, and the first entry is what loads on open.
const REPORTS = [
  { key: 'upcoming', label: 'Upcoming Dates', load: (root, el) => loadSimpleReport(root, el, {
      endpoint: 'upcoming',
      emptyMessage: 'No upcoming interviews or assessment deadlines.',
      columns: [
        { label: 'Date', key: 'date' },
        { label: 'Time', key: 'time' },
        { label: 'Kind', key: 'kind' },
        { label: 'Company', key: 'company' },
        { label: 'Role', key: 'role' },
        { label: 'Detail', key: 'detail' },
      ],
    }) },
  { key: 'leads', label: 'Leads', load: loadLeads },
  { key: 'activity', label: 'Applications', load: loadActivity },
  { key: 'skills', label: 'Skills', load: loadSkills },
  { key: 'unemployment', label: 'Unemployment Report', load: loadUnemployment },
];

// The two skill views are one report with a toggle rather than two nav items:
// they answer the same question ("what do employers want that I don't claim?")
// from opposite sides, and splitting them is what made a skill missing from one
// while flagged in the other read as a contradiction.
const SKILL_VIEWS = {
  demand: {
    label: 'All demanded skills',
    toggleTo: 'gaps',
    toggleLabel: 'View Skill Gaps →',
    endpoint: 'skill-frequency',
    emptyMessage: 'No skill demand data found.',
    columns: [
      { label: 'Skill', key: 'skill' },
      { label: 'Demand', render: (r) => `${r.demand} JDs (${r.pct}%)` },
      { label: 'In your skills', render: (r) => (r.inTaxonomy ? '✓' : '') },
    ],
    caption: '✓ = this demanded skill matched a group in your own skills library. '
           + 'A blank row is a skill employers are asking for that your profile does '
           + 'not currently claim.',
  },
  gaps: {
    label: 'Skill gaps',
    toggleTo: 'demand',
    toggleLabel: '← View all demanded skills',
    endpoint: 'skill-gaps',
    emptyMessage: 'No significant gaps found.',
    columns: [
      { label: 'Skill', key: 'skill' },
      { label: 'Demand', render: (r) => `${r.demand} JDs (${r.pct}%)` },
    ],
    caption: 'Skills demanded across the JDs you have evaluated that are absent '
           + 'from your skills library and your bullets.',
  },
};

function loadSkills(root, contentEl, view = 'demand') {
  const cfg = SKILL_VIEWS[view];
  contentEl.innerHTML = `
    <div class="bff-skills-toggle">
      <strong>${cfg.label}</strong>
      <a href="#" id="bff-skills-toggle">${cfg.toggleLabel}</a>
    </div>
    <div id="bff-skills-body"><p class="text-muted">Loading…</p></div>
  `;
  contentEl.querySelector('#bff-skills-toggle').addEventListener('click', (e) => {
    e.preventDefault();
    loadSkills(root, contentEl, cfg.toggleTo);
  });
  fetchSimpleReport(root, contentEl.querySelector('#bff-skills-body'),
                    cfg.endpoint, cfg.columns, cfg.emptyMessage, cfg.caption);
}

function isoDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export async function render(root) {
  renderNav(root, { title: '' });

  root.innerHTML = `
    <div class="page-wrap">
      <div id="flash-area"></div>
      <style>
        .bff-reports-layout { display: grid; grid-template-columns: 200px 1fr; gap: 2rem; align-items: start; }
        .bff-reports-nav { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; text-align: center; }
        .bff-reports-nav img { width: 120px; height: 120px; object-fit: contain; }
        .bff-reports-nav h2 { margin: 0 0 0.5rem; font-size: 1.1rem; }
        .bff-reports-nav-list { display: flex; flex-direction: column; gap: 0.4rem; width: 100%; }
        .bff-reports-nav-list a {
          display: block; padding: 0.6rem 0.9rem; border-radius: 0.375rem;
          border: 1px solid var(--m-border); color: var(--m-link); text-decoration: none;
          font-weight: 600; font-size: 0.9rem;
        }
        .bff-reports-nav-list a:hover { background: var(--m-row-hover); }
        .bff-reports-nav-list a.active {
          background: var(--m-accent); border-color: var(--m-accent); color: var(--m-accent-text);
        }
        .bff-reports-header { margin: 0 0 1rem; color: var(--m-heading); }
        .bff-reports-filters { display: flex; align-items: flex-end; gap: 1rem; margin-bottom: 1rem; }
        .bff-reports-filters label { display: block; font-size: 0.85rem; margin-bottom: 0.25rem; }
        /* Long role titles should wrap, not ellipsis-truncate like the CRUD list tables do,
           and sorting isn't wired up here so the header shouldn't look clickable. */
        .bff-reports-body .data-table td { white-space: normal; }
        .bff-reports-body .data-table thead th { cursor: default; }
        /* The Leads report is the one place re-sorting (by salary, company…) is useful,
           so its headers opt back into looking + acting clickable. */
        .bff-reports-body .bff-leads-table thead th[data-sort] { cursor: pointer; user-select: none; }
        .bff-reports-body .bff-leads-table thead th[data-sort]:hover { color: var(--m-link); }
        .bff-leads-table a { color: var(--m-link); font-weight: 600; }
        .bff-skills-toggle {
          display: flex; align-items: baseline; justify-content: space-between;
          gap: 1rem; margin-bottom: 1rem;
        }
        .bff-skills-toggle a { color: var(--m-link); font-weight: 600; font-size: 0.9rem; }
        .bff-unemployment-nav { margin-top: 0; margin-bottom: 1rem; }
        .bff-unemployment-nav .page-info { font-size: 0.95rem; font-weight: 600; }
      </style>
      <div class="bff-reports-layout">
        <div class="bff-reports-nav">
          <img src="/images/bff-logo.png" alt="Best Foot Forward">
          <h2>BFF Reports</h2>
          <nav class="bff-reports-nav-list" id="bff-reports-nav-list"></nav>
        </div>
        <div>
          <h2 class="bff-reports-header" id="bff-reports-header"></h2>
          <div class="bff-reports-body" id="bff-reports-body"></div>
        </div>
      </div>
    </div>
  `;

  const navListEl = root.querySelector('#bff-reports-nav-list');
  const headerEl = root.querySelector('#bff-reports-header');
  const bodyEl = root.querySelector('#bff-reports-body');

  const select = (report, link) => {
    navListEl.querySelectorAll('a').forEach((a) => a.classList.remove('active'));
    link.classList.add('active');
    headerEl.textContent = report.label;
    report.load(root, bodyEl);
  };

  const links = REPORTS.map((report) => {
    const link = document.createElement('a');
    link.href = '#';
    link.textContent = report.label;
    link.addEventListener('click', (e) => {
      e.preventDefault();
      select(report, link);
    });
    navListEl.appendChild(link);
    return link;
  });

  select(REPORTS[0], links[0]);
}

// ── Leads report (sortable; clickable postings) ──────────────────────────────

function escHtml(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function formatSalary(r) {
  const unit = (!r.salary_currency || r.salary_currency === 'USD') ? '$' : `${r.salary_currency} `;
  const fmt = (n) => unit + Number(n).toLocaleString();
  if (r.salary_min && r.salary_max) return `${fmt(r.salary_min)} – ${fmt(r.salary_max)}`;
  if (r.salary_min) return `${fmt(r.salary_min)}+`;
  if (r.salary_max) return `up to ${fmt(r.salary_max)}`;
  return '—';
}

const LEAD_COLUMNS = [
  { label: 'Match Score', sortKey: 'score', numeric: true, render: (r) => (r.score ?? '—') },
  { label: 'Company', sortKey: 'company', render: (r) => escHtml(r.company) },
  { label: 'Role', sortKey: 'role', render: (r) => escHtml(r.role) },
  { label: 'Source', sortKey: 'source', render: (r) => escHtml(r.source) },
  { label: 'Salary', sortKey: 'salary_min', numeric: true, render: (r) => formatSalary(r) },
  { label: 'Status', sortKey: 'status', render: (r) => escHtml(r.status) },
  { label: 'Link', render: (r) => (r.url ? `<a href="${escHtml(r.url)}" target="_blank" rel="noopener">open ↗</a>` : '—') },
];

function loadLeads(root, contentEl) {
  contentEl.innerHTML = '<p class="text-muted">Loading…</p>';
  fetchLeads(root, contentEl);
}

async function fetchLeads(root, contentEl) {
  const res = await api.get('/plugins/bff-reports/leads');
  if (res.status !== 'ok') {
    flash(root.querySelector('.page-wrap') ?? root, res.message);
    contentEl.innerHTML = '';
    return;
  }

  const { rows } = res.data;
  if (!rows.length) {
    contentEl.innerHTML = '<p class="text-muted">No active leads. Run /evaluate-job to score a JD.</p>';
    return;
  }

  // Server (the active_leads view) already orders score-desc; mirror that as the
  // initial client sort so the header arrow matches the rows on first paint.
  const state = { rows, sortKey: 'score', sortDir: 'desc' };
  renderLeads(contentEl, state);
}

function compareLeads(a, b, state) {
  const col = LEAD_COLUMNS.find((c) => c.sortKey === state.sortKey);
  const dir = state.sortDir === 'asc' ? 1 : -1;
  let av = a[state.sortKey];
  let bv = b[state.sortKey];
  if (col && col.numeric) {
    av = (av == null) ? -Infinity : Number(av);
    bv = (bv == null) ? -Infinity : Number(bv);
    return (av - bv) * dir;
  }
  return String(av ?? '').localeCompare(String(bv ?? '')) * dir;
}

function renderLeads(contentEl, state) {
  const sorted = [...state.rows].sort((a, b) => compareLeads(a, b, state));

  const thead = LEAD_COLUMNS.map((c) => {
    if (!c.sortKey) return `<th>${c.label}</th>`;
    const arrow = state.sortKey === c.sortKey ? (state.sortDir === 'asc' ? ' ▲' : ' ▼') : '';
    return `<th data-sort="${c.sortKey}">${c.label}${arrow}</th>`;
  }).join('');

  const body = sorted.map((r) =>
    `<tr>${LEAD_COLUMNS.map((c) => `<td>${c.render(r)}</td>`).join('')}</tr>`
  ).join('');

  contentEl.innerHTML = `
    <div class="table-wrap">
      <table class="data-table bff-leads-table">
        <thead><tr>${thead}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <p class="text-muted">${sorted.length} active lead(s), highest score first.</p>
  `;

  contentEl.querySelectorAll('th[data-sort]').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.getAttribute('data-sort');
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = key;
        // Numeric columns are most useful high-to-low; text A-to-Z.
        state.sortDir = (key === 'score' || key === 'salary_min') ? 'desc' : 'asc';
      }
      renderLeads(contentEl, state);
    });
  });
}

function loadActivity(root, contentEl) {
  const today = new Date();
  const defaultStart = new Date(today);
  defaultStart.setDate(defaultStart.getDate() - 7);

  contentEl.innerHTML = `
    <div class="bff-reports-filters">
      <div>
        <label for="bff-activity-start">Start date</label>
        <input type="date" id="bff-activity-start" class="form-input" value="${isoDate(defaultStart)}">
      </div>
      <div>
        <label for="bff-activity-end">End date</label>
        <input type="date" id="bff-activity-end" class="form-input" value="${isoDate(today)}">
      </div>
      <button type="button" class="btn btn-primary" id="bff-activity-run">Run</button>
    </div>
    <div id="bff-activity-results"></div>
  `;

  const startEl = contentEl.querySelector('#bff-activity-start');
  const endEl = contentEl.querySelector('#bff-activity-end');
  const resultsEl = contentEl.querySelector('#bff-activity-results');

  const run = () => fetchActivity(root, resultsEl, startEl.value, endEl.value);
  contentEl.querySelector('#bff-activity-run').addEventListener('click', run);
  run();
}

async function fetchActivity(root, resultsEl, start, end) {
  resultsEl.innerHTML = '<p class="text-muted">Loading…</p>';

  const res = await api.get(`/plugins/bff-reports/activity?start=${start}&end=${end}`);
  if (res.status !== 'ok') {
    flash(root.querySelector('.page-wrap') ?? root, res.message);
    resultsEl.innerHTML = '';
    return;
  }

  const { rows } = res.data;

  if (!rows.length) {
    resultsEl.innerHTML = `<p class="text-muted">No activity between ${start} and ${end}.</p>`;
    return;
  }

  const columns = [
    { label: 'Match Score', render: (r) => (r.score ?? '—') },
    { label: 'Company', key: 'company' },
    { label: 'Position', key: 'role' },
    { label: 'Activity', key: 'activity' },
    { label: 'Date', render: (r) => r.date ?? '?' },
  ];
  resultsEl.innerHTML = renderTable(columns, rows)
    + `<p class="text-muted">${rows.length} application(s) with activity between ${start} and ${end}.</p>`;
}

function loadUnemployment(root, contentEl) {
  const today = new Date();
  const currentWeekStart = new Date(today);
  currentWeekStart.setDate(today.getDate() - today.getDay());
  const defaultWeekStart = new Date(currentWeekStart);
  defaultWeekStart.setDate(currentWeekStart.getDate() - 7);

  const state = { weekStart: defaultWeekStart };

  contentEl.innerHTML = `
    <div class="pagination bff-unemployment-nav">
      <button type="button" class="page-btn" id="bff-unemp-prev">&larr; Previous week</button>
      <span class="page-info" id="bff-unemp-range"></span>
      <button type="button" class="page-btn" id="bff-unemp-next">Next week &rarr;</button>
    </div>
    <div id="bff-unemp-results"></div>
  `;

  const rangeEl = contentEl.querySelector('#bff-unemp-range');
  const resultsEl = contentEl.querySelector('#bff-unemp-results');

  const run = () => fetchUnemployment(root, resultsEl, rangeEl, state.weekStart);

  contentEl.querySelector('#bff-unemp-prev').addEventListener('click', () => {
    state.weekStart.setDate(state.weekStart.getDate() - 7);
    run();
  });
  contentEl.querySelector('#bff-unemp-next').addEventListener('click', () => {
    state.weekStart.setDate(state.weekStart.getDate() + 7);
    run();
  });

  run();
}

function formatWeekRange(start, end) {
  const opts = { month: 'short', day: 'numeric' };
  const s = new Date(`${start}T00:00:00`);
  const e = new Date(`${end}T00:00:00`);
  return `${s.toLocaleDateString(undefined, opts)} – ${e.toLocaleDateString(undefined, opts)}, ${e.getFullYear()}`;
}

async function fetchUnemployment(root, resultsEl, rangeEl, weekStart) {
  resultsEl.innerHTML = '<p class="text-muted">Loading…</p>';

  const res = await api.get(`/plugins/bff-reports/unemployment?weekStart=${isoDate(weekStart)}`);
  if (res.status !== 'ok') {
    flash(root.querySelector('.page-wrap') ?? root, res.message);
    resultsEl.innerHTML = '';
    return;
  }

  const { weekStart: start, weekEnd: end, rows } = res.data;
  rangeEl.textContent = formatWeekRange(start, end);

  const columns = [
    { label: 'Date', key: 'date' },
    { label: 'Event Type', key: 'activity' },
    { label: 'Company', key: 'company' },
    { label: 'Position', key: 'role' },
  ];

  const table = rows.length ? renderTable(columns, rows) : '<p class="text-muted">No activity recorded for this week.</p>';
  const note = rows.length >= 3
    ? `<p class="text-muted">${rows.length} activit${rows.length === 1 ? 'y' : 'ies'} found — enough to report for this week.</p>`
    : `<p class="text-muted"><strong>Only ${rows.length} activit${rows.length === 1 ? 'y' : 'ies'} found — most states require at least 3 per week.</strong></p>`;

  resultsEl.innerHTML = table + note;
}

function renderTable(columns, rows) {
  const thead = columns.map((c) => `<th>${c.label}</th>`).join('');
  const body = rows.map((r) => `<tr>${columns.map((c) => `<td>${c.render ? c.render(r) : (r[c.key] ?? '')}</td>`).join('')}</tr>`).join('');
  return `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>${thead}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function loadSimpleReport(root, contentEl, { endpoint, columns, emptyMessage, caption }) {
  contentEl.innerHTML = '<p class="text-muted">Loading…</p>';
  fetchSimpleReport(root, contentEl, endpoint, columns, emptyMessage, caption);
}

async function fetchSimpleReport(root, contentEl, endpoint, columns, emptyMessage, caption) {
  const res = await api.get(`/plugins/bff-reports/${endpoint}`);
  if (res.status !== 'ok') {
    flash(root.querySelector('.page-wrap') ?? root, res.message);
    contentEl.innerHTML = '';
    return;
  }

  const { rows } = res.data;

  if (!rows.length) {
    contentEl.innerHTML = `<p class="text-muted">${emptyMessage}</p>`;
    return;
  }

  // caption is a static string from the REPORTS table above, never user data.
  const captionHtml = caption ? `<p class="text-muted">${caption}</p>` : '';
  contentEl.innerHTML = renderTable(columns, rows)
    + `<p class="text-muted">${rows.length} result(s).</p>`
    + captionHtml;
}
