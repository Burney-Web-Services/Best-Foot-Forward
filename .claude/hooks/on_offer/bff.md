# Hook: Regenerate BFF Logseq Graph Page + Home Dashboard on Offer

**Trigger:** on_offer
**Requires:** Python 3.11+, `best_foot_forward` package (bundled with BFF)

## Instructions

After recording an accepted offer in BFF (DB already updated: `applications.stage='offer_accepted'`, `status='accepted'`, `concluded_at` set, offer terms written via `record_offer.py`):

1. Get `COMPANY` from the offer-recording context.

2. Run: `python3 -m best_foot_forward.utils.export_graph --only '{COMPANY}'`
   - Execute from the BFF project root.
   - Regenerates `{Company}.md` and `{Company}/{Role}/Application.md` from current DB state.
   - Properties like `status::`, `stage::`, and `concluded::` are written by `export_graph.py` — do not hand-edit.

3. Run: `python3 -m best_foot_forward.utils.generate_home`
   - Execute from the BFF project root.
   - Regenerates `Home.md`, `Leads Dashboard.md`, `Declined Leads.md`, and `Applications Dashboard.md` (and stamps the Sèvo pulse if `BFF_SEVO_GLANCE` is set), so the new "🎉 Offers" block appears and the accepted application — plus everything closed out alongside it in `/accept-offer`'s Phase 4 — leaves the "In motion" rollup immediately rather than waiting for the next application or prep run.

4. If either command isn't available or fails (e.g., permission denied), skip silently. The DB update already happened; the graph and dashboard will catch up on the next scheduled export.

5. Confirm in one line: "BFF knowledge graph + Home dashboard updated — {Company} offer accepted."

## Why this pattern

The database is the source of truth for all application state. `export_graph.py` is the only writer to BFF's graph and `generate_home.py` is the only writer for the dashboards — both resync from current DB state, so running them after an accepted offer is always safe and idempotent.

Accepting has wider blast radius than a rejection: one application concludes, and the withdraw/not-pursue sweep in `/accept-offer`'s Phase 4 can conclude dozens more in the same session. Regenerating the whole dashboard set — not just the accepted company's pages — is what makes the board reflect a finished search in one pass, matching the reasoning `on_rejection/bff.md` already applies to the smaller single-application case.
