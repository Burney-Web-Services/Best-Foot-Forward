# ADR-0004: Bullet library organized by tracks and themes

**Status:** Superseded by [ADR-0009](0009-flexible-tracks.md)  
**Date:** 2026-05-15

> **Superseded 2026-07-22.** The fixed `engineer` / `manager` / `executive` track enum described
> here was replaced by freeform track tags. The *themes* half of this decision still stands.
> Read [ADR-0009](0009-flexible-tracks.md) for current behaviour.

## Context

A resume bullet library needs a retrieval model — some way to select "the right bullets for this role" without reading every bullet every time. The dimensions that matter for selection are:

- **What kind of role is this?** (IC engineer vs. engineering manager vs. executive)
- **What does this JD emphasize?** (AI adoption, distributed systems, EdTech, mobile, etc.)

## Decision

Every bullet carries two classifiers:

**Tracks** — `engineer`, `manager`, `executive`, `general`. Mutually assignable; a bullet can appear on both an engineer and manager resume. "General" is for bullets that apply across all tracks but aren't primary.

**Themes** — a controlled vocabulary (e.g., `ai-native`, `distributed-systems`, `people-management`, `education-mission`, `mobile`). Each bullet can have multiple themes. The vocabulary is shared across `bullet_themes`, `story_themes`, and `skill_themes` tables, enabling cross-table retrieval by theme.

**`use_when`** — an optional condition field. Bullets with `use_when` set are never included by default; they're only pulled in when the specified condition is true. Used for: historically old experience (pre-2011), niche skills, context-dependent framings.

**15-year rule** — experience older than 15 years (pre-2011) only appears when it directly addresses a specific gap in the JD. Historical employers exist in the DB for completeness but their bullets carry `use_when` and `general` track.

## Consequences

- **Session retrieval**: At tailoring session start, Claude reads `_bullets.json`, filters by track and relevant themes, and works from that reduced set. The full library (100+ bullets) rarely needs to be read exhaustively.
- **Vocabulary discipline**: Adding a new theme carelessly fragments retrieval. New themes should be rare and deliberate. When possible, use an existing theme and adjust the bullet text.
- **Bullet provenance**: Bullets should trace back to source stories in the `stories` table via `story_bullets`. Currently many bullets are orphaned (no story link). This is a known gap — see `roadmap.md`.
- **Skills library mirrors this**: `_skills.json` uses the same track/theme structure for skills groups, enabling parallel retrieval logic.
