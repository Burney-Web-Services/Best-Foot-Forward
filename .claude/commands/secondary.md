# secondary

## Purpose
Set up and open a secondary-sourcer session (e.g. a collaborator helping evaluate leads) that evaluates job leads for the primary seeker. Replaces the old file-bundle sync (`import-from-primary` / `export-to-primary`) with a live MCP connection to the primary's `best-foot-forward` server, plus a locally-cached grounding snapshot so scoring still works offline.

Run this once at the start of a sourcing session.

## Prerequisites
- `BFF_ROLE=secondary` in the environment (see `src/best_foot_forward/utils/config.py`). If it's not set, tell the user how to set it and stop.
- The `best-foot-forward` MCP server registered in Claude Code, pointing at the primary machine's Streamable HTTP endpoint `http://<primary-LAN-IP>:8765/mcp` with a bearer token minted on the primary via `scripts/mint_token.py --name <who>` (stored in the primary's `data/mcp_tokens.json`). If it's not registered, print the exact config block to add and stop.

## Workflow
1. **Confirm role.** Verify `BFF_ROLE=secondary`. If not, stop with instructions.
2. **Seed local grounding caches.** Call the `best-foot-forward` MCP tool **`get_profile_bundle`**. It returns JSON `{ version, exported_at, caches, memory }`. Write each entry:
   - Every key in `caches` (e.g. `_bullets.json`, `_bullets_conditional.json`, `_skills.json`, `_contact.json`, `_education.json`, `_employers.json`) → `data/<name>` verbatim.
   - `memory["user_profile.md"]` → `memory/user_profile.md`.
   These are the exact files evaluate-job reads, so scoring is now calibrated to the primary's live inventory and keeps working if the connection drops mid-session.
3. **Report grounding.** State counts: number of bullets (from `_bullets.json`), conditional bullets (from `_bullets_conditional.json`), skill groups (from `_skills.json`), and the bundle's `exported_at` date so the user knows how fresh the calibration is.
4. **If MCP is unreachable** (the `get_profile_bundle` call fails): report "Using previously cached grounding from <mtime of data/_bullets.json>" and continue. The session is fully offline-capable as long as the caches were seeded at least once before.
5. **Print the session contract:**
   > Paste a JD (text, file, or URL) to evaluate. Each lead pushes to BFF main immediately when online (`sync_leads`), or queues as a local `#Lead` page in the `bff-leads` graph when offline. Run `/push-leads` (or `/cleanup`) before you quit to drain any queued leads.

## Notes
- `get_profile_bundle`, `get_bullets`, `get_skills`, and `get_career_profile` are the only MCP tools that work from a secondary — the DB-backed tools (`get_active_leads`, `get_application_summary`, …) are primary-only and will refuse.
- This command does not touch SQLite; the secondary has no BFF database of its own.
