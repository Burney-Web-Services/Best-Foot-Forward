PRAGMA foreign_keys = ON;

-- ── Profile ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS contact (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    phone    TEXT,
    email    TEXT,
    location TEXT
);

CREATE TABLE IF NOT EXISTS education (
    id          INTEGER PRIMARY KEY,
    institution TEXT NOT NULL,
    location    TEXT,
    degree      TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS document_prefs (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    accent_color_hex TEXT NOT NULL DEFAULT '50938A',
    font_name       TEXT NOT NULL DEFAULT 'Calibri'
);

-- ── Bullet library ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employers (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    location   TEXT,
    start_date TEXT,
    end_date   TEXT,       -- NULL means present
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS bullets (
    id          TEXT PRIMARY KEY,
    employer_id INTEGER NOT NULL REFERENCES employers(id),
    role        TEXT NOT NULL,
    text        TEXT NOT NULL,
    use_when    TEXT        -- conditional use; NULL = always eligible
);

CREATE TABLE IF NOT EXISTS bullet_tracks (
    bullet_id TEXT NOT NULL REFERENCES bullets(id) ON DELETE CASCADE,
    track     TEXT NOT NULL,   -- freeform tag inferred from role/scope language
                                -- (engineer, manager, architect, founding-engineer,
                                -- etc.) — not an enum; see ADR-0005
    PRIMARY KEY (bullet_id, track)
);

CREATE TABLE IF NOT EXISTS bullet_themes (
    bullet_id TEXT NOT NULL REFERENCES bullets(id) ON DELETE CASCADE,
    theme     TEXT NOT NULL,
    PRIMARY KEY (bullet_id, theme)
);

-- ── Skills library ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skills (
    id      TEXT PRIMARY KEY,
    label   TEXT NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_tracks (
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    track    TEXT NOT NULL,   -- freeform tag, same convention as bullet_tracks.track
    PRIMARY KEY (skill_id, track)
);

CREATE TABLE IF NOT EXISTS skill_themes (
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    theme    TEXT NOT NULL,
    PRIMARY KEY (skill_id, theme)
);

-- ── Job descriptions ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jds (
    id               INTEGER PRIMARY KEY,
    company          TEXT NOT NULL,
    role             TEXT NOT NULL,
    file_path        TEXT UNIQUE,
    evaluated_at     TEXT,          -- ISO datetime
    score            INTEGER,       -- 0–100 evaluate-job score
    salary_min       INTEGER,       -- low end of posted range
    salary_max       INTEGER,       -- high end of posted range
    salary_target    INTEGER,       -- the seeker's ask/target for this role
    salary_currency  TEXT DEFAULT 'USD',
    output_dir       TEXT,          -- where tailored .docx files are written
    source           TEXT DEFAULT 'paul',   -- 'paul' | 'jess' | 'secondary' | 'pasted' | user identifier
    lead_status      TEXT DEFAULT 'approved', -- 'pending' | 'approved' | 'declined' | 'applied' (declined = seeker passed on the lead; cf. applications.status='rejected' = company rejected the seeker)
    lead_decided_at  TEXT,          -- ISO datetime the lead left 'pending' for a triage decision; NULL while untriaged. Distinct from evaluated_at (when it was scored) — a lead scored weeks ago can be declined today.
    decline_reason   TEXT,          -- the seeker's own one-line reason for passing, in their words (cf. summary = Claude's fit analysis). Set only on lead_status='declined'.
    decline_category TEXT,          -- groupable counterpart to decline_reason: one slug from triage_lead.DECLINE_CATEGORIES ('domain'|'stack'|'role_type'|'level'|'comp'|'location'|'strategy'|'other'). Free text can't be aggregated; this is what lets a report say "I keep passing on support roles". Set only on lead_status='declined'. Validated in Python, not by a CHECK — see triage_lead.py.
    url              TEXT,          -- canonical posting URL
    summary          TEXT,          -- evaluate-job narrative: one-paragraph fit summary
    logseq_page      TEXT           -- title of the Logseq page mirroring this JD (e.g. 'GoGuardian/Staff Software Engineer/Application')
);

CREATE TABLE IF NOT EXISTS jd_required_skills (
    id              INTEGER PRIMARY KEY,
    jd_id           INTEGER NOT NULL REFERENCES jds(id) ON DELETE CASCADE,
    skill_label     TEXT NOT NULL,          -- raw/lowercase matched term from JD text (unchanged shape)
    skill_id        TEXT REFERENCES skills(id),  -- NULL when the term isn't in the user's own skills taxonomy
    -- Added for the skill-gap-vocabulary fix (jd_skills.py): canonical_label is the
    -- display-worthy, alias-normalized form ("k8s" and "kubernetes" both -> "Kubernetes"),
    -- which is what lets equivalent mentions across different JDs aggregate instead of
    -- each staying a singleton the gap report's HAVING demand >= 2 filters out.
    -- source is 'lexicon' | 'profile' | 'llm' — where the term's vocabulary came from.
    canonical_label TEXT,
    source          TEXT
);
CREATE INDEX IF NOT EXISTS idx_jd_required_skills_canonical ON jd_required_skills(canonical_label);

CREATE INDEX IF NOT EXISTS idx_jd_required_skills_jd    ON jd_required_skills(jd_id);
CREATE INDEX IF NOT EXISTS idx_jd_required_skills_label ON jd_required_skills(skill_label);

-- ── Applications ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS applications (
    id                INTEGER PRIMARY KEY,
    jd_id             INTEGER REFERENCES jds(id),
    created_at        TEXT NOT NULL,
    resume_summary    TEXT NOT NULL,
    letter_salutation TEXT,
    letter_closing    TEXT,
    status            TEXT NOT NULL DEFAULT 'applied',  -- applied | interviewing | offer | accepted | rejected | ghosted | withdrawn | not_pursued | offer_declined
    concluded_at      TEXT,          -- ISO datetime (rejected/accepted/offer_declined date)
    applied_at        TEXT,          -- ISO date (when submitted)
    stage             TEXT,          -- application | screen | phone_screen | interview_1..3 | onsite | final | assessment_submitted | offer_received | offer_accepted | declined_offer | rejection
    notes             TEXT,
    source_application_id INTEGER REFERENCES applications(id),  -- which prior application was the tailoring template
    tailoring_notes   TEXT,          -- framing decisions: track, angle, gaps acknowledged, salary noted
    follow_up_date    TEXT,          -- ISO date for next follow-up action
    follow_up_count   INTEGER DEFAULT 0,
    -- ── Offer terms ───────────────────────────────────────────────────────
    -- Columns, not a separate `offers` table: an offer belongs to exactly one
    -- application, and `jds` already carries its own salary columns inline. Two
    -- concurrent offers are two application rows, each with its own terms. What
    -- this shape cannot hold is a renegotiation history on one offer — that goes
    -- in `notes`, which is append-only by convention.
    -- Distinct from jds.salary_min/max (the posted range) and jds.salary_target
    -- (the seeker's ask): these are what was actually put on the table.
    offer_received_at TEXT,         -- ISO date the offer landed
    offer_salary      INTEGER,      -- base salary as offered/accepted
    offer_total_comp  INTEGER,      -- first-year total incl. bonus/equity; NULL if base-only
    offer_currency    TEXT,         -- NULL until an offer exists (cf. jds.salary_currency, which defaults)
    offer_title       TEXT,         -- title as offered; often differs from jds.role
    offer_start_date  TEXT,         -- ISO date
    offer_deadline    TEXT,         -- ISO date to respond by
    offer_notes       TEXT          -- equity, sign-on, PTO, remote terms, level — one field, not eight columns
);

CREATE TABLE IF NOT EXISTS application_bullets (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    bullet_id      TEXT NOT NULL REFERENCES bullets(id),
    position       INTEGER NOT NULL,
    text_override  TEXT    -- NULL = use canonical bullet text
);

CREATE TABLE IF NOT EXISTS application_skills (
    id               INTEGER PRIMARY KEY,
    application_id   INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    skill_id         TEXT NOT NULL REFERENCES skills(id),
    position         INTEGER NOT NULL,
    content_override TEXT    -- NULL = use canonical skill content
);

CREATE TABLE IF NOT EXISTS application_letter_paragraphs (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    position       INTEGER NOT NULL,
    body           TEXT NOT NULL
);

-- ── Interview tracking ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    jd_id           INTEGER REFERENCES jds(id),
    name            TEXT NOT NULL,
    title           TEXT,
    role            TEXT CHECK(role IN ('recruiter','hiring_manager','interviewer','reference','other')),
    interview_date  TEXT,
    interview_time  TEXT,
    interview_stage TEXT,
    notes           TEXT,
    email           TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ── STAR corpus ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    situation    TEXT,
    task         TEXT,
    action       TEXT,
    result       TEXT,
    employer_id  INTEGER REFERENCES employers(id),
    timeframe    TEXT,
    raw_transcript TEXT,
    source_type  TEXT CHECK(source_type IN ('audio','transcript','typed','conversation')),
    source_file  TEXT,
    notes        TEXT,
    readiness    TEXT DEFAULT 'draft',  -- draft | ready | practiced
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    short_version TEXT,          -- condensed one-paragraph telling of the story
    outline      TEXT,           -- bullet outline for quick recall
    lp_tags      TEXT            -- leadership-principle tags (comma-separated)
);

CREATE TABLE IF NOT EXISTS story_themes (
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    theme    TEXT NOT NULL,
    PRIMARY KEY (story_id, theme)
);

CREATE TABLE IF NOT EXISTS story_bullets (
    story_id  INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    bullet_id TEXT NOT NULL REFERENCES bullets(id),
    PRIMARY KEY (story_id, bullet_id)
);

CREATE TABLE IF NOT EXISTS story_interview_use (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id       INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    application_id INTEGER REFERENCES applications(id),
    question_prompt TEXT,   -- "Tell me about a time when..." prompt it answered
    used_at        TEXT,    -- ISO datetime of actual interview use
    outcome_notes  TEXT,    -- how it landed (post-debrief capture)
    created_at     TEXT DEFAULT (datetime('now'))
);

-- ── Assessments ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS assessments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id),
    type           TEXT CHECK(type IN ('tdd','take-home','coding','project','other')),
    description    TEXT,
    url            TEXT,           -- link to the assessment doc/platform
    submission_url TEXT,           -- separate submission link if applicable
    deadline       TEXT,           -- ISO date when due
    submitted_at   TEXT,           -- ISO datetime when submitted
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

-- ── File registry ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS file_registry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    jd_id           INTEGER REFERENCES jds(id) ON DELETE SET NULL,
    application_id  INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    story_id        INTEGER REFERENCES stories(id) ON DELETE SET NULL,
    file_path       TEXT NOT NULL UNIQUE,   -- relative to project root (data/...)
    file_type       TEXT NOT NULL,          -- jd|resume|letter|screen_prep|interview_prep|transcript|recording|questions|notes|research|misc
    summary         TEXT,                   -- 1-2 sentence label
    description     TEXT,                   -- fuller context: why created, what it contains
    file_size       INTEGER,                -- bytes at registration time
    file_mtime      TEXT,                   -- ISO datetime from disk stat
    source_urls     TEXT,                   -- JSON array of URLs this file originated from (e.g. job posting links)
    registered_at   TEXT DEFAULT (datetime('now')),
    source          TEXT DEFAULT 'manual'   -- manual | sync | auto
);

CREATE INDEX IF NOT EXISTS idx_file_registry_jd   ON file_registry(jd_id);
CREATE INDEX IF NOT EXISTS idx_file_registry_app  ON file_registry(application_id);
CREATE INDEX IF NOT EXISTS idx_file_registry_type ON file_registry(file_type);

-- ── Active leads view ─────────────────────────────────────────────────────────
-- A "lead" is a scored/pending JD not yet turned into an application. This view is
-- the single source of truth for lead selection + ordering, consumed by both the
-- web Leads report (JS) and generate_home.write_leads_dashboard (Python).
CREATE VIEW IF NOT EXISTS active_leads AS
    SELECT j.id, j.company, j.role, j.score, j.source, j.url, j.summary,
           j.salary_min, j.salary_max, j.salary_currency, j.lead_status,
           date(j.evaluated_at) AS evaluated
    FROM jds j
    LEFT JOIN applications a ON a.jd_id = j.id
    WHERE j.lead_status IN ('pending', 'approved') AND a.id IS NULL
    ORDER BY (j.score IS NULL), j.score DESC, j.company;
