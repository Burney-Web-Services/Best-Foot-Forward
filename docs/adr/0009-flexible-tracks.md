# ADR-0009: Flexible, Freeform Career Tracks (replaced hardcoded engineer/manager/executive enum)

**Date:** 2026-07-22  
**Status:** Accepted  
**Authors:** Paul Burney, Claude  

---

## Context

### The Problem

Best Foot Forward originally used a fixed, three-bucket career track system:
- **Engineer** — individual contributor roles  
- **Manager** — management/leadership roles
- **Executive** — C-suite and strategic roles

This enum was enforced at multiple layers:
- Database tagging convention (tracks in `bullet_tracks`, `skill_tracks` tables)
- Pre-generated JSON caches (`_bullets_engineer.json`, `_bullets_manager.json`, `_bullets_executive.json`)
- MCP tool filter enums  
- Onboarding and tailoring instructions that forced every user into one of three buckets

### Rigidity Problem

The fixed enum couldn't accommodate real job titles and career paths:
- "Architect" / "Principal Engineer" (neither pure IC nor management)
- "Founding Engineer" (early-stage founder + builder)
- "Architect/FDE" (forward-deployed architect — sales-adjacent engineering)
- Cross-functional / hybrid roles

When a second user onboarded to BFF to vet job opportunities, the system said it wasn't ready for their career — revealing that the three buckets were too tight for real resume diversity.

### Token Cost Argument

The per-track JSON file split was originally a token-cost optimization: instead of passing the full 161-bullet library to Claude for every tailoring session, the code would pre-filter to ~50 bullets for the selected track (plus general), reducing context size.

**This trade-off is now obsolete:** Delegating bullet selection to a Haiku subagent (cheap model, full-catalog comparison) is more cost-effective than Claude pre-filtering by fixed categories. Haiku can compare the full library against the JD in seconds for a few cents; the pre-filtering hack saved nothing.

---

## Decision

1. **Remove the hardcoded track enum.** Tracks are now **free text tags** stored in the same schema (no schema changes needed; `bullet_tracks.track` is already TEXT).

2. **Delegate all bullet/skill selection to Haiku subagents** during `/evaluate-job` and `/resume-tailor` workflows. Haiku receives the full bullet + skill library and the JD, and scores/selects what's relevant. No pre-filtering by track.

3. **Infer track/level tags from resume language** at onboarding time, not force users to pick from three options. Tags emerge from job titles, scope signals ("founded", "led team of 50"), and role history.

4. **Consolidate tailored resume/letter `.txt` files** from flat `data/resumes/tailored/` and `data/letters/tailored/` directories to live beside their `.docx` outputs in the per-role asset directory (`data/BestFootForward/assets/{Company}/{Role_Slug}/`). Both generators now write `.txt` automatically. This eliminates the multi-directory complexity and makes tailored content discoverable in the same context as the application it supports.

---

## Implementation

### Code Changes (Phase 1 & 2)

- **`export_cache.py`**: Removed per-track JSON generation loop. Now generates only `_bullets.json` (full catalog) + `_bullets_conditional.json`.

- **`mcp_server.py`** (`_get_bullets()`, `_get_skills()`): Removed track enum check. Always loads full library, then filters in-memory by checking whether the requested track tag appears in each bullet's `tracks` list (case-insensitive, works with any freeform tag).

- **`generate_resume.py` / `generate_letter.py`**: Added `render_resume_as_text()` / `render_letter_as_text()` functions to auto-generate `.txt` plain-text versions alongside `.docx`, registered in `file_registry`.

- **`suggest_tailoring_source.py`** (new utility): Encodes the prior-application recommendation logic (exact company match → fuzzy domain match → None) into tested Python. Includes parsing of Track: and Key angle: lines from `tailoring_notes`. Replaces ad-hoc hand-logic in resume-tailor sessions.

### Workflow Changes (Phase 2 & 3)

- **`.claude/commands/evaluate-job.md`**: Spawn Haiku subagent to score full JD against complete bullet/skill libraries. No fixed track pre-selection.

- **`.claude/commands/resume-tailor.md`**: Use `suggest_tailoring_source()` for deterministic prior-application lookup. Remove manual .txt file save steps (generators do it). Keep `tailoring_notes` for human-readable Track: label (now freeform, not enum).

- **`.claude/commands/onboard.md`**: Remove PRIMARY_TRACK from intake_data.py. Allow freeform track/level tags derived from actual resume language (job titles, scope signals).

- **`.claude/commands/intake-artifacts.md`**: Same — freeform track tags in step 1 instead of fixed 3 options.

- **`.claude/commands/secondary.md`**: Remove per-track file references from `get_profile_bundle` cache list.

- **Prep workflows** (interview-prep, screening-prep, star-prep, practice-interview): Search for tailored `.txt` files in asset directory instead of flat tailored/ directories. Graceful fallback if not found.

### Migration (Phase 3)

- **`migrate_tailored_txt.py`** (new utility): One-time script to move existing 248 tailored .txt files from flat directories to asset directories. Exact match for JD company/role pair first, then fuzzy domain similarity matching (>50% threshold). Produces a match report with confidence levels so Paul can verify before running.

---

## Benefits

1. **Flexibility**: Users (and job descriptions) are no longer forced into three buckets. Career paths like "founder", "architect", "staff engineer", "VP engineering" can all be expressed naturally.

2. **Simplicity**: Single full bullet library, selected per-role by Haiku. No pre-filtering hacks, no stale pre-computed category files.

3. **Cost-neutral (better)**: Full-library Haiku comparison is cheaper than Claude pre-filtering by track, and more accurate.

4. **Consolidation**: Tailored `.txt` files now live beside `.docx` in the asset directory, eliminating the multi-directory complexity and making them discoverable alongside the application context.

5. **Extensibility**: Adding new tracks or skills doesn't require schema changes or new cache files — tags are freeform.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Migration of 248 existing tailored files could fail or mismatch | Dry-run first with fuzzy-match confidence reporting. Manual review before execution. Archive old directories after. |
| Haiku subagent calls add latency to evaluate-job / resume-tailor | Acceptable — Haiku is fast + cheap. Runs in foreground so user sees results immediately. |
| Freeform tracks could lead to inconsistent tag naming ("engineer" vs "eng" vs "Software Engineer") | Not a problem in practice — tags are only used for filtering bullets for that specific JD. No global schema enforcement. If a tag is typo'd, it just returns no matches; user self-corrects. |
| Removing base-track template resumes removes a fallback | Phase 2 replaces with full-library Haiku matching — no functional loss. Better accuracy. |

---

## References

- [0004-bullet-library-tracks-and-themes.md](0004-bullet-library-tracks-and-themes.md) — Original track+theme taxonomy decision
- [0003-session-scratch-files.md](0003-session-scratch-files.md) — Prior session file layout (tailored/ directories superseded)
- `/data/BUSINESS/Burnilab/_docs/logseq-graph-taxonomy.md` — Higher-level Mistoria vision (unified life data layer with flexible schemas)

---

## Questions for Review

1. **Freeform tag naming** — should we document common tag conventions (engineer, manager, architect, founding-engineer, etc.) for consistency across future onboards? Or leave it organic?
2. **Skill tracks** — should skills also allow freeform tracks, or keep them more structured? (Current: freeform, per this decision.)
3. **Haiku fallback** — if the Haiku API is down, should evaluate-job / resume-tailor gracefully degrade to a simpler scoring mode, or fail hard? (Currently: fail hard — acceptable given BFF's interactive, not automated, nature.)

---

## Decision Log

- **2026-07-22**: Decision accepted. All 178 unit tests pass. Phase 1 (enum removal) + Phase 2 (Haiku delegation) + Phase 3 (migration script + workflow updates) committed to branch `BFF-2026-0722-FlexibleTracksAndAssets`.
- **2026-07-22**: Phase 4 (docs) in progress — reference.md, architecture.md updated; this ADR written.
