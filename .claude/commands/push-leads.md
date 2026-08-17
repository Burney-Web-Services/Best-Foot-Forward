# push-leads

## Purpose
Drain the secondary machine's locally-queued `#Lead` pages (evaluated while offline) up to the primary's BFF database via MCP. The online counterpart of the offline branch of `/evaluate-job`.

Run on a **secondary machine** (`BFF_ROLE=secondary`) when the `best-foot-forward` MCP server is reachable again — and automatically as part of `/cleanup`.

## Workflow
1. **Find queued leads.** Use the `markdown-graph` MCP tool `list_pages` (graph `bff-leads`) to list `#Lead` pages, then read each with `read_page`. A lead is unpushed when its `pushed::` property is absent or `false`.
   - If there are none, report "No queued leads to push." and stop.
2. **Parse each page** into a lead object: `company`, `role`, `score`, `salary_min`, `salary_max`, `salary_currency`, `url`, `summary` (the `## Summary` body), `required_skills` (from the `## Required skills` list), `evaluated_at` (from `evaluated::`).
3. **Push in bulk.** Call the `best-foot-forward` MCP tool **`sync_leads`** with the full array. It dedupes by `(company, role)` — new leads insert, existing ones update (score/url/summary/salary refreshed), so re-running is safe. Report the returned `imported/updated/skipped` counts.
4. **Mark pushed.** For each successfully-pushed page, set `pushed:: true` via the `markdown-graph` tool `set_property` (graph `bff-leads`) so it isn't pushed again. (Alternatively, move it to a `bff-leads/archive` namespace.)
5. **Report** a one-line summary: N pushed, M updated, K already present.

## Notes
- Requires the MCP server reachable. If `sync_leads` fails (offline), leave the pages `pushed:: false` and tell the user to retry later — nothing is lost.
- `sync_leads` is primary-gated on the server side but callable from a secondary over the authenticated connection (it runs against the primary's DB). The lead's `source` is set from the caller's bearer-token identity (e.g. `alex`), not from the page.
- This is idempotent: a page left `pushed:: false` after a failed run is simply retried next time.
