# ADR-0002: Claude Code as conversational runtime (no separate application server)

**Status:** Accepted  
**Date:** 2026-05-15

## Context

The "application" needed to: ask clarifying questions, read files, make judgment calls about which bullets to select, draft prose, and write structured output — all in a tight feedback loop with the user. This is a reasoning-heavy workflow, not a data-processing pipeline.

Options considered:
- Build a traditional web or CLI app that calls the Anthropic API
- Build a custom agent using the Claude Agent SDK
- Use Claude Code sessions directly as the UX

## Decision

Claude Code sessions *are* the application. There is no separate server. Workflows are defined as `.claude/commands/` skill files (and natural language triggers in `CLAUDE.md`) that Claude Code loads and executes. The user interacts by typing in Claude Code's chat interface.

`db_query.py` is explicitly allowlisted in `.claude/settings.local.json` as the only SQL execution path. This prevents Claude from running arbitrary Python that could corrupt the DB and gives the user a clear audit trail of every query.

## Consequences

- **No deployment complexity**: There is no server to run, no API keys to manage in a deployed app, no build step. The tool runs wherever Claude Code runs.
- **Intelligence is the model**: All judgment — which bullets fit, how to frame a gap, what tone the letter needs — is handled by Claude, not by hand-written heuristics.
- **Context window is the session boundary**: Everything Claude needs for a session must be loaded at session start (memory files, bullet library, JD). Long sessions risk losing earlier context. The memory system (ADR-0006) mitigates this across sessions; skill files keep per-workflow context loading consistent.
- **Single user, single session**: No concurrency, no multi-user support. Intentional for a personal tool.
- **Portability concern**: The tool requires Claude Code, which requires the user's Anthropic account. Not easily transferable to someone else in its current form. The long-term vision (ADR-0002 is the key blocker to address) is to abstract this enough that a new user can onboard through conversation without needing to clone this repo's personal data.
