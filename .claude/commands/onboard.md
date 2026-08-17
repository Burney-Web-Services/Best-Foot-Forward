# onboard

## Purpose
Guide a new user through BFF setup: collect contact, education, employment history, achievement bullets, and skills; write them to SQLite; and generate the base resume file needed for `/resume-tailor`.

## Intake branches
Three paths based on what the user brings:
- **Type 1** — Recent resume + codebase artifacts (git logs, PRs, docs) → extract and quantify contributions
- **Type 2** — Outdated resume → salvage structure, fill gaps, strengthen weak bullets
- **Type 3** — No resume → structured intake interview to build from scratch

All three paths end at the same destination: a populated SQLite database and a base resume file at `data/resumes/{Track}.txt`.

---

## Workflow

### Phase 0 — Intent (explore vs. build)

Before the intake, gauge why they're here. If they're **just exploring** BFF (e.g. a new open-source user kicking the tires) rather than committing to their real job search, offer the fast path:

> "Want to explore with a sample profile I'll set up, or build your own now?"

If they choose **explore**, run `python3 -m best_foot_forward.utils.load_example_data` to populate a fresh database and Logseq graph from the bundled Leia Organa example dataset (`examples/leia-organa/`). If it reports that a real database already exists, tell the user and stop — do not force-load over real data. Once loaded, drive the demo yourself — **you** pick a representative role from the loaded applications to walk through and tailor; don't make the user hunt for or choose a specific application. Suggest `/evaluate-job` and `/resume-tailor` against the example. When they're ready for real use, run `/onboard` again and build their own.

If they choose **build** (or they're clearly here for their real search), continue with the intake below.

### Phase 1 — Triage

Ask these four questions together in one message:

> 1. Do you have a resume? (yes / yes but it's out of date / no)
> 2. If yes: When was it last substantially updated? (within the last year / 1–3 years ago / 3+ years ago)
> 3. If yes and updated within the last year: Do you have access to work artifacts — git commit history, PR descriptions, architecture docs you authored, or performance reviews?
> 4. What kind of role are you targeting? (free text — e.g., "engineer", "manager", "principal architect", "founding engineer", etc., or "not sure yet")

Branch rules:
- Yes + updated within last year + has artifacts → **Type 1 (Artifact Extraction)**
- Yes + updated within last year + no artifacts → treat as **Type 2** (resume exists but artifacts unavailable)
- Yes + outdated → **Type 2 (Resume Freshening)**
- No → **Type 3 (Zero Resume Build)**

**Note on track selection:** Defer asking "what track are you targeting?" until later. Instead, infer role/level tags from the actual job titles and scope signals in the resume/history. In Phase 3, use the language of their background to propose tags; they confirm or edit freely (e.g., "engineer", "manager", "architect", "founding engineer"). This keeps track selection flexible rather than forcing users into one of 3 buckets at onboarding time.

---

### Phase 1.5 — Document style (optional)

Resume and letter files are formatted with an accent color and font. The defaults are:
- **Accent color**: Teal (#50938A) — used for section headers and your name
- **Font**: Calibri — clean, professional, widely supported

Offer to customize if they want:
> "Your documents will use **teal accent** and **Calibri font** by default. Want to pick a different color or font?"

If yes, present curated lists (avoid free-text entry — unsupported fonts or invalid colors will silently degrade):

**Accent colors:** Navy (#2F4556), Charcoal (#4A4A4A), Burgundy (#8B3A3A), Forest Green (#2D5016), Slate Blue (#3D5A80), Teal (#50938A)

**Fonts:** Arial, Calibri, Cambria, Garamond, Georgia, Times New Roman

Store their choice in the `document_prefs` table (or use defaults if they skip).

---

### Phase 2A — Type 1: Artifact Extraction

Goal: harvest what the codebase proves, not just what the resume says.

1. **Resume parse** — ask the user to paste their full resume text. Extract employers (name, location, start/end dates), existing bullet candidates, and skills listed.
2. **Artifact triage** — ask which of the following are available to paste or describe:
   - Recent git log: `git log --oneline -100`
   - 5–10 most impactful PR or MR descriptions
   - Architecture docs, RFCs, or design decisions authored
   - Performance review or self-evaluation text
   - Jira/Linear issue history or sprint summaries
3. **Per-artifact extraction pass** — for each artifact set provided, read through and identify significant contributions. Draft achievement candidates with targeted follow-up questions:
   - "I see a commit for [X] — do you know the impact? Latency improvement, cost reduction, error rate change?"
   - "This PR migrates [X] — was this a significant initiative, or routine maintenance?"
   - "You authored this doc — did you drive this initiative, or was it assigned to you?"
4. **Metric probing** — for every candidate bullet, probe for quantification before finalizing:
   - Before/after metrics: latency, cost, error rate, test coverage, deployment frequency
   - Scale: team size, user count, revenue impact if known
   - Timeline: how long did this take? ahead or behind schedule?
5. **Bullet finalization** — present the candidate bullets. User confirms, rejects, or refines each one. Assign freeform tracks (e.g., "engineer", "manager", "architect", "general") and themes based on the work scope and language.
6. **Skills audit** — identify skills implied by the artifacts but absent from the resume. Confirm each: "I noticed [X] throughout your commits — is that a skill you'd list?" Add confirmed skills with tracks and themes.
7. Proceed to Phase 3.

---

### Phase 2B — Type 2: Resume Freshening

Goal: salvage and update what exists; fill the gap between the resume's last update and today.

1. **Resume parse** — ask the user to paste their full resume text. Extract employers, bullet candidates, and skills as a draft structure.
2. **Weakness audit** — flag bullets that match these patterns:
   - Passive/weak verbs: "responsible for", "assisted with", "helped", "worked on", "participated in", "supported"
   - No outcome, metric, or impact statement
   - Experience older than 15 years (capture it, but note it will be low-priority in tailoring)
   - Skills listing old framework versions or sunset tools
   Report: "I found X bullets that could be strengthened and Y skills that may be outdated."
3. **Gap filling** — identify the resume's cutoff date. For each year between that date and today:
   - "Your resume ends in [year]. Walk me through what you've been doing since then."
   - For each new role: employer name, location, dates, responsibilities, accomplishments.
4. **Bullet strengthening** — for each flagged weak bullet, probe for outcomes before rewriting:
   - "What was the result of that work? Did it save time, reduce errors, increase revenue, or improve reliability?"
   - Rewrite as an achievement-oriented bullet. Show the before/after. User confirms.
5. **Skills update** — for each dated skill flagged: "You listed [X] — is that still current? What's your current proficiency?" Also prompt for skills gained since the resume cutoff.
6. **Track realignment** — if the person has transitioned (IC → management, or vice versa) since the resume, ask about their current role level/title and use that language for track tags. Allow freeform labels ("founding engineer", "principal architect", etc.) rather than forcing into fixed categories.
7. Proceed to Phase 3.

---

### Phase 2C — Type 3: Zero Resume Build

Goal: conduct a structured intake interview to generate a complete first resume from scratch.

Open with: "We're going to build your resume from scratch through conversation. Every kind of work counts — paid or unpaid, formal or informal. This typically takes 20–30 minutes."

1. **Contact info** — name, phone, email, city/state.
2. **Work history timeline** — "Walk me through the last 10 years. Include paid jobs, freelance work, informal gigs, caregiving, and volunteering — all of it counts."
   - For each role: employer or client name, location (if applicable), approximate dates, what you did, what you were responsible for.
   - Follow-up: "Was there anything in that role you're particularly proud of? Any problem you solved or improvement you made?"
3. **Achievement mining** (across all roles):
   - "Describe a specific problem you solved at work. What happened, what did you do, what changed?"
   - "Was there ever a time you saved time, money, or stress for someone?"
   - "Did anyone ever thank you or recognize your work specifically? What for?"
4. **Skills inventory** (prompt by category):
   - Technical: software tools, programming, platforms, equipment or machinery
   - Interpersonal: customer service, teaching, managing people, coaching
   - Domain knowledge: industry-specific expertise
   - Other: languages spoken, logistics/scheduling, project coordination
5. **Education and credentials** — formal degrees, certifications, bootcamps, self-study, in-progress credentials.
6. **Track discovery** — "Based on what you've described, what role title or level would best describe the kind of work you're looking for?" Accept freeform answers (e.g., "engineer", "senior engineer", "architecture lead", "VP engineering", "founding engineer"). If they're unsure, suggest language that emerged from their job history.
7. Proceed to Phase 3.

---

### Phase 3 — Review and Confirm

Before writing the data file, summarize what will be written:

> - Contact: [name, location, email]
> - Education: [institution(s)]
> - Employers: [list with dates]
> - Bullets: X total (with inferred tracks: engineer, manager, architect, etc.)
> - Skills: Z skill groups
> - Not yet captured (if any): [brief description — see "Content that doesn't fit" below]

Ask: "Does this look right? Anything to add, correct, or remove before I write it?"

Incorporate any corrections, then proceed to Phase 4.

---

### Phase 4 — Write intake_data.py

Write to `data/session/intake_data.py` using this exact format:

```python
# Written by /onboard — read by import_intake.py.
# Do not edit manually between these two steps.

CONTACT = {
    "name": "...",
    "phone": "...",
    "email": "...",
    "location": "...",
}

EDUCATION = [
    {
        "institution": "...",
        "location": "...",
        "degree": "...",
        "sort_order": 0,
    },
]

EMPLOYERS = [
    {
        "name": "...",
        "location": "...",
        "start_date": "MM/YYYY",
        "end_date": "MM/YYYY",  # None = current employer
        "sort_order": 0,       # 0 = most recent, ascending for older employers
        "notes": "",
    },
]

BULLETS = [
    {
        "id": None,           # auto-generated by import_intake.py
        "employer": "...",    # must match an EMPLOYERS name exactly
        "role": "...",
        "text": "...",
        "tracks": ["engineer"],   # freeform tags inferred from the role's own language —
                                  # e.g. engineer, manager, architect, founding-engineer,
                                  # staff-engineer. Not an enum; see ADR-0009.
        "themes": [],             # ai-native | distributed-systems | leadership | product-delivery | backend | frontend | data | scale | mentorship | edtech | fintech | healthcare | open-source
    },
]

SKILLS = [
    {
        "id": None,           # auto-generated by import_intake.py
        "label": "...",       # e.g. "Backend:" or "AI & Product Engineering:"
        "content": "...",     # comma-separated list of tools/technologies
        "tracks": ["engineer"],
        "themes": [],
    },
]
```

Writing rules:
- EMPLOYERS `sort_order`: 0 = most recent employer, ascending for older employers
- Bullet `employer` must exactly match the `name` field of an entry in EMPLOYERS
- Leave `id` as `None`; `import_intake.py` will generate slug-based IDs
- For **Type 3 users**: informal/volunteer work goes in EMPLOYERS with a brief `notes` description; bullets from that work are treated the same as formal employment

---

### Phase 5 — Import and verify

Run in sequence:

```bash
python3 src/best_foot_forward/utils/import_intake.py
python3 src/best_foot_forward/utils/export_cache.py
```

If either fails, read the error and fix `data/session/intake_data.py`, then re-run. The import is safe to re-run; it uses upsert logic throughout.

---

### Phase 6 — Initialize asset directory

Create the base asset directory structure for this user (one-time setup):
```
mkdir -p data/BestFootForward/assets
```

This is where all tailored .docx/.txt resumes and letters will live, organized by company and role. No base resume template file is needed — all tailoring sessions generate fresh .docx + .txt versions from the full bullet/skill library as Haiku selects them per the JD.

---

### Phase 7 — Completion summary

**Graph bootstrap (first time only):**
If this is a fresh onboard (no prior data/BestFootForward/ graph), initialize it:
```
python3 -m best_foot_forward.utils.init_graph
```

This bootstraps the graph structure, populates pages from your SQLite data, generates the Home dashboard + Leads board, and auto-registers with `markdown-graph-mcp` if installed.

Output: `data/BestFootForward/pages/Home.md` (and Leads Dashboard) — open in Logseq or your editor to browse.

**Draft `memory/user_profile.md` (skip if it already exists — don't clobber hand-edits):**
From the intake data just written, draft a short career-context summary: name, target track(s), a one-line-per-employer history summary, and standout themes from the bullets. This is what `/evaluate-job` and `/resume-tailor` read for full career context, so keep it factual and drawn only from what was just confirmed in Phase 3 — don't add anything new.

If Phase 3 flagged anything under "Not yet captured," add it verbatim under a `## Not yet captured` heading at the end of the file — see "Content that doesn't fit" below.

Report:
- Bullet count by track (inferred from job history)
- Skill group count
- Path where the asset directory was created

Suggest next steps:
> "Run `/evaluate-job` to score a job description for fit."
> "Run `/resume-tailor` when you're ready to tailor for a specific role."
> "Run `/capture-voice` any time to teach me your writing voice so letters and interview answers sound like you (optional, ~5 min)."

If bullet coverage is thin overall:
> "You have X bullets across Y tracks. Consider running `/intake-artifacts` to bulk-add from your codebase, or `/onboard` again after gathering more examples."

If anything was flagged under "Not yet captured" in Phase 3:
> "I also noticed [X] in what you gave me, which doesn't have a home in BFF's fields yet — I saved it under 'Not yet captured' in your profile rather than guessing at how to represent it. Want me to add proper support for it? That's a small, deliberate change I can make separately whenever you're ready — just ask."

---

## Notes

- Do not fabricate experience. Only use what the user provides during the intake.
- All bullets must have an outcome, metric, or impact. If the user provides a task description with no result, probe before writing the bullet.
- For **Type 1**: the artifact extraction pass often surfaces more achievements than the resume itself. Treat the resume as a starting inventory, not a ceiling.
- For **Type 3**: informal and volunteer work is legitimate experience. Frame it professionally and without apology.
- The 15-year rule applies from day one. Capture old experience, but note it will be low-priority in tailoring.
- **Content that doesn't fit**: if a resume or artifact includes information with no home in the existing fields (contact/education/employers/bullets/skills) — a security clearance line, publications, patents, licenses, anything structurally new — do not modify BFF's code or schema to accommodate it mid-onboarding. Onboarding is an intake conversation, not a coding session. Note the content verbatim (Phase 3 summary, then `## Not yet captured` in `memory/user_profile.md`) and offer, at the end, to build proper support for it as a separate, deliberate follow-up — never as an automatic side effect of getting through intake.
