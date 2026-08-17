# ADR-0007: mystery6 default port is 3071 (BFF in octal 🤘🏻)

**Status:** Accepted
**Date:** 2026-07-10

## Context

`/web`'s mystery6 admin UI needed a default port. `3100` was the original arbitrary pick (see
`~/.claude/plans/bff-story-bot-issue-elegant-otter.md` for the incident that prompted revisiting
this file: a `SessionEnd` hook meant to auto-stop the server was instead getting triggered by
every headless `claude -p` turn from the `bff-chat` plugin, occasionally killing the server out
from under itself). While removing that hook and its unscoped `pgrep`-based kill fallback (so
multiple mystery6 instances can now safely coexist on different ports for testing), the port
came up for a rename too.

Options considered:
- Leave it at `3100` — boring, arbitrary, no reason to change it.
- Pick something else arbitrary.
- Pick something *meaningful*.

## Decision

Default port is now **3071** — B-F-F, spelled out in octal digits. Octal only has digits 0-7, so
this isn't a literal base-8 encoding of the letters "BFF" (that would need actual octal *values*,
and letters aren't numbers) — it's a mnemonic: three digits, reads like "BFF" if you squint,
sits comfortably in the ephemeral-port-adjacent range mystery6 already lived in, and is
memorable enough that nobody has to `grep` for "what port does `/web` use again."

Nerds are gonna nerd. This one's for Paul.

## Consequences

- **Memorable over arbitrary**: `3071` ties the port back to the project name instead of being
  an unexplainable magic number.
- **No functional impact**: Purely cosmetic — any port still works via `/web <port>`, and nothing
  in mystery6, `bff-chat`, or BFF's own scripts hardcodes `3071` as meaningful (it's just the
  default argument value in `web/mystery/setup.mjs` and `.claude/commands/web.md`).
- **Stale references**: Anywhere `3100` was written down as a literal (old permission-allow
  entries in `.claude/settings.local.json`, stale notes in memory files) will look outdated but
  isn't broken — those are historical records of past commands, not live config.
