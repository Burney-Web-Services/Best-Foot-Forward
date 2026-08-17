# Hook: Regenerate BFF Logseq Graph Page + Home Dashboard on Prep

**Trigger:** on_prep
**Requires:** Python 3.11+, `best_foot_forward` package (bundled with BFF)

## Instructions

After a prep doc (`interview-prep`, `screening-prep`, or `star-prep`) has been
generated and registered in `file_registry`:

1. Get `COMPANY` from the prep session file used for this run (`data/session/prep_data.py`
   for interview/screening prep, `data/star_data.py` for STAR prep).

2. Run: `python3 -m best_foot_forward.utils.export_graph --only '{COMPANY}'`
   - Execute from the BFF project root.
   - This rebuilds `{Company}.md` and `{Company}/{Role}/Application|Prep.md` from the
     current DB state, picking up the prep file just registered.

3. Run: `python3 -m best_foot_forward.utils.generate_home`
   - Execute from the BFF project root.
   - This regenerates `Home.md` and `Leads Dashboard.md` (and stamps the Sèvo pulse
     if `BFF_SEVO_GLANCE` is set) so the dashboard reflects the new prep doc / stage.

4. If either command isn't available or fails (e.g., permission denied), skip
   silently. The DB update already happened; the graph and dashboard will catch up
   on the next scheduled export.

5. Confirm in one line: "BFF knowledge graph + Home dashboard updated — {Company}."

## Why this pattern

The database is the source of truth. `export_graph.py` is the only writer for BFF's
graph, and `generate_home.py` is the only writer for the Home dashboard — both just
resync from the current DB state, so running them after any prep registration is
always safe and idempotent.
