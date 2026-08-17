# Hook: Update BFF Logseq Graph + Home Dashboard on Rejection

**Trigger:** on_rejection
**Requires:** Python 3.11+, `best_foot_forward` package (bundled with BFF)

## How it works

After a rejection is logged to the BFF database (status='rejected', stage='rejection', concluded_at set), this hook regenerates the company's graph pages from the current DB state.

Since the database is the source of truth and `export_graph.py` is the only graph writer, syncing is a one-step operation.

## Instructions

1. Get `COMPANY` from the rejection log (already available in the calling context).

2. Run: `python3 -m best_foot_forward.utils.export_graph --only '{COMPANY}'`
   - Run from the BFF project root.
   - This regenerates `{Company}.md` and `{Company}/{Role}/Application.md` with current DB state.

3. Run: `python3 -m best_foot_forward.utils.generate_home`
   - Run from the BFF project root.
   - Refreshes `Home.md` / `Leads Dashboard.md` so the "passes this week" counter and
     the "In motion" rollup reflect the closed application right away.

4. If either command isn't available or fails (e.g., permission denied), skip silently — the DB update already happened and the graph will catch up on the next full export.

5. Confirm in one line: "BFF knowledge graph + Home dashboard updated — {Company} closed."

## Why this pattern

- DB is always master; the graph is a read-only view of application state.
- Hand-editing page properties is error-prone and creates sync drift.
- `export_graph.py` is the single source of graph truth for BFF's own graph, and `generate_home.py` is the single writer for the Home dashboard.
