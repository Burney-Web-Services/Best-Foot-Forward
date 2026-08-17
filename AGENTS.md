# Best Foot Forward — Agent Guide

Best Foot Forward is a local-first job-search workspace. Preserve the user's
career facts: tailor and reorganize source material, but never invent
experience, results, or credentials.

## Session startup

At the start of a conversation, read `memory/project_status.md` and greet the
user with exactly one line before addressing their request:

`Ready. [N] applications complete. Last: [Company] — [Role].`

Use the values in that file; do not query the database just to form the
greeting. Read `memory/project_jobsearch.md` only when a workflow needs the
full job-search history.

## Workflows

The reusable workflows live in `.agents/skills/`. Use them when their
descriptions match the request. The source procedures they reference remain in
`.claude/commands/` so Claude Code, Gemini/Antigravity, and Codex share one
canonical workflow.

- A pasted job description, JD file, fit/compatibility-score request →
  `evaluate-job`.
- “tailor” → `resume-tailor`.
- “onboard” or entering career history → `onboard`.
- “cleanup”, “wrap up”, or “session cleanup” → `cleanup`.
- “prep”, “screen”, “interview prep”, STAR story, interview practice/debrief,
  artifact intake, or primary/secondary transfer → use the correspondingly
  named skill.

After a major unit of work, suggest: “Good stopping point — worth running the
`cleanup` skill then starting a fresh context before we continue.” Do this once
per natural break, never mid-task.

## Data integrity

- `data/best_foot_forward.db` is the source of truth. Treat JSON files such as
  `data/_bullets*.json` and `data/_skills.json` as generated caches. After a
  direct database edit, run `python3 src/best_foot_forward/utils/export_cache.py`.
- The Logseq graph at `data/BestFootForward/` mirrors the application pipeline.
  Use `python3 -m best_foot_forward.utils.export_graph` to write generated
  pages and `reconcile_graph` before DB-backed reports when graph pages may
  have been edited. Never delete `pages/*.md` wholesale.
- Each completed tailoring session must scan the JD directory with
  `python3 src/best_foot_forward/utils/scan_jds.py data/BestFootForward/assets`
  and correct the placeholder role on the resulting JD record.
- Files written by the resume generator count as an application; the Codex
  `PostToolUse` hook runs `track_application.py` after resume generation.

## Tailoring conventions

- Read `data/_bullets.json` (the full catalog — there is no per-track split;
  ADR-0009 removed it) and `data/_skills.json`; load `data/_bullets_conditional.json`
  only when needed. Tracks are freeform tags, not an enum — bullet/skill selection
  is delegated to a subagent against the full library, not pre-filtered by track.
- Preserve bullet and skill IDs in session data. Use bullet dictionaries
  (`{'id': '…', 'text': '…'}`) and skill dictionaries
  (`{'id': '…', 'label': '…', 'content': '…'}`).
- Do not use pre-2011 experience unless it directly addresses an explicit JD
  requirement or gap.
- JD files and generated documents belong in
  `data/BestFootForward/assets/{Company}/{Role_Slug}/`. Output filenames are
  `{First Last} Resume - {Company} {Role}.docx` and
  `{First Last} Cover Letter - {Company} {Role}.docx`.

## Validation and safety

- Run the most relevant command-level check after changing code or workflow
  configuration. Do not alter user data merely to test configuration.
- Keep private `data/` content out of commits and reports. Do not expose it in
  open-source documentation.
- Project-local Codex configuration is activated only for trusted repositories.
  Use `/mcp` and `/hooks` after opening the project to inspect and trust the
  local MCP server and hook.
