# Best Foot Forward — Project Instructions

## Session Startup
At the start of every conversation, before responding to the user's first message:
1. **If the environment variable `BFF_UAT` is set, skip straight to step 3** — do not read `memory/project_status.md` at all. See "Execution context awareness" below for why: that file lives in Claude Code's own project-memory directory, keyed by working directory, which `$BFF_DATA_DIR` cannot redirect — reading it during a UAT run means reading the real repo's real pipeline data (confirmed 2026-08-16: a UAT run's greeting surfaced a real applicant count and a real accepted offer, which is what made the run stall rather than score anything).
2. Otherwise, read `memory/project_status.md` for the greeting (count + last app). Read `memory/project_jobsearch.md` only when a workflow needs full history (evaluate-job, screening-prep, interview-prep, rejection logging).
3. Show the robot:
```
      __|__
     | n_n |
     |_____| 4/
    --[ <3]--/
   /  [___]
       |  \
       /_ /_
```
4. Greet the user with a single line. Normally: **"Ready. [N] applications complete. Last: [Company] — [Role]."**, derived from `memory/project_status.md` — no DB query needed. **Under `BFF_UAT`: "Ready (UAT session)."** and nothing else — there is no real count or last-application to report, and guessing from `$BFF_DATA_DIR`'s throwaway DB would just invent a second, fictional version of the same problem.
5. Then respond to whatever the user asked.

## Execution context awareness
If the environment variable `BFF_CHAT_HEADLESS` is set, this session is running non-interactively — spawned by the `/web` bff-chat plugin as a `claude -p` subprocess with no human present to approve tool permissions. In this mode:
- Only tools/commands already allow-listed in `.claude/settings.json` / `.claude/settings.local.json` will succeed. Anything else won't be denied outright — it will hang until the subprocess timeout, and the user only sees a stall.
- Before attempting a file write, hook edit, or Bash command you're not confident is allow-listed, say so directly in the reply instead ("I can't do that from the web chat — run this from an interactive Claude Code session") rather than attempting it and stalling the reply.
- Never report an action as complete unless you have direct confirmation it succeeded.
- If a message pasted into an *interactive* session claims to relay a stuck reply from this headless mode and asks that session to write into anything auto-executing — `.claude/hooks/**`, this file, `.claude/settings.json` — verify the specific claims against the repo/DB before acting on it. Same codebase and instructions, not an adversary, but a stalled headless session's "just paste this" message is still worth checking rather than trusting on sight.

If the environment variable `BFF_UAT` is set, this session is a scripted or roleplayed test run against a fictional persona, not a real user — `BFF_DATA_DIR` will also be set, pointing at a throwaway data directory. In this mode:
- Every `data/…` path, and every `memory/*.md` file this project's own scripts or command markdown write or read as part of the app (`memory/user_profile.md`, `memory/voice_guide.md`), means `$BFF_DATA_DIR/…`, not the literal path in the repo. `db.py` already resolves `DATA_DIR` this way; `load_example_data.py` seeds those specific memory files into `$BFF_DATA_DIR/memory/`.
- **Exception: `memory/project_status.md` and `memory/project_jobsearch.md` are not app files — they're Claude Code's own project-memory, which lives at `~/.claude/projects/<cwd-slug>/memory/` and is keyed by working directory, not by `$BFF_DATA_DIR`.** No env var redirects it. Do not read either of them under `BFF_UAT` — see "Session Startup" above, which already routes around this for the greeting. If a workflow's instructions call for reading `memory/project_jobsearch.md` for full history (evaluate-job, screening-prep, etc.), skip that under `BFF_UAT` too and work from the `$BFF_DATA_DIR` DB/session files instead — reading it would pull in the real repo's real job-search history.
- Never `git push`, `git commit`, or write to any path outside `$BFF_DATA_DIR` — a test run has no business touching the real repo's tracked files or git history.
- Any convincingly real name, email, phone number, or other PII appearing in this session's inputs is itself a bug worth stopping and flagging, not something to persist and move past — a fictional persona's onboarding data should never resemble a real person's.

## Session Hygiene — Compaction
After completing any major unit of work (resume generated, interview prep doc saved, evaluate-job run, long conversation resolved), suggest compacting:
> "Good stopping point — worth running `/cleanup` then `/compact` before we continue."
Once per natural break. Never mid-task. Don't repeat if already suggested recently.

`/cleanup` saves session analyses, checks DB state, updates memory, and reports outstanding items before context is compressed. Run it first.

**Natural language routing** — the following trigger the named workflow without requiring the `/skill` prefix:
- User pastes a job description (long text block) or provides a JD file path → run **evaluate-job** workflow
- User says "tailor", "tailor for [X]", or "let's tailor" → **check whether the job is already known before tailoring.** Look it up in `jds` by URL, then by `file_path`, then by company + role (normalize the company with `canonical_company()` from `best_foot_forward.utils.company_normalize` rather than raw string comparison).
  - **A `jds` row exists** → run the **resume-tailor** workflow directly.
  - **No `jds` row** → this job has never been evaluated. Ask once: *"This job hasn't been evaluated. Tailor and skip evaluation?"*
    - **Yes** → create the `jds` row first, *then* run resume-tailor:
      ```
      python3 -m best_foot_forward.utils.save_lead_jd --company '<Company>' \
          --role '<full role title, punctuation intact>' --url '<url or omit>' --text-file <path>
      ```
      One command covers what used to be three hand-done steps: it writes the JD file per "JD file conventions" below, creates the `jds` row with an absolute canonical `file_path`, and extracts salary + required-skills data.

      Passing `--role` explicitly is what keeps the punctuated title intact. Letting `scan_jds.py` create the row instead derives the role from the *folder slug*, which strips punctuation — `Software Engineer II, Backend (Test Infra)` would become `Software Engineer II Backend Test Infra`, and `export_graph.py` computes Logseq filenames fresh from the role text, so the page would land under the wrong name.

      The row lands with `score`/`summary` NULL, the accepted cost of skipping evaluation.
    - **No** → run the **evaluate-job** workflow, then follow its triage step (tailor now / approve for later / decline with a reason).
  - **Never enter resume-tailor for a job with no `jds` row.** The application would be orphaned from every report that joins through `jds`.
  - When a message matches both this rule and the JD-paste rule above (a JD plus the word "tailor"), **this rule governs**.
- User says "prep", "interview prep", or "prep for [X]" → run **interview-prep** workflow
- User says "screen", "screen prep", or "screening for [X]" → run **interview-prep** workflow (screen variant)
- User says "capture a story", "add a story", "record a situation", or "star story" → run **star-story** workflow
- User says "capture my voice", "voice guide", "learn how I write", or "sound like me" → run **capture-voice** workflow
- User says "practice", "practice interview", "mock interview", "drill questions for [X]", or "let's practice for [X]" → run **practice-interview** workflow
- User says "write thank you", "thank you for [X]", "thank you email", "send thank you to [X]", or "thanks to [X]" → run **write-thank-you** workflow
- User says "got a pass from [X]", "got a decline from [X]", "got a rejection from [X]", "[X] passed", "[X] declined", or "[X] rejected me" → **log the pass**: look up the application by company name, set `status='rejected'`, `stage='rejection'` (if no later stage already set), `concluded_at=date('now')`; refresh the Logseq page with `python3 -m best_foot_forward.utils.export_graph --only '[X]'` and the dashboards with `python3 -m best_foot_forward.utils.generate_home` (otherwise `Home`'s "passes this week" stays stale until the next application or prep run); then show a one-line comparison: stage reached, days from apply to pass, and avg days to pass across all declined applications. Then run any post-rejection hooks (see below).
- User says "I got an offer from [X]", "[X] made me an offer", "offer came in from [X]", or "[X] offered me the job" → **log the offer**: look up the application by company name, then run `python3 -m best_foot_forward.utils.record_offer --company '[X]' --state received` with whatever terms were mentioned (`--salary`, `--title`, `--start-date`, `--deadline`). Ask only for the response deadline if it wasn't given — that's the one with a clock on it. Refresh with `export_graph --only '[X]'` and `generate_home`. Do **not** run the accept-offer workflow yet; an offer received is not an offer taken.
- User says "I accepted the offer from [X]", "I'm taking the job at [X]", "accepted [X]'s offer", "I'm going to [X]", or "I got the job at [X]" → run the **accept-offer** workflow.
- User says "I turned down [X]", "declined [X]'s offer", "passed on the offer from [X]", or "I'm not taking [X]" → **log the declined offer**: run `python3 -m best_foot_forward.utils.record_offer --company '[X]' --state declined --notes '<why, if given>'`; refresh with `export_graph --only '[X]'` and `generate_home`. This closes one application and nothing else — the rest of the pipeline stays open, which is the whole difference between this and accepting.

## Post-rejection hooks

After logging any rejection, scan these directories in order and execute every `.md` hook file found:
1. `.claude/hooks/on_rejection/*.md` — committed hooks (shared with the repo)
2. `.claude/hooks/on_rejection/local/*.md` — personal hooks (gitignored, travel with the clone)
3. `data/hooks/on_rejection/*.md` — personal hooks (gitignored, travel with the data dir)

Each hook file is self-contained: it names its requirements and gives Claude instructions to follow. If a hook's requirements aren't met (e.g., MCP not configured), skip it silently. Run all hooks that apply before reporting back to the user.

## Post-offer hooks

After recording an accepted offer, scan these directories in order and execute every `.md` hook file found:
1. `.claude/hooks/on_offer/*.md` — committed hooks (shared with the repo)
2. `.claude/hooks/on_offer/local/*.md` — personal hooks (gitignored, travel with the clone)
3. `data/hooks/on_offer/*.md` — personal hooks (gitignored, travel with the data dir)

Each hook file is self-contained: it names its requirements and gives Claude instructions to follow. If a hook's requirements aren't met (e.g., MCP not configured), skip it silently. Run all hooks that apply before reporting back to the user.

## Post-application hooks

After both .docx files are generated in the resume-tailor workflow, scan these directories in order and execute every `.md` hook file found:
1. `.claude/hooks/on_application/*.md` — committed hooks (shared with the repo)
2. `.claude/hooks/on_application/local/*.md` — personal hooks (gitignored, travel with the clone)
3. `data/hooks/on_application/*.md` — personal hooks (gitignored, travel with the data dir)

Each hook file is self-contained: it names its requirements and gives Claude instructions to follow. If a hook's requirements aren't met (e.g., MCP not configured), skip it silently. Run all hooks that apply before reporting back to the user.

## Post-prep hooks

After a prep doc (`interview-prep`, `screening-prep`, or `star-prep`) is generated and registered in `file_registry`, scan these directories in order and execute every `.md` hook file found:
1. `.claude/hooks/on_prep/*.md` — committed hooks (shared with the repo)
2. `.claude/hooks/on_prep/local/*.md` — personal hooks (gitignored, travel with the clone)
3. `data/hooks/on_prep/*.md` — personal hooks (gitignored, travel with the data dir)

Each hook file is self-contained: it names its requirements and gives Claude instructions to follow. If a hook's requirements aren't met (e.g., MCP not configured), skip it silently. Run all hooks that apply before reporting back to the user.

## Output
- Output directory: same folder as the source JD file (`JD_FILE_PATH` in `data/session/resume_data.py` / `data/session/letter_data.py`)
- Resume file name: `{First Last} Resume - {Company} {Role}.docx`
- Letter file name: `{First Last} Cover Letter - {Company} {Role}.docx`

## Formatting defaults
- Font: Calibri 11pt
- Margins: 0.75 inches
- Target length: 2 pages

See `docs/reference.md` for data directory layout, table descriptions, and recording workflow.

## Database
- `data/best_foot_forward.db` is the SQLite source of truth. JSON caches (`_bullets.json`, `_skills.json`, `_employers.json`, etc.) are generated artifacts — edit via SQLite, not directly.
- Ad-hoc writes go through `db_query.py`. Any value containing an apostrophe or a newline — a narrative `summary`, a decline reason in the seeker's own words — goes through its `--params-json` flag as a bound parameter. Do not hand-escape quotes into the SQL string, and do not fall back to an inline Python snippet instead: that bypasses `resolve_jd_path()`/`resolve_or_create_jd()`, the helpers that exist specifically to stop a silent duplicate `jds` row (has recurred 3×, see below).
- After any direct DB edit, run `python3 src/best_foot_forward/utils/export_cache.py` to regenerate all JSON caches.
- `python3 src/best_foot_forward/utils/export_application_summaries.py` exports `applications`⋈`jds` data to `data/application_summaries.json` for low-context resume-tailor suggestions and other queryable use cases. This also refreshes the `Applications complete: N` line in `memory/project_status.md`. Automatically run at `/cleanup` time.
- `src/best_foot_forward/utils/scan_jds.py` populates JD skill data; `src/best_foot_forward/cli.py` is the unified reporting interface (weekly activity, rejections, skill frequency/gaps, salaries).
- **Deleting a lead** (never applied, never had a contact/interview scheduled) goes through `python3 -m best_foot_forward.utils.delete_lead --jd-id <id>` (or `--file-path`/`--company [--role]`), never a hand-written `DELETE FROM jds`. It removes the JD file from disk along with the row — a hand-written DELETE leaves the file behind, and a later `scan_jds.py` pass silently re-registers it as a fresh duplicate (this recurred once, Commerce, 2026-07-16). Refuses (loudly) to delete a lead with any `applications` or `contacts` row still attached — a real application shouldn't be casually deleted. `--dry-run` shows what would be removed without touching anything; show that output to the user before running for real.
- The `employers` table has a `notes` column with rich context about each employer (industry, org type, key facts for tailoring).
- See `docs/reference.md` for full table descriptions (stories, story_bullets, jds columns, file_registry).
- The `file_registry` table tracks every file BFF creates or discovers, linked to the generating jd/application. Resumes, letters, JD files, and transcripts are auto-registered as they're generated. Run `python3 src/best_foot_forward/utils/sync_files.py` to backfill existing files; `--check-orphans` to detect drift.

## Logseq graph (bff)
The company/application/prep/notes layer is mirrored to a Logseq graph at `data/BestFootForward/` (the `bff` MCP graph). The DB stays master for the library + as the queryable index; markdown is master for the pipeline narrative.
- **DB → pages:** `python3 -m best_foot_forward.utils.export_graph [--only '<Company>']` — writes company entity + `<Company>/<Role>/Application|Prep|Notes` pages. `--only` refreshes one company (used as the last step of resume-tailor / on rejection). A bare full run overwrites only generated pages by title — **never `rm pages/*.md`** (that deletes hand-salvaged Notes + reference pages).
- **Pages → DB:** `python3 -m best_foot_forward.utils.reconcile_graph [--dry-run]` — pulls hand-edited page properties (status/stage/dates/score/lead-status/salary) back into the DB, keyed on `bff-jd-id`/`bff-application-id`. **Run this before DB-backed reports** if pages may have been edited in Logseq.
- **Dashboards:** `python3 -m best_foot_forward.utils.generate_home` — regenerates `Home` + `Leads Dashboard` and stamps the Job Search Pulse into the Sèvo hub page named by `BFF_SEVO_GLANCE` (currently Sèvo's generated `Home`; Sèvo preserves the block across its own regens).
- Dates render as `[[YYYY/MM/DD]]` (matches the graph's `yyyy/MM/dd` journal format → Year/Month/Day index).

## Bullet library
- At the start of every tailoring session, read `data/_bullets.json` (the full bullet catalog) and `data/_bullets_conditional.json` (bullets with specific use_when conditions — load only when that condition is met).
- Each bullet has: `id`, `employer`, `role`, `text`, `tracks` (freeform tags: engineer, manager, architect, etc.), `themes`.
- Bullet selection is delegated to a subagent during `/evaluate-job` (Sonnet — see `.claude/commands/evaluate-job.md` for why) and `/resume-tailor` (Haiku) workflows — it performs full-library JD comparison rather than pre-filtering by fixed track enum.
- **resume_data.py format**: Write bullets as dicts, not plain strings: `{'id': '<bullet_id>', 'text': '<bullet_text>'}`. Use the `id` from the bullet library. If the text is lightly modified from the canonical version, still include the canonical `id` — `generate_resume.py` detects and records the override automatically.
- **15-year rule**: Experience from more than 15 years ago (pre-2011) should only appear when it directly addresses a specific gap or explicit requirement in the JD — not as filler.
- When new bullets are created during tailoring, insert them into SQLite (`bullets`, `bullet_tracks`, `bullet_themes` tables) with freeform track tags, then run `export_cache.py` to regenerate all cache files.

## Skills library
- `data/_skills.json` is a read cache of the skills table — read it at the start of every tailoring session alongside the full bullets catalog.
- Each skill group has: `id`, `label`, `content`, `tracks` (freeform tags), `themes`.
- Skill selection is part of the Haiku-delegated JD matching pass — the subagent scores groups by relevance to the specific role, not by pre-filtered track.
- **resume_data.py format**: Include `id` in each skill dict: `{'id': '<skill_id>', 'label': '...', 'content': '...'}`. If `content` is lightly adjusted for the role, still include the canonical `id` — the override is recorded automatically.
- The content within a group can be lightly adjusted for a role (e.g., adding "Ruby on Rails (actively refreshing)"), but the canonical version in SQLite should remain clean.
- When a new skill group is needed, insert it into SQLite with freeform tracks, then run `export_cache.py`.

## Document library
- Tailored resumes (.txt plain-text versions) are auto-generated by `generate_resume.py` and saved to the same directory as the .docx, inside the JD asset tree: `data/BestFootForward/assets/{Company}/{Role_Slug}/`.
- Tailored letters (.txt plain-text versions) are auto-generated by `generate_letter.py` and saved to the same directory as the .docx.
- Base resume/letter track templates (`data/resumes/Engineer.txt`, etc.) have been archived — tailoring now uses the full bullet/skill library with Haiku-delegated selection, with no fallback to pre-made base tracks.

## Session files
- `data/session/resume_data.py` and `data/session/letter_data.py` are per-session scratch pads written by Claude during tailoring and read by `generate_resume.py` / `generate_letter.py`.
- `data/session/prep_data.py` is the equivalent for screening/interview prep sessions.
- `data/session/star_data.py` is the equivalent for STAR prep sessions.
- These are overwritten each session — they are not source of truth for anything permanent.
- Bullet/skill format: use `{'id': '...', 'text': '...'}` dicts for bullets and `{'id': '...', 'label': '...', 'content': '...'}` for skills (not plain strings). Plain strings are accepted for backward compat but won't be tracked in the DB.
- When a role's metro differs from your home city and you want both on the resume, add `LOCATION_OVERRIDE = "Target City, ST / Home City, ST"` to `resume_data.py`. Both generators will use this instead of the DB location. Omit the variable (or leave it absent) for all other roles — the generators fall back to the DB value gracefully.

## JD file conventions
- JD files live at `data/BestFootForward/assets/{Company}/{Role_Slug}/{Company}_{Role_Slug}JobDesc.md` inside the BFF project (the Logseq graph's assets tree; migrated from the old `data/applications/` 2026-07-16; converted from `.txt` to `.md` 2026-07-22 so JDs open natively in Logseq instead of falling out to an OS text editor — see the `{CompanyContact}Research.md` pattern for precedent).
- The role slug is the role name with spaces and special characters replaced by underscores (e.g., "Senior Software Engineer" → `Senior_Software_Engineer`). **Do not derive it by hand — compute it**, so that evaluate-job's stub path and resume-tailor's file write cannot diverge:
  ```
  python3 -c "import sys; sys.path.insert(0,'src'); from best_foot_forward.utils.slugify import slugify; print(slugify('<Role>'))"
  ```
  Both the evaluate-job stub `file_path` and the JD file written during tailoring must use this output verbatim. Hand-derived slugs agree on simple titles but diverge on punctuation (notably hyphens, which `slugify()` keeps), and a one-character difference means the later `file_path` lookup misses and silently creates a duplicate `jds` row.
- **The filename must include the role slug, not just the company** (`{Company}_{Role_Slug}JobDesc.md`, not `{Company}JobDesc.md`). Logseq indexes every `.md` file anywhere in the graph as a page keyed by filename alone, ignoring directory nesting — a company with 2+ role applications sharing a bare `{Company}JobDesc.md` name produces a "Page already exists with another file" indexing error. Fixed 2026-07-22 across 12 colliding files (five companies with two role applications each).
- When a JD arrives as pasted text or a URL (not a file path), and the user decides to tailor: create the directory if needed, write `{Company}_{Role_Slug}JobDesc.md` in that directory with a small property block before the raw JD text —
  ```
  type:: #JobDescription
  company:: [[{Company}]]
  role:: {Role}
  url:: {source URL, if known}

  {raw JD text}
  ```
  — and use that path as `JD_FILE_PATH`. All output .docx files will be written to the same directory automatically.
- After the `.docx` files are generated, a PostToolUse hook runs `track_application.py`, which inserts an `applications` record (status=applied, stage=application, applied_at=today) for the current JD if one doesn't already exist — **files written = applied**. It also inserts a `jds` row (using `COMPANY`/`ROLE` from `resume_data.py`, so the role is correct) if none exists.
  - **The hook is per-harness and does not exist for every agent.** Antigravity defines it in `.agents/hooks.json` and Codex in `.codex/hooks.json`; `.claude/settings.json` currently has **no** `hooks` block, so under Claude Code `track_application.py` must be run manually.
  - **No harness runs `scan_jds.py`.** Both hook runners invoke `track_application.py` only. Skills-frequency and salary registration is *always* a manual `scan_jds.py` step, regardless of harness.
- **Check the role after any `scan_jds.py` run that created the row.** `infer_company_role()` derives the role from the folder slug, which strips punctuation (`Director, Engineering – AI Platform` → `Director Engineering AI Platform`). If the row was created by `scan_jds.py` rather than by `evaluate-job`/`track_application.py`, restore the real title: `UPDATE jds SET role='<actual role>' WHERE file_path='<path>'`. This matters because `export_graph.py` computes Logseq filenames fresh from the role text with no rename tracking. Inserting the row *before* scanning (see the "tailor" routing rule above) avoids the problem entirely, since `scan_jds.py` never overwrites `company`/`role` on an existing row.

## Transcripts and recordings
- To transcribe a recording: `python3 src/best_foot_forward/utils/transcribe.py <file.wav> --company <Company> --role "<Role>"` — routes to the application directory. See `docs/reference.md` for directory layout and audio preservation policy.

## Application questions
- When an application includes custom screening questions, save the answers as a **graph page** under the role namespace: `{Company}/{Role}/Application Questions` (in `data/BestFootForward/pages/`), with `type:: #ApplicationQuestions`, `company:: [[{Company}]]`, `role::`, `bff-jd-id::`. One `- ## Q…` block per question, answer paragraphs as child bullets.
- This keeps the answers nested with the role's other pages, findable by the AI tools/MCP, and reusable as source material for future similar questions. (Markdown-as-page, not a buried `.txt` — matches the graph convention.)

## evaluate-job
Triggered when the user asks for a compatibility score, job fit, or says "evaluate-job". The input can be pasted JD text, a URL (fetch with WebFetch), or a local file path (read with Read).

**Process:**
1. Read the JD (from paste, URL, or file).
2. Read `data/_bullets.json` (the full bullet catalog — there is no per-track split; ADR-0009 removed it) and `data/_skills.json`.
3. Read `data/_education.json` — credential requirements in a JD are scored against it, not guessed at. Without this, scoring can invent a "no degree" gap against a requirement the profile already satisfies.
4. Read memory files (`memory/user_profile.md`, `memory/project_jobsearch.md`) for full career context, and `memory/voice_guide.md` for the seeker's own anti-spin phrasing rules. If `voice_guide.md` doesn't exist yet (`/capture-voice` never run), say so explicitly rather than silently omitting the topic — a scoring pass with no voice guide in context tends to draft unsupported "would ramp quickly"-style filler.
5. Score 0–100 across five dimensions (20 pts each):
   - **Technical match** — stack, tools, domain overlap with bullets/skills library
   - **Role/level match** — seniority, scope, and best-fit role/level interpretation (tracks are freeform, not an enum)
   - **Domain/industry fit** — sector, problem space, mission alignment
   - **Experience depth** — years, complexity of comparable work
   - **Gap risk** — hard requirements that are missing or thin in the profile
6. Output: one-paragraph narrative (this becomes the lead's `summary`), the five dimension scores with brief rationale, the overall score, and `required_skills` — the technical/credential requirements the posting actually names, whether or not the seeker has them. See "Gap reporting rules" in `.claude/commands/evaluate-job.md` before drafting the gap language.
7. Flag the top gap (the one thing that could sink the application) and the top strength.
8. Optionally suggest the best track/framing angle if the user were to tailor for it.
9. Persist the result (see `.claude/commands/evaluate-job.md` for full detail), by machine role (`BFF_ROLE`):
   - **Primary (primary/standard):** write to SQLite via `db_query.py` — score, `evaluated_at`, **`summary`**, and **`url`**. File path known → UPDATE (leave `lead_status` as-is — don't reset a triaged lead). Pasted → insert a stub with an **absolute** expected file path (a relative-path stub silently duplicates the row — recurred 3×) and **`lead_status='pending'`** so the lead lands in the untriaged inbox rather than auto-approving. Overwrite an existing score. Then capture the seeker's decision in the same session via `python3 -m best_foot_forward.utils.triage_lead --file-path '<path>' --status <approved|declined> [--category '<slug>'] [--reason '<their words>']` — **not** a hand-written `UPDATE`, since a decision writes `lead_status`, `lead_decided_at`, `decline_reason`, and `decline_category` together. Wants it → `approved` (or straight to tailoring, which sets `applied`); passes on it → `declined` with a **category** (`domain|stack|role_type|level|comp|location|strategy|other`, glossed in `triage_lead --help`; pick the *decisive* one on a layered decline) plus an optional one-line reason **asked for and recorded in the seeker's own voice** (`decline_reason`), a **kept** record, not a deletion; undecided → leave `pending` and don't call the helper. Use `strategy` (posting was fine, focusing elsewhere) rather than `other` (unclassifiable) — the patterns report counts them differently. If `jds.url` is NULL on a lead being kept or declined, offer once to add the posting link so it can be revisited; recommended, not required. `lead_status='declined'` (seeker passed on a lead) is distinct from `applications.status='rejected'` (a company rejected the seeker).
   - **Secondary, MCP reachable:** push one lead via the `sync_leads` MCP tool (fields incl. `url`, `summary`, `source_urls`). Lands as `lead_status='pending'`, attributed to the caller's source. No staging file.
   - **Secondary, MCP unreachable:** write a `#Lead` page (`type:: #Lead`, `pushed:: false`) into the local `bff-leads` graph via the `markdown-graph` `write_page` tool; `/push-leads` (or `/cleanup`) drains it later.
   - Keep the URL from any URL-sourced JD — it is the lead's clickable posting link.
   Secondary sessions start with `/secondary`, which seeds the local grounding caches over MCP so scoring works online or offline.
