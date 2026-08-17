# Hook: Regenerate BFF Logseq Graph Page + Home Dashboard on Application

**Trigger:** on_application
**Requires:** Python 3.11+, `best_foot_forward` package (bundled with BFF)

## Instructions

After both .docx files are generated for a new application:

1. Get `COMPANY` from `data/session/resume_data.py` (the last tailoring session).

2. Run: `python3 -m best_foot_forward.utils.export_graph --only '{COMPANY}'`
   - Execute from the BFF project root.
   - This generates/updates `{Company}.md` and `{Company}/{Role}/Application.md` pages directly from the current DB state.
   - By this point, `track_application.py` (or `generate_resume.py`'s own inline tracking) has already inserted the application record into the database (status='applied', stage='application', applied_at=today).

3. Run: `python3 -m best_foot_forward.utils.generate_home`
   - Execute from the BFF project root.
   - This regenerates `Home.md` and `Leads Dashboard.md` (and stamps the Sèvo pulse
     if `BFF_SEVO_GLANCE` is set) so "Recently applied" picks up the new application
     immediately instead of waiting for a prep doc or a manual run.

4. If either command isn't available or fails (e.g., permission denied), skip silently. The DB update already happened; the graph and dashboard will catch up on the next scheduled export.

5. Confirm in one line: "BFF knowledge graph + Home dashboard updated — {Company} / {Role}."

## Why this pattern

The database is the source of truth. `export_graph.py` is the only graph writer for BFF's own graph, and `generate_home.py` is the only writer for the Home dashboard — both just resync from the current DB state, so running them after any application is always safe and idempotent. Previously only the `on_prep` hook did this, which meant a new application's `Home.md` entry only appeared once you later ran interview/screening prep for it — not right after applying.
