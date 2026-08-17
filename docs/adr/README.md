# Architecture Decision Records

These are point-in-time records of *why* Best Foot Forward is built the way it is — written when
each decision was made, and deliberately left standing afterward.

**They are history, not documentation.** An ADR describes the reasoning available at its date,
including constraints and alternatives that no longer apply. When one is overtaken by a later
decision it gets marked `Superseded` and points forward, rather than being rewritten — the value
of the record is that it says what was true then. For how the system behaves *now*, read
[`../architecture.md`](../architecture.md) and [`../reference.md`](../reference.md).

If you're skimming and want the two that explain the most unusual choices, read
[ADR-0002](0002-claude-code-as-runtime.md) (why there's no application server) and
[ADR-0008](0008-logseq-graph-pipeline-master.md) (why there are two sources of truth).

| # | Decision | Date | Status |
|---|----------|------|--------|
| [0001](0001-sqlite-source-of-truth.md) | SQLite as source of truth, with generated JSON read caches | 2026-05-15 | Accepted |
| [0002](0002-claude-code-as-runtime.md) | Claude Code as the conversational runtime — no separate application server | 2026-05-15 | Accepted |
| [0003](0003-session-scratch-files.md) | Session scratch files as generator inputs | 2026-05-15 | Accepted |
| [0004](0004-bullet-library-tracks-and-themes.md) | Bullet library organized by tracks and themes | 2026-05-15 | **Superseded by 0009** |
| [0005](0005-application-tracking-hook.md) | Automatic application tracking via a PostToolUse hook | 2026-05-20 | Accepted |
| [0006](0006-project-memory-system.md) | Claude Code project memory for cross-session context | 2026-05-15 | Accepted |
| [0007](0007-mystery-default-port.md) | mystery6 default port is 3071 (BFF in octal) | 2026-07-10 | Accepted |
| [0008](0008-logseq-graph-pipeline-master.md) | Logseq Markdown graph as the pipeline master | 2026-07-16 | Accepted |
| [0009](0009-flexible-tracks.md) | Flexible, freeform career tracks, replacing the fixed enum | 2026-07-22 | Accepted |

## A note on numbering

Numbers are permanent identifiers assigned in the order decisions were recorded, not a strict
chronology — 0006 predates 0005 by date. ADR-0009 was briefly also numbered 0005; it was
renumbered before the repository was made public, and every reference in the codebase was
updated with it.
