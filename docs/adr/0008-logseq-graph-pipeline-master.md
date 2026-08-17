# ADR-0008: Logseq Markdown graph as the pipeline master

**Status:** Accepted
**Date:** 2026-07-16
**Amends:** ADR-0001 (SQLite as source of truth)

## Context

ADR-0001 made SQLite the single source of truth for everything: the reusable
library (bullets, skills, stories, employers) *and* the job-search pipeline
(job descriptions, applications, contacts, notes, prep). That was right for the
library, which is relational and feeds `.docx` generation and reporting. But the
pipeline is a **narrative** layer — company research, application framing, screen
debriefs, interview prep — that humans and AI want to *navigate and edit*, not
query. Keeping it locked in SQLite meant it wasn't discoverable in the same
knowledge-graph fabric as the rest of the user's world (the "Sèvo" Logseq hub).

The decision to go Markdown-as-master for that layer was recorded in the Sèvo hub
on 2026-07-15 (stay on Logseq OG / Markdown, SQLite as a disposable index).

## Decision

**Split the masters.**

- **SQLite stays master for the library** — `employers`, `bullets`, `skills`,
  `tracks`/`themes`, `stories`, `contact`, `education`, `jd_required_skills`,
  `file_registry`. These feed `.docx` generation and the reporting CLI, and the
  JSON read-cache discipline from ADR-0001 still applies to them unchanged.
- **A Logseq Markdown graph is master for the pipeline narrative** — one page per
  company (`{Company}`, a `mistoria-reference:: org:` entity), with namespaced
  children `{Company}/{Role}/Application|Prep|Notes` plus `{Company}/Notes`. The
  graph lives at `data/BestFootForward/` and is registered as the `bff` graph in
  `markdown-graph-mcp`.
- **SQLite is also a rebuildable index over the pipeline.** Pipeline fields still
  live in `jds`/`applications`/etc. for relational reporting, but the pages are
  authoritative; the DB rows are reconciled *from* the pages, keyed on the
  `bff-jd-id::` / `bff-application-id::` echoed in each page.

Per Sèvo's "Document vs. database" rule: never copy a fact into both. A value the
DB owns (selected bullets/skills) renders on a page as a regenerated block; a
value a page owns (status, stage, dates) is reconciled back into the DB index.

### The sync loop

- `export_graph.py` — DB → pages (`--only '<Company>'` refreshes one company;
  run as the last step of `resume-tailor` and on rejection).
- `reconcile_graph.py` — pages → DB (column-UPSERT on the echoed ids; run before
  DB-backed reports if pages may have been hand-edited).
- `generate_home.py` — regenerates the Home + Leads dashboards.

## Consequences

- **Human- and AI-navigable pipeline**: companies, applications, prep, and notes
  are browsable in Logseq and queryable via the `markdown-graph` MCP tools.
- **`.docx` generation is unaffected** — it reads only the library + session
  scratch files, never the pipeline pages.
- **Never `rm data/BestFootForward/pages/*.md`** before an export. `export_graph`
  overwrites only the pages it generates (by title); a bare re-run is safe, a
  wipe deletes hand-authored Notes and ported reference pages.
- **Reconcile-before-report discipline**: after Logseq edits, run
  `reconcile_graph.py` so reporting/MCP reads reflect the pages.
- **Dates render as `[[YYYY/MM/DD]]`** to match the graph's `yyyy/MM/dd` journal
  format (Year/Month/Day namespace index).
- **Two-way drift is possible** between an edit and a reconcile — acceptable for a
  single-user tool; the id-keyed UPSERT never orphans library/tracking FKs.
