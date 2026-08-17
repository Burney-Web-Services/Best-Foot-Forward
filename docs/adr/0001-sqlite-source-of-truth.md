# ADR-0001: SQLite as source of truth with generated JSON read caches

**Status:** Accepted — **amended by [ADR-0008](0008-logseq-graph-pipeline-master.md) (2026-07-16)**  
**Date:** 2026-05-15

> **Amendment (ADR-0008):** SQLite remains the source of truth for the **library**
> (bullets, skills, stories, employers) and the JSON read-cache discipline below
> still applies to it. The **pipeline** layer (`jds` narrative fields,
> `applications`, `contacts`, prep, notes) is now **Markdown-as-master** in a
> Logseq graph; the corresponding SQLite tables are a rebuildable index over the
> pages. See ADR-0008.

## Context

The system needs persistent storage for bullets, skills, employers, job descriptions, applications, and stories. The options considered were:

- Flat JSON/YAML files edited directly
- A hosted database (PostgreSQL, PlanetScale, etc.)
- SQLite with direct reads during sessions
- SQLite as write store with generated JSON read caches

## Decision

SQLite is the authoritative data store. All permanent edits go through SQLite — either via `db_query.py` in-session or direct SQL tooling.

JSON files with a `_` prefix (`_bullets.json`, `_skills.json`, `_employers.json`, `_contact.json`, `_education.json`) are **generated read caches** produced by `export_cache.py`. They exist for fast in-session reads and are never edited directly. The `_` prefix signals this explicitly.

## Consequences

- **Fast session reads**: Claude reads the full bullet and skills library in one pass from JSON at session start, without repeated DB queries.
- **Single source of truth**: No sync conflicts between JSON and DB. JSON is always regeneratable. If the two ever diverge, SQLite wins.
- **Discipline required**: Every direct DB change must be followed by `python3 src/best_foot_forward/utils/export_cache.py`. Skipping this leaves JSON stale.
- **Local-only**: SQLite is a file. No concurrency, no remote access. Intentional for a single-user personal tool.
- **Portability**: The `data/` directory (gitignored) moves between machines as a unit — DB + caches together. See ADR-0006 on the complementary portability problem with memory files.
