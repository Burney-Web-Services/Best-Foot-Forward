# ADR-0006: Claude Code project memory for cross-session context

**Status:** Accepted  
**Date:** 2026-05-15

## Context

A tailoring agent is only as good as what it knows about the candidate. This context — career history, tailoring preferences, completed applications, voice patterns — needs to persist across sessions without the user re-explaining it every time.

Options considered:
- Embed all context in `CLAUDE.md` (loaded every session automatically)
- Store context in SQLite tables (queryable but requires structured queries to retrieve)
- Use Claude Code's built-in project memory system (`~/.claude/projects/.../memory/`)
- A hybrid: CLAUDE.md for workflow instructions, memory files for personal context

## Decision

`CLAUDE.md` contains **workflow instructions** — how to run the evaluate-job, resume-tailor, interview-prep, and star-story skills; file naming conventions; DB schema reference; tailoring rules. It is committed to the repo and applies to any agent running this codebase.

The **Claude Code memory system** stores personal context — `user_profile.md`, `project_jobsearch.md`, `feedback_style.md`, `voice_guide.md`, etc. These are loaded automatically via `MEMORY.md` (the index file) and read on demand. They are not in the git repo.

## Consequences

- **Rich session context without prompting**: At session start, the agent already knows who the seeker is, what's been applied for, and how they like tailoring to go.
- **Typed memory**: Memory is categorized as `user`, `feedback`, `project`, or `reference`. This shapes when memories are read and what they're used for — feedback memories are checked before starting any tailoring workflow; project memories are checked for application state.
- **Not in the repo**: Memory files live at `~/.claude/projects/<sanitized-project-path>/memory/`. This path is derived from the absolute project path on the current machine. Transferring to a new machine requires manually copying this directory to the correct location on the new machine. `data/` and `memory/` must both be transferred for the agent to work correctly on a new machine.
- **Stale memory risk**: Memories are point-in-time observations. Code behavior described in a memory file may no longer be accurate. Memory should be treated as context, not ground truth — verify against current files before acting on specific technical claims.
- **Portability gap for multi-user vision**: The memory system is personal to the seeker. Making this a multi-user tool requires replacing or abstracting the memory layer — most likely by moving per-user context into the DB and generating it from structured onboarding conversations.
