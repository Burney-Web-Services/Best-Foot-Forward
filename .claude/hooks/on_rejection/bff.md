# Hook: Regenerate BFF Logseq Graph Page + Home Dashboard on Rejection

**Trigger:** on_rejection
**Requires:** Python 3.11+, `best_foot_forward` package (bundled with BFF)

## Instructions

After logging a rejection in BFF (DB already updated: `applications.status='rejected'`, `stage='rejection'`, `concluded_at` set):

1. Get `COMPANY` from the rejection logging context.

2. Run: `python3 -m best_foot_forward.utils.export_graph --only '{COMPANY}'`
   - Execute from the BFF project root.
   - This regenerates `{Company}.md` and `{Company}/{Role}/Application.md` pages directly from current DB state.
   - Properties like `status::`, `stage::`, and `concluded::` are written by `export_graph.py` — do not hand-edit.

3. Run: `python3 -m best_foot_forward.utils.generate_home`
   - Execute from the BFF project root.
   - This regenerates `Home.md` and `Leads Dashboard.md` (and stamps the Sèvo pulse
     if `BFF_SEVO_GLANCE` is set) so the "passes this week" counter and the "In motion"
     rollup drop the closed application immediately, instead of waiting for the next
     application or prep run.

4. If either command isn't available or fails (e.g., permission denied), skip silently. The DB update already happened; the graph and dashboard will catch up on the next scheduled export.

5. Confirm in one line: "BFF knowledge graph + Home dashboard updated — {Company} closed."

## Why this pattern

The database is the source of truth for all application state. `export_graph.py` is the only writer to BFF's graph and `generate_home.py` is the only writer for the Home dashboard — both just resync from the current DB state, so running them after any rejection is always safe and idempotent. Hand-editing page properties introduces drift and is never necessary.

Previously this hook ran only `export_graph`, which updated the company and role pages but left `Home.md` stale: a freshly-logged rejection still showed **0 passes this week** until some later application or prep run happened to refresh the dashboard. This is the same gap `on_application` had before it gained its own `generate_home` step.
