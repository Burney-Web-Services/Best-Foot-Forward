# intake-artifacts

## Purpose
Bulk-add achievement bullets and skills to an existing BFF profile by mining codebase artifacts: git logs, PR descriptions, architecture docs, and performance reviews. Use this after initial onboarding to enrich your bullet library from work you're currently doing.

Distinct from `/onboard` (which builds the profile from scratch) — this skill assumes the database is already populated and you want to add more bullets from ongoing work.

---

## When to use
- You've started a new role and want to capture it in BFF before it fades
- You completed a major project and want to document it while it's fresh
- Your resume was last updated a while ago and you have artifact evidence of recent work
- Your manager review or performance eval just happened and it surfaced good material

---

## Inputs

The user provides one or more of the following (paste directly into the chat):
- Recent git log: `git log --oneline -100` or `git log --oneline --since="6 months ago"`
- PR or MR descriptions (paste 5–10 from your most impactful work)
- Architecture docs, RFCs, ADRs, or design decisions you authored
- Performance review text or self-evaluation
- Jira/Linear epic or issue summaries
- Sprint retrospective notes

---

## Workflow

### Step 1 — Establish context

Before reading any artifacts, ask:
1. What employer is this work from? (confirm it matches an existing employer in the database)
2. What role title should these bullets be filed under?
3. What track tags are most relevant for this material? (free text — e.g., "engineer", "manager", "architect", "derive from content", etc.)
4. How recent is this material? (approximate date range)

Read `data/_employers.json` to confirm the employer exists. If not, note it — the user will need to add the employer to SQLite before import.

---

### Step 2 — Artifact extraction pass

For each artifact set provided, read through and identify significant contributions. Focus on:

- Shipped features or systems (especially customer-facing or high-impact)
- Performance or reliability improvements (with before/after if detectable)
- Architecture decisions or technical leadership
- Team or process improvements
- Incident response or reliability work
- Cross-team collaboration or influence
- Mentorship or people development (for manager track)

For each significant item identified, draft a candidate bullet and ask a targeted follow-up to get the metric:
- "I see [X] — do you know the quantified impact? (latency, cost, error rate, test coverage, users affected?)"
- "This [PR/commit/doc] looks significant — was this something you led, or were you a contributor?"
- "How long did this take, and was it on schedule?"

Do not draft a bullet without at least one of: outcome, metric, scale, or explicit impact statement. If the artifact doesn't contain enough, ask before writing.

---

### Step 3 — Bullet finalization

Present the candidate bullets as a numbered list. For each:
- Show the drafted text
- Show the proposed track(s) and theme(s)
- Ask: "Keep as-is / edit / skip?"

For any user edits, incorporate and re-present before finalizing.

---

### Step 4 — Skills audit

After bullets are finalized, scan the artifacts for skills or tools that appear frequently but may not be in the skills library. Prompt:
- "I noticed [X] used throughout — is that in your skills list?"
- Read `data/_skills.json` to check. If missing, draft a new skill group entry with label, content, tracks, and themes.

---

### Step 5 — Write to SQLite

For each confirmed bullet, run:

```bash
python3 src/best_foot_forward/utils/db_query.py "INSERT OR IGNORE INTO bullets (id, employer_id, role, text) VALUES ('<id>', (SELECT id FROM employers WHERE name='<employer>'), '<role>', '<text>')"
python3 src/best_foot_forward/utils/db_query.py "INSERT OR IGNORE INTO bullet_tracks (bullet_id, track) VALUES ('<id>', '<track>')"
python3 src/best_foot_forward/utils/db_query.py "INSERT OR IGNORE INTO bullet_themes (bullet_id, theme) VALUES ('<id>', '<theme>')"
```

Bullet ID convention: `{employer-slug}-{zero-padded-sequence}` where the slug is the first word of the employer name, lowercased, alphanumeric only (e.g., "Kuat Drive Yards" → `kuat`, bullet #7 → `kuat-007`). Check the existing bullet IDs for that employer first to determine the next sequence number:

```bash
python3 src/best_foot_forward/utils/db_query.py "SELECT id FROM bullets WHERE employer_id = (SELECT id FROM employers WHERE name='<employer>') ORDER BY id"
```

For each confirmed new skill group:

```bash
python3 src/best_foot_forward/utils/db_query.py "INSERT OR IGNORE INTO skills (id, label, content) VALUES ('<id>', '<label>', '<content>')"
python3 src/best_foot_forward/utils/db_query.py "INSERT OR IGNORE INTO skill_tracks (skill_id, track) VALUES ('<id>', '<track>')"
```

Skill ID convention: `skills-{slug}` where the slug is the label lowercased with spaces replaced by hyphens, trailing colon removed (e.g., "AI & Product Engineering:" → `skills-ai-product-engineering`).

After all inserts, regenerate the caches:

```bash
python3 src/best_foot_forward/utils/export_cache.py
```

---

### Step 6 — Summary

Report:
- Number of bullets added (by employer and track)
- Number of new skill groups added
- Updated bullet count by track (read from the regenerated cache)

Suggest:
> "Good stopping point — worth running `/cleanup` then `/compact` before we continue."

---

## Notes

- Do not fabricate metrics. If the user doesn't know the number, write the bullet without it and note it for later ("impact TBD — ask your manager or check the dashboard").
- Bullets should be achievement-oriented, not task-oriented. "Reduced error rate from 4% to 0.3%" beats "Fixed error handling in the payment service."
- If the artifact reveals a significant incident or recovery, capture it — incident response bullets are strong for both engineer and manager tracks.
- This skill does not modify the base resume files in `data/resumes/`. After adding bullets, use `/resume-tailor` to incorporate them into a tailored application.
