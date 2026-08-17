# ADR-0005: Automatic application tracking via PostToolUse hook

**Status:** Accepted  
**Date:** 2026-05-20

## Context

Every completed tailoring session should result in an `applications` record in the DB — capturing that materials were generated, when, and for which JD. Manual tracking steps get skipped. The question was where to trigger this insertion.

Options considered:
- Require Claude to manually run `track_application.py` at the end of every session
- Build it into `generate_resume.py` directly
- Use a Claude Code PostToolUse hook that fires after `generate_resume.py` completes

## Decision

A PostToolUse hook in `.claude/settings.local.json` fires `track_application.py` immediately after any invocation of `generate_resume.py`. The script reads the current `data/resume_data.py` to get `JD_FILE_PATH`, looks up the corresponding `jds` record, and inserts an `applications` row if one doesn't already exist (`INSERT OR IGNORE`).

The core assumption is: **files written = applied**. Generating a `.docx` is treated as equivalent to submitting an application.

## Consequences

- **Zero manual tracking**: The agent does not need to remember to run tracking. If `generate_resume.py` ran, the application is logged.
- **Idempotent**: Re-running `generate_resume.py` for the same JD (e.g., after a typo fix) does not create a duplicate record.
- **Assumption can misfire**: For cold outreach or speculative document generation (e.g., Mission.io), the record is created even though no application was formally submitted. This is accepted — the DB record is useful even for networking contacts.
- **JD record must exist first**: `track_application.py` looks up by `file_path`. If no `jds` record exists for the JD file, the hook fails silently. For pasted JDs (no file yet), Claude must insert a stub `jds` record before running generation. This is documented in `CLAUDE.md` and the `evaluate-job` skill.
