# session-cleanup (BFF)

BFF-specific session cleanup. Start by reading and following `~/.claude/skills/cleanup/SKILL.md` (the universal cleanup workflow), then run the BFF-specific additions below. Add the BFF sections to the final report.

---

## BFF Note Provenance Convention

BFF session artifacts have specific authorship conventions. Follow these instead of the global defaults:

| Source | Convention | When Used |
|--------|-----------|-----------|
| **Seeker's raw notes** | `{Company}Notes.md` | Seeker's own observations, impressions, things they heard/said |
| **Claude's analysis** | `{Company}ClaudeNotes.md` | Synthesis, strategic framing, pattern-matching, assessments Claude produced |
| **Co-mingled prep** | `{Company}ScreenPrep.*`, `{Company}InterviewPrep.*` | Claude-structured, seeker-informed — these always blend both voices |
| **Living research dossier** | `{Company}CompanyNotes.md` | Claude-assembled company research; no authorship ambiguity needed |
| **Structured debrief (DB)** | `applications.notes` | Append-only, clearly labeled by round and date |

When writing a mixed file, use explicit section headers: `## Seeker's Notes` and `## Claude's Analysis`.

---

## BFF Addition A — Application materials check

For each company touched this session:
1. Check that the application directory exists at `data/BestFootForward/assets/{Company}/{Role_Slug}/`
2. Verify expected files are present (JD, resume .docx, letter .docx if applicable)
3. Flag any Claude analysis, session assessments, or rejection debriefs that were produced verbally but not yet saved
   - Write to `{Company}ClaudeNotes.md` in the application directory — do not ask permission
   - If the seeker shared raw notes or impressions, write to `{Company}Notes.md`

## BFF Addition B — DB state check

Run:
```bash
python3 src/best_foot_forward/utils/db_query.py "SELECT j.company, j.role, a.status, a.stage, a.applied_at, a.concluded_at FROM applications a JOIN jds j ON a.jd_id = j.id ORDER BY a.id DESC LIMIT 10"
```

Verify:
- Rejections logged this session have `status='rejected'`, `concluded_at` set
- Advances have correct `stage` value
- New JD stubs inserted this session have correct `company`, `role`, `score`, `file_path`

Report anything that looks wrong or missing.

## BFF Addition B2 — Refresh application summaries export

Refresh the portable JSON export that powers resume-tailor suggestions in low-context sessions:

```bash
python3 src/best_foot_forward/utils/export_application_summaries.py
```

This regenerates `data/application_summaries.json` (applications + JDs with tailoring metadata) and refreshes the `Applications complete: N` line in `memory/project_status.md` to match the current count. Run this so the next session has fresh data for tailoring recommendations.

## BFF Addition C0 — Known issues log

When Step 5 of the global workflow (Outstanding items) surfaces a technical bug, data-integrity issue, or anything flagged as "needs verification" or "worth a look" — as opposed to a purely job-search follow-up like a thank-you note or pending recruiter reply — log it immediately to `memory/project_roadmap.md` under the `## DB gaps identified (not yet resolved)` section (or the nearest matching section if the issue isn't DB-related). Do not just report it in the cleanup summary and let it evaporate at `/compact`.

Format: one bullet, bold short title, then what was observed, root cause if known, and what fix is needed. Follow the existing entries in that section as the template (e.g., the `scan_jds.py path mismatch` and `track_application.py JD lookup path mismatch` entries). Mark entries `FIXED {date}` once resolved rather than deleting them — the history of what broke and why is useful.

Job-search-specific outstanding items (pending replies, thank-you notes, follow-ups) still go through the global Step 5 flow, not this log.

## BFF Addition B2 — Secondary lead push (secondary machine only)

If `BFF_ROLE=secondary`: run the `/push-leads` workflow to drain any locally-queued `#Lead` pages (leads evaluated offline this session) up to the primary via MCP. If the MCP server is unreachable, note that queued leads remain `pushed:: false` and will retry next session — nothing is lost. Report the push result (or "no queued leads") in the cleanup summary. On non-secondary machines, skip this addition.

## BFF Addition C — Memory check (BFF-specific files)

Read `memory/MEMORY.md`. For each memory file that could be affected by this session:
- New rejection → update `project_jobsearch.md` (add to rejections list) + `project_status.md` (pipeline + recent rejections)
- Application advance → `project_jobsearch.md` + `project_status.md`
- Seeker shared preferences or working style → `user_profile.md` or `feedback_style.md`
- Process or tool behavior changed → relevant memory file
- Any "advancing" entry that is now a rejection → update it

Do not save ephemeral session details. Save only what will be useful cold, in a future conversation.

---

## Report additions (append to the global report)

```
DB:
- [DB changes verified or made, or "no DB changes"]
```

## Notes
- Do not ask permission before writing `{Company}ClaudeNotes.md` — if a notable analysis exists only in the conversation, save it. That's the point.
- If `applications.notes` already has a debrief from a prior round, append with `\n\n---\n\n` — never overwrite.
- Memory check is a judgment call: "would future-me benefit from knowing this cold?"
- If the seeker is in a hurry, prioritize Addition A (artifact capture) and the global memory check — skip DB and BFF memory if needed.
