import { Router } from 'express';
import { requireLogin } from '../../mystery6-src/middleware/auth.js';
import { getConfigDb } from '../../mystery6-src/db/config-db.js';
import { getTargetAdapter } from '../../mystery6-src/db/target-db.js';

const router = Router();

function activityLabel(status, stage) {
  stage = stage || '';
  if (status === 'rejected') return 'Declined';
  if (status === 'offer') return 'Offer';
  if (stage.startsWith('interview')) return 'Interviewed';
  if (stage === 'screen' || stage === 'phone_screen') return 'Screened';
  return 'Applied';
}

function isoDate(d) {
  // Local calendar date, not UTC — matches Python's date.today() and avoids
  // an off-by-one near midnight when the server's local timezone is behind UTC.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

router.get('/activity', requireLogin, async (req, res, next) => {
  try {
    const today = new Date();
    const defaultStart = new Date(today);
    defaultStart.setDate(defaultStart.getDate() - 7);

    const start = DATE_RE.test(req.query.start) ? req.query.start : isoDate(defaultStart);
    const end = DATE_RE.test(req.query.end) ? req.query.end : isoDate(today);

    const adapter = getTargetAdapter(getConfigDb());
    const rows = await adapter.select(`
      SELECT j.company, j.role, j.score, a.status, a.stage,
             date(a.applied_at)   AS applied_at,
             date(a.concluded_at) AS concluded_at
      FROM applications a
      JOIN jds j ON a.jd_id = j.id
      WHERE date(a.applied_at) BETWEEN ? AND ?
         OR (a.concluded_at IS NOT NULL AND date(a.concluded_at) BETWEEN ? AND ?)
      ORDER BY COALESCE(date(a.concluded_at), date(a.applied_at)) DESC, j.company
    `, [start, end, start, end]);

    const data = rows.map((r) => ({
      company: r.company,
      role: r.role,
      score: r.score,
      activity: activityLabel(r.status, r.stage),
      date: (r.status === 'rejected' || r.status === 'offer') ? r.concluded_at : r.applied_at,
    }));

    res.json({ status: 'ok', message: 'ok', data: { start, end, rows: data } });
  } catch (err) {
    next(err);
  }
});

router.get('/unemployment', requireLogin, async (req, res, next) => {
  try {
    const today = new Date();
    const currentWeekStart = new Date(today);
    currentWeekStart.setDate(today.getDate() - today.getDay());
    const defaultWeekStart = new Date(currentWeekStart);
    defaultWeekStart.setDate(currentWeekStart.getDate() - 7);

    let weekStart = defaultWeekStart;
    if (DATE_RE.test(req.query.weekStart)) {
      const [y, m, d] = req.query.weekStart.split('-').map(Number);
      weekStart = new Date(y, m - 1, d);
      weekStart.setDate(weekStart.getDate() - weekStart.getDay()); // snap to Sunday
    }
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 6);

    const start = isoDate(weekStart);
    const end = isoDate(weekEnd);

    const adapter = getTargetAdapter(getConfigDb());

    const applied = await adapter.select(`
      SELECT j.company, j.role, date(a.applied_at) AS date, 'Applied' AS activity
      FROM applications a JOIN jds j ON a.jd_id = j.id
      WHERE a.applied_at IS NOT NULL AND date(a.applied_at) BETWEEN ? AND ?
    `, [start, end]);

    const offers = await adapter.select(`
      SELECT j.company, j.role, date(a.concluded_at) AS date, 'Offer' AS activity
      FROM applications a JOIN jds j ON a.jd_id = j.id
      WHERE a.concluded_at IS NOT NULL AND date(a.concluded_at) BETWEEN ? AND ?
        AND a.status = 'offer'
    `, [start, end]);

    // Rejections aren't a job-search activity you performed, so they're excluded by
    // default — unless the rejection followed an interview/screening that also
    // happened this same week, in which case it's the direct outcome of real
    // engagement that week and worth showing alongside it.
    const declines = await adapter.select(`
      SELECT j.company, j.role, date(a.concluded_at) AS date, 'Declined' AS activity
      FROM applications a JOIN jds j ON a.jd_id = j.id
      WHERE a.concluded_at IS NOT NULL AND date(a.concluded_at) BETWEEN ? AND ?
        AND a.status = 'rejected'
        AND EXISTS (
          SELECT 1 FROM contacts c
          WHERE c.jd_id = a.jd_id AND c.interview_date IS NOT NULL
            AND date(c.interview_date) BETWEEN ? AND ?
        )
    `, [start, end, start, end]);

    const interviews = await adapter.select(`
      SELECT j.company, j.role, date(c.interview_date) AS date,
             CASE c.interview_stage WHEN 'screen' THEN 'Screened' ELSE 'Interviewed' END AS activity
      FROM contacts c JOIN jds j ON c.jd_id = j.id
      WHERE c.interview_date IS NOT NULL AND date(c.interview_date) BETWEEN ? AND ?
    `, [start, end]);

    const assessments = await adapter.select(`
      SELECT j.company, j.role, date(ass.submitted_at) AS date, 'Assessment Submitted' AS activity
      FROM assessments ass
      JOIN applications a ON ass.application_id = a.id
      JOIN jds j ON a.jd_id = j.id
      WHERE ass.submitted_at IS NOT NULL AND date(ass.submitted_at) BETWEEN ? AND ?
    `, [start, end]);

    const rows = [...applied, ...offers, ...declines, ...interviews, ...assessments]
      .filter((r) => r.activity)
      .sort((a, b) => a.date.localeCompare(b.date) || a.company.localeCompare(b.company))
      .map((r) => ({ date: r.date, activity: r.activity, company: r.company, role: r.role }));

    res.json({ status: 'ok', message: 'ok', data: { weekStart: start, weekEnd: end, rows } });
  } catch (err) {
    next(err);
  }
});

// The standalone /matches ("JD Match Scores") report was removed once Leads and
// Applications both carried a Match Score column of their own — it had become a
// third view of the same number.

router.get('/leads', requireLogin, async (req, res, next) => {
  try {
    const adapter = getTargetAdapter(getConfigDb());
    // active_leads (a SQL view) is the single source of truth for lead selection
    // + ordering — shared with generate_home.write_leads_dashboard on the Python side.
    const rows = await adapter.select(`SELECT * FROM active_leads`);

    const data = rows.map((r) => ({
      score: r.score,
      company: r.company,
      role: r.role,
      source: r.source || 'paul',
      salary_min: r.salary_min,
      salary_max: r.salary_max,
      salary_currency: r.salary_currency || 'USD',
      status: r.lead_status,
      url: r.url || '',
      summary: r.summary || '',
      evaluated: r.evaluated || '',
    }));

    res.json({ status: 'ok', message: 'ok', data: { rows: data } });
  } catch (err) {
    next(err);
  }
});

router.get('/upcoming', requireLogin, async (req, res, next) => {
  try {
    const adapter = getTargetAdapter(getConfigDb());
    const today = isoDate(new Date());

    const interviews = await adapter.select(`
      SELECT c.interview_date AS dt, c.interview_time AS tm,
             j.company, j.role, c.interview_stage AS detail
      FROM contacts c
      JOIN jds j ON c.jd_id = j.id
      WHERE c.interview_date IS NOT NULL AND c.interview_date >= ?
    `, [today]);

    const assessments = await adapter.select(`
      SELECT ass.deadline AS dt, NULL AS tm,
             j.company, j.role, ass.description AS detail
      FROM assessments ass
      JOIN applications a ON ass.application_id = a.id
      JOIN jds j ON a.jd_id = j.id
      WHERE ass.deadline IS NOT NULL AND ass.submitted_at IS NULL AND ass.deadline >= ?
    `, [today]);

    const rows = [
      ...interviews.map((r) => ({ ...r, kind: 'Interview' })),
      ...assessments.map((r) => ({ ...r, kind: 'Assessment' })),
    ].sort((a, b) => (a.dt + (a.tm || '')).localeCompare(b.dt + (b.tm || '')));

    const data = rows.map((r) => ({
      date: r.dt,
      time: (r.tm || '').slice(0, 5) || '—',
      kind: r.kind,
      company: r.company,
      role: r.role,
      detail: r.detail || '',
    }));

    res.json({ status: 'ok', message: 'ok', data: { rows: data } });
  } catch (err) {
    next(err);
  }
});

router.get('/skill-frequency', requireLogin, async (req, res, next) => {
  try {
    const adapter = getTargetAdapter(getConfigDb());
    // Must stay in sync with reports/skills.py's view_frequency() — the CLI and this
    // view are supposed to be the same report. Two things here are load-bearing:
    //
    // 1. Grouping on COALESCE(canonical_label, lower(skill_label)), not on the raw
    //    label. The canonicalization migration exists so "k8s" and "kubernetes"
    //    aggregate into one row; grouping on the raw label undoes it. On a real
    //    database that split AWS across 5 rows and Python across 8, which scrambles
    //    the ranking this report is entirely about.
    // 2. MAX(skill_id), not a bare skill_id. Under GROUP BY, SQLite picks a bare
    //    column from an arbitrary row in the group, so a skill matched to the user's
    //    taxonomy in some JDs but not others got a coin-flip checkmark. MAX() is
    //    non-NULL whenever any row in the group matched, which is the actual question.
    //    Same reason skill_label is wrapped: pick a stable label, not an arbitrary one.
    const rows = await adapter.select(`
      SELECT MAX(skill_label) as skill_label,
             COALESCE(canonical_label, lower(skill_label)) as grp,
             COUNT(*) as demand,
             MAX(skill_id) as skill_id
      FROM jd_required_skills
      GROUP BY grp
      ORDER BY demand DESC, grp
      LIMIT 30
    `);
    const [{ total: totalJds }] = await adapter.select(`SELECT COUNT(*) as total FROM jds WHERE file_path IS NOT NULL`);

    const data = rows.map((r) => ({
      // grp is the canonical, alias-normalized form — the same string the CLI prints.
      skill: r.grp || r.skill_label,
      demand: r.demand,
      pct: totalJds ? Math.floor((r.demand / totalJds) * 100) : 0,
      inTaxonomy: !!r.skill_id,
    }));

    res.json({ status: 'ok', message: 'ok', data: { totalJds, rows: data } });
  } catch (err) {
    next(err);
  }
});

router.get('/skill-gaps', requireLogin, async (req, res, next) => {
  try {
    const adapter = getTargetAdapter(getConfigDb());

    const profileTerms = new Set();
    for (const row of await adapter.select(`SELECT content FROM skills`)) {
      for (const term of (row.content || '').split(',')) {
        const t = term.trim().toLowerCase();
        if (t) profileTerms.add(t);
      }
    }
    for (const row of await adapter.select(`SELECT text FROM bullets`)) {
      for (const word of (row.text || '').toLowerCase().split(/\s+/)) {
        if (word) profileTerms.add(word);
      }
    }
    const longTerms = [...profileTerms].filter((t) => t.length > 3);

    const demandRows = await adapter.select(`
      SELECT skill_label, COUNT(*) as demand, skill_id
      FROM jd_required_skills
      GROUP BY lower(skill_label)
      HAVING demand >= 2
      ORDER BY demand DESC
    `);

    const gaps = demandRows.filter((r) => {
      const label = r.skill_label.toLowerCase();
      if (profileTerms.has(label)) return false;
      return !longTerms.some((t) => label.includes(t) || t.includes(label));
    });

    const [{ total: totalJds }] = await adapter.select(`SELECT COUNT(*) as total FROM jds WHERE file_path IS NOT NULL`);

    const data = gaps.map((r) => ({
      skill: r.skill_label,
      demand: r.demand,
      pct: totalJds ? Math.floor((r.demand / totalJds) * 100) : 0,
    }));

    res.json({ status: 'ok', message: 'ok', data: { rows: data } });
  } catch (err) {
    next(err);
  }
});

export default router;
