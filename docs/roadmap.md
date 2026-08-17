# Best Foot Forward — Roadmap

Features under active consideration. Not a commitment list — a thinking-out-loud record.

---

## In progress / recently landed

**STAR corpus capture** (`star-story` skill)  
Status: Skill written; DB tables (`stories`, `story_themes`, `story_bullets`) live.  
Next: Run first real story captures to validate the interview flow. Integrate story retrieval into `interview-prep` skill — when generating Q&A responses, query stories by theme rather than bullets alone. Build audio transcription path (Whisper) when voice input is useful.

**Screen/interview debrief notes**  
`applications.notes TEXT` column added (2026-06-02). Claude saves recruiter screen debrief — topics covered, flags raised, intel learned about role/team — directly to the DB after each screen. The `interview-prep` and `screening-prep` skills should read this field at the start of prep sessions so context from prior rounds is automatically in scope.  
Next: Update `interview-prep` skill to query and inject `applications.notes` for the target company.

---

## Near-term

**MCP-server auth for live secondary sync** (planned 2026-07-17)  
Replaces the export/transfer-file/import cycle with a live round trip for Claude-based secondaries (a collaborator today, a second machine of your own eventually) — bearer tokens, source-by-identity instead of client-supplied, Tailscale-only exposure. Full spec in `docs/architecture.md` → "Secondary Machine Sync" → "Planned — live MCP transport."

**Public lead intake via Lovable** (planned, weekend of 2026-07-18/19)  
No-login intake form for sourcers who don't run a coding agent — Supabase table, pull-based bridge into `jds`. Full spec in `docs/architecture.md` → "Secondary Machine Sync" → "Planned — public lead intake."

**Bullet provenance audit**  
Most bullets in `_bullets.json` are orphaned — no link to a source story. Once the STAR corpus is populated, run a pass to link existing bullets to the stories they came from via `story_bullets`.

**Salary data quality**  
`cli.py salaries` exists but `salary_min`/`salary_max` fields on the `jds` table are inconsistently populated. Either improve JD parsing to extract salary ranges automatically, or build a light post-apply prompt ("Did you see a salary range? Want to log it?").

**Thank-you note and follow-up tracking**  
The DB has application stages but no log of: when a thank-you was sent, to whom, via which channel. At minimum, a `contacts` record with a `last_contact` field and a note. A lightweight `follow_ups` table would be better.

---

## Medium-term

**Full process management**  
The current system handles apply → stage transitions but the surrounding intelligence decays across sessions. Things worth capturing persistently:
- Recruiter touchpoints and response timing
- Offer/comp details (base, equity, benefits) for comparison if multiple offers land
- Rejection stage and signal (why rejected, at what stage) — over time, surface patterns
- Reference tracking (who's been used where, whether they've been contacted)

**Interview prep improvements**  
The `interview-prep` skill currently works from bullets. Once stories are populated, it should surface the full STAR narrative for each Q&A response, not just the resume line. The prep doc would include both the short version (resume bullet) and the long version (full story).

**Voice pattern extraction from STAR transcripts**  
The current `voice_guide.md` is hand-derived from a few cover letters. A corpus of 20+ STAR interview transcripts would give much richer signal for "how the seeker actually sounds" — opener patterns, sentence rhythm, characteristic phrases, what to avoid. This upgrades every letter and tell-me-about-yourself the agent drafts.

---

## Long-term / architectural

**Multi-user onboarding**  
The current system is deeply personalized to the seeker. The architecture (bullet library, skills library, tracks, themes, evaluate-job, resume-tailor) is the generalizable kernel. The path to multi-user:
1. Move per-user context from memory files into DB tables (`users`, `user_bullets`, `user_skills`, etc.)
2. Build a conversational onboarding flow: "Give me your current resume. Let's talk through it."
3. The agent interviews the user to fill out their bullet library, employer context, and skills — the same way the seeker's data was originally entered, but automated
4. Abstract away the `data/` personal directory so a new user gets a fresh DB

The ADR-0006 memory portability problem is a preview of this challenge at small scale.

**Evaluation scoring calibration**  
The evaluate-job 5-dimension model (20 pts each, 100 total) is heuristic. Over time, correlate predicted scores with actual outcomes (screened, interviewed, offered, rejected at which stage) to see if the scoring model is predictive. Adjust dimension weights or add dimensions if patterns emerge.

**CI / automated cache validation**  
A simple check that `_bullets.json` and `_skills.json` match what's in the DB would catch the "forgot to run export_cache.py" failure mode. Could be a pre-commit hook or a lightweight test.
