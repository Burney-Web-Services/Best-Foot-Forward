# evaluate-job

## Purpose
Score a job description 0–100 for fit against the seeker's background, using the live bullet and skills libraries as the ground truth for what's actually on the resume.

## Input
The user provides one of:
- Pasted job description text (as the command argument)
- A local file path (read with the Read tool; supports .txt, .odt, .pdf, etc.)
- A URL (fetch with WebFetch; if fetch fails, ask the user to paste instead). **Keep the URL** — it becomes the lead's clickable posting link.

## Grounding (one path, both machines)
Scoring is always grounded in the **local JSON caches** — the same files on the primary and on a secondary machine:
1. Read `data/_bullets.json` (the complete bullet library) and `data/_skills.json`.
2. Read `data/_education.json`. Credential requirements in a JD are scored *against*
   it, never guessed at — without this in the grounding set a scoring pass has
   invented a "no degree" gap against a requirement the profile already satisfies.
3. Read `memory/user_profile.md` and `memory/project_jobsearch.md` for full career
   context, and `memory/voice_guide.md` for the seeker's own anti-spin phrasing
   rules. The voice guide is optional as a *file* (not every user has run
   `/capture-voice` yet) but not as a *step*: if it doesn't exist, tell the
   subagent explicitly ("no voice guide captured yet") rather than silently
   omitting the topic — a scoring pass with no voice guide in context has drafted
   unsupported "would ramp quickly"-style filler nothing in the profile backs up.
4. Delegate the actual bullet/skill selection and fit analysis to a subagent (see Workflow step 3 below for the exact model and why).

On a **secondary machine** these caches are seeded/refreshed by `/secondary` (which pulls them over MCP from the primary via `get_profile_bundle`). Once seeded, evaluate-job scores identically whether or not the MCP server is currently reachable — no online/offline split for scoring.

## Workflow
1. Read the JD from whichever input form was provided.
2. Ground the scoring per the section above (load full bullet/skills libraries and memory).
3. Spawn a subagent (via `Agent(description="...", prompt="...", model="sonnet", run_in_background: false)`) to score 0–100 across five dimensions (20 pts each). Default model is **Sonnet**. Was Haiku; switched after a side-by-side test on an identical prompt (both with the gap-reporting guardrail below applied) showed Sonnet calibrating scores more defensibly against genuinely missing hard requirements (29/100 with 2/20 technical match, vs. Haiku's notably generous 53/100 and 8/20 for the same zero-overlap JD) and proactively flagging adjacency-conflation risk unprompted — the exact "adjacent skill treated as evidence" failure mode the gap-reporting rules exist to prevent. Evaluation volume is one call per JD, not high-frequency, so the cost delta is immaterial. **If the environment variable `BFF_EVAL_MODEL` is set, use its value as the subagent's `model` instead of `sonnet`** — this exists solely so `tests/uat/compare_eval_models.sh` can re-run this exact comparison later without editing this file; ignore it for a real user's own evaluation:
   - **Technical match** — stack, tools, domain overlap with bullets/skills library
   - **Role/level match** — seniority, scope, and best-fit role title/level interpretation (no fixed track enum)
   - **Domain/industry fit** — sector, problem space, mission alignment
   - **Experience depth** — years, complexity of comparable work
   - **Gap risk** — hard requirements that are missing or thin in the profile (score high when gaps are low)
   
   Pass the full `_bullets.json`, `_skills.json`, `_education.json`, the JD text,
   the memory context, and `memory/voice_guide.md` (or the explicit "no voice
   guide captured" note) to the agent. It returns a summary, dimension scores,
   overall score, top strength, top gap, best framing angle, and
   **`required_skills`** — the technical and credential requirements the posting
   actually names, whether or not the seeker has them. That last field is not
   decoration: it's what `save_lead_jd --skills-json` (below) writes to
   `jd_required_skills`, and it's the only place in the primary flow where a
   requirement the seeker lacks can enter the database at all — see "Gap
   reporting rules" below for how to state it.

### Gap reporting rules — pass these to the subagent verbatim

A gap is a finding, not a problem to be softened. State it and stop.

- **Name the gap in one clause and do not follow it with a reassurance.** "No
  Kubernetes anywhere in the bullet library" is a complete, correct answer. "No
  Kubernetes in the bullet library, though the Docker and Terraform work suggests
  they'd ramp quickly" is not — the second clause is an unsupported prediction
  about the future, which is a fabrication delivered in a friendly tone.
- **Adjacency is not evidence.** Terraform does not evidence Pulumi. Jenkins does
  not evidence GitLab CI. Managing a platform team does not evidence Kubernetes. If
  the profile does not contain the thing, say it does not contain the thing. Do not
  reason from a neighbouring skill to a claim about this one.
- **Banned move — the compensating clause.** Do not attach "but", "though",
  "however", "that said", "the good news is", "strong foundation", "solid grounding",
  "would ramp quickly", "quick study", "hit the ground running", "transferable", or
  "adjacent experience" to a gap. If the seeker asks how bad a gap is, answer then.
  Unasked, don't.
- **Every capability claim names its source.** Any sentence asserting the seeker can
  do something must be traceable to a specific bullet `id` or skill-group `id` from
  `_bullets.json` / `_skills.json`. If you cannot name the id, you cannot make the
  claim — delete the sentence rather than hedging it.
- **`top_gap` is the gap, not the mitigation.** One sentence: the requirement, and
  what the profile has on it (often "nothing"). No plan, no framing, no silver lining.
- **This instruction survives the whole session.** Do not relax it because an earlier
  turn already produced encouraging phrasing, and do not relax it because the overall
  score came out high. A 90-scoring role still gets its gaps stated flat.

Calibration check before returning: a well-formed gap section reads like a diff, not
like a pep talk. If a line would be at home in a recruiter's outreach email, rewrite it.

**Before presenting, re-read the subagent's `top_gap` and gap-risk rationale against
the banned-move list above and strip any compensating clause yourself.** Don't send it
back to try again — this bias re-offends within a single session even after being
corrected once, so re-prompting doesn't fix it. Edit the output; don't renegotiate
with it.

4. Output:
   - **One-paragraph narrative summary of fit** (this becomes the lead's `summary` — keep it self-contained)
   - Table or list of the five dimension scores with one-line rationale each
   - **Overall score** (sum of five dimensions)
   - **Top strength** — the single most compelling match point
   - **Top gap** — the one thing most likely to sink the application
   - **Best framing angle** — recommended track and theme emphasis if the user were to tailor for this role
5. Persist the result immediately after presenting it, per machine role (`BFF_ROLE`):

### Primary machine (`BFF_ROLE=primary` or unset/`standard`) → SQLite

**Step 1 — save the JD text first, for every lead.** Before writing the score, run:
```
python3 -m best_foot_forward.utils.save_lead_jd --company '<Company>' \
    --role '<full role title, punctuation intact>' --url '<url or omit>' --text-file <path> \
    --skills-json '<the subagent's required_skills array from Workflow step 3, as JSON>'
```
Write the raw posting text to a temp file and pass `--text-file` (or pipe it via `--text-file -`); avoid `--text` for anything long. It prints the `jd_id` to use in step 2.

`--skills-json` is what actually gets a requirement the seeker lacks into `jd_required_skills` — omitting it still indexes whatever the shipped lexicon and the seeker's own skills table cover, but the subagent's read of the specific JD is the richer source. Pass the `required_skills` array from the scoring output verbatim; `save_lead_jd` canonicalizes and unions it with the lexicon/profile pass.

This is the step that makes the declined pile analysable. A lead you pass on is never tailored, and the JD file used to be written only *during* tailoring — so every declined lead had no JD text on disk and zero `jd_required_skills` rows, which is why a "what do the jobs I decline have in common?" report could talk about scores and salaries but never about stack. Saving it at evaluation time is the only moment the text is guaranteed to be in hand.

What the helper does, all of which used to be hand-done here and repeatedly went wrong:
- Computes the asset path with `slugify()` and writes `{Company}_{Role_Slug}JobDesc.md` with the standard property block. **The path is never hand-derived.** Hand-built stub paths caused the same silent-duplicate-row bug three times (Teaching Strategies 2026-07-01, Beacon Biosignals 2026-07-02, Pfizer 2026-07-14), and hand-derived slugs diverge on punctuation — notably hyphens, which `slugify()` keeps.
- Resolves or creates the `jds` row via the shared `db.resolve_or_create_jd()`, always with an absolute canonical `file_path`, so a pasted lead and a later tailoring session cannot end up on two different rows.
- Extracts salary and required skills, **filling only** — a salary you set by hand off a sidebar widget is never overwritten by a later parse that finds nothing (the Inductive Automation case).
- Registers the file in `file_registry`, which JD files never were despite the docs claiming otherwise.
- **Never writes `score`, `summary` or `evaluated_at`.** Those belong to step 2. This is also why it does not call `scan_jds.py`: without `--rescan` that skips any file whose row already exists, so it would do nothing at all. (`--rescan` used to also overwrite `evaluated_at` with the scan time, replacing when the lead was **scored** with when it was **scanned**; it now fills that column only when it is NULL. Extraction still belongs here, not to a second pass.)

Store the **full role title with punctuation intact** in `jds.role`; only the *path* is slugified.

If the JD arrived as a file path that is already inside the asset tree, skip step 1 — the text is already saved.

**Step 2 — write the score.** Via Bash `python3 src/best_foot_forward/utils/db_query.py "..."`:
- `UPDATE jds SET score=<score>, evaluated_at=datetime('now'), summary='<narrative>', url=COALESCE(url,'<url or NULL>') WHERE id=<jd_id from step 1>`. Key on `id`, not `file_path` — step 1 already resolved it, and an id cannot be mistyped into a duplicate row.
- This UPDATE deliberately does **not** touch `lead_status` — re-scoring a lead you've already triaged (approved/applied/declined) must not silently reset it to `pending`.
- **Do not set `lead_status` here.** `save_lead_jd` already lands a brand-new lead as `pending` (naming it explicitly on insert, as `scan_jds.py` does, because the schema `DEFAULT` is still `'approved'` and would otherwise auto-approve it), and it leaves an already-triaged lead's status untouched. Writing it again from this step can only get it wrong on a re-score.
- If the record already exists and has a score, overwrite it.
- After the write, log it: `python3 -m best_foot_forward.utils.log_action --actor evaluate-job --action score --entity-type jd --entity-id <jd_id> --details '{"company": "<Company>", "role": "<Role>", "score": <score>}'`
- **Capture the triage decision in the same session.** On the primary you are both evaluator and decider, so once you present the score and the user reacts, record the decision with `triage_lead` (key on the same `file_path` you just wrote). **Do not hand-write the `UPDATE`** — a triage decision writes four columns together (`lead_status`, `lead_decided_at`, `decline_reason`, `decline_category`), and the helper is the one place that keeps them consistent:
  - *Wants to tailor now* → proceed straight to the resume-tailor workflow; `track_application.py` records `applied` itself, so no call is needed here.
  - *Wants it but not right now* → `python3 -m best_foot_forward.utils.triage_lead --file-path '<path>' --status approved` (shows up under "Top open leads to pursue").
  - *Declines it* ('skip this one', 'not a fit', 'pass on this') → **ask for a category, then an optional reason**, then `python3 -m best_foot_forward.utils.triage_lead --file-path '<path>' --status declined --category '<slug>' --reason '<their words>'`.
    - **Category first.** Present the eight options with their glosses, exactly as `triage_lead --help` prints them (`domain`, `stack`, `role_type`, `level`, `comp`, `location`, `strategy`, `other`). Offer your own read as the default — *"Reads like `stack` to me, given the Playwright/TypeScript requirement. Sound right?"* — so it is one keystroke to confirm and easy to override. Never invent one silently.
    - **Layered declines pick the decisive category, not all of them.** Most declines have more than one cause; store the one that actually decided it and let `--reason` carry the rest. Interra Health was stack *and* role_type *and* level; `stack` was the wall.
    - **`strategy` is not `other`.** Use `strategy` when nothing was wrong with the posting and the seeker is spending the effort elsewhere ("I'd rather chase the one they just rejected me for"). Use `other` only when none of the seven fit. The Decline Patterns report counts `strategy` separately from market signal, so miscoding one as the other distorts the whole roll-up.
    - **Then the reason,** plainly and once — *"Anything to add in your own words? (Enter to skip.)"* If they confirm the top gap, record that gap in a short phrase; if they give their own reason (salary, commute, company reputation, gut, a contact's tip), record **their** wording, not a paraphrase of the fit analysis. If they don't answer or wave it off, run the command without `--reason` rather than inventing one. A category with no reason is fine and common.
    - `decline_reason` is the seeker's voice, `decline_category` is the groupable form of the same decision, and `summary` is yours (the fit analysis). Keeping all three separate is the point — it's what lets a later report distinguish "I keep declining support roles" from "these roles kept scoring low."
  - **Offer to capture the posting URL before recording a non-`applied` decision.** If `jds.url` is NULL for this lead (typical when the JD arrived as pasted text rather than a URL), ask once: *"Want to add the posting link so you can revisit this later? (Enter to skip.)"* Recommended, never required — a declined lead is kept precisely so it can be reconsidered, and without a URL there is nothing to reopen, since a lead that is never tailored has no JD file on disk either. If they give one, write it before triaging: `UPDATE jds SET url='<url>' WHERE file_path='<path>'`. If they skip, proceed; do not ask again.
  - A **declined lead is kept, not deleted** — the row, score, summary, category and reason stay in the DB so the analysis remains queryable. `declined` is a first-person decision by the seeker; it is distinct from `applications.status='rejected'`, which means a company rejected *you*.
  - *Re-triaging an already-declined lead to add detail* (a category on an older decline) → pass `--decided-at '<its existing lead_decided_at>'`, and re-pass its existing `--reason`. A re-triage overwrites all four columns by default, so omitting them restamps the decision as today and blanks a reason already on record.
  - *Undecided / no clear signal* → leave it `pending`. Don't call the helper at all; `pending` means no decision has been made, and stamping a decision date on a non-decision defeats the column.
  A lead therefore only stays `pending` when it is genuinely untriaged — chiefly leads pushed by a secondary sourcer that the seeker hasn't reviewed yet — so the pending list stays a real triage inbox rather than a dumping ground for everything ever scored.
- **Refresh the dashboards after any lead-status change.** Whenever this flow lands a new lead or flips a `lead_status` (pending / approved / declined), run `python3 -m best_foot_forward.utils.generate_home` so the Home glance and the `Leads Dashboard` / `Declined Leads` / `Applications Dashboard` pages reflect it immediately. Unlike resume-tailor (whose `on_application` hook already runs `generate_home`), evaluate-job has no PostToolUse hook, so this refresh is a manual step in the workflow — skip it only if the write didn't change any lead state. (If the seeker instead triages a lead later via the `triage_lead` commands printed by the CLI leads/declined reports, those runs won't auto-refresh either; the dashboards catch up on the next `generate_home` run or application.)

### Secondary machine, MCP reachable (`BFF_ROLE=secondary`, online) → push live
Call the `best-foot-forward` MCP tool **`sync_leads`** with a one-element `leads` array. Include every field you have:
```json
{ "company": "...", "role": "...", "score": 72,
  "salary_min": 180000, "salary_max": 210000, "salary_currency": "USD",
  "url": "https://...", "summary": "<the one-paragraph narrative>",
  "required_skills": ["Python", "distributed systems"],
  "evaluated_at": "2026-07-18T14:30:00", "source_urls": ["https://..."] }
```
The lead lands on the primary as `lead_status='pending'`, attributed to your authenticated source (e.g. `alex`). Report the tool's `imported/updated/skipped` line back to the user. No staging file.

### Secondary machine, MCP unreachable (`BFF_ROLE=secondary`, offline) → local #Lead page
Write a `#Lead` page into the **local `bff-leads` graph** via the `markdown-graph` MCP tool `write_page` (graph `bff-leads`, page title `{Company}/{Role}/Lead`). Properties:
```
type:: #Lead
company:: [[{Company}]]
role:: {role}
score:: {score}
lead-status:: pending
source:: secondary
salary-min:: / salary-max:: / salary-currency::
url:: {url}
evaluated:: [[YYYY/MM/DD]]
pushed:: false
```
Body: `## Summary` (the narrative), `## Required skills` (comma-joined), and `## Posting` with `[Open posting]({url})`. These queue until `/push-leads` drains them to the primary when the MCP server is reachable again. Confirm: "Lead queued locally in bff-leads (pushed:: false). Run /push-leads when back online."

## Notes
- Do not fabricate experience. Score only against what exists in the bullet/skills caches and memory.
- Be honest about gaps. Calibration is a property of the *score* — it must reflect the evidence in both directions. It is not a licence to soften the *language* around a gap. See "Gap reporting rules" above.
- If the file path points to a folder rather than a file, list the folder contents and ask the user to clarify.
- To tell online from offline on a secondary: attempt a cheap MCP call (e.g. `get_career_profile`); if it errors/times out, you're offline — use the local #Lead path.
