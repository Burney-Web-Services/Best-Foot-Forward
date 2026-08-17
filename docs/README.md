# Best Foot Forward — Project Docs

## What this is

Best Foot Forward turns a career's worth of context — projects, decisions, stories, results — into a structured professional memory, then draws on it conversationally through a coding agent to evaluate job fit, tailor resumes and cover letters, and track the full application lifecycle. See the [top-level README](../README.md) for the pitch. This is the index for how it's actually built.

The codebase serves two purposes at once:

1. **A working job-search tool**, in daily use during a real 2026 search.
2. **A generalizable agent.** The bullet library, skills library, freeform tracks and themes, `evaluate-job`, and `resume-tailor` are the portable kernel. The goal is that anyone who arrives with a single resume can use it.

## Docs structure

- [`commands.md`](commands.md) — What each workflow does, when to reach for it, and what it produces.
- [`architecture.md`](architecture.md) — Mermaid diagrams: database schema, data layer, Logseq graph, tailoring pipeline, gap tracking, secondary-machine sync.
- [`reference.md`](reference.md) — Data directory layout, table descriptions, decline categories, offer columns, file registry, utility modules, environment variables.
- [`machine-setup.md`](machine-setup.md) — Per-machine agent configuration, and what has to be deployed by hand.
- [`roadmap.md`](roadmap.md) — Features under consideration, with status and rationale.
- [`adr/`](adr/) — Architecture Decision Records. Significant design choices and what follows from them.
- [`example/LeiaOrgana/`](example/LeiaOrgana/jds/README.md) — Source material for the bundled example persona: her resume, a STAR story, a voice sample, and six anonymized job postings.

The loadable example dataset itself lives outside `docs/`, at [`examples/leia-organa/`](../examples/leia-organa/README.md). `/onboard`'s explore path loads it via `python3 -m best_foot_forward.utils.load_example_data`.

## Key files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project instructions loaded into every Claude Code session |
| `AGENTS.md` | The same contract for Codex, Gemini, and Antigravity |
| `.claude/commands/` | Canonical workflow definitions |
| `.agents/skills/` | Per-workflow skill wrappers that point other agents at the same definitions |
| `src/best_foot_forward/schema.sql` | The full SQLite schema, with column comments |
| `data/best_foot_forward.db` | SQLite source of truth (gitignored) |
| `data/_bullets.json` | Read cache of the bullet library — generated, do not edit directly |
| `data/_skills.json` | Read cache of the skills library — generated, do not edit directly |
| `src/best_foot_forward/utils/export_cache.py` | Regenerates all JSON caches from SQLite |
| `src/best_foot_forward/utils/generate_resume.py` | Produces the `.docx` resume from `data/session/resume_data.py` |
| `src/best_foot_forward/utils/generate_letter.py` | Produces the `.docx` cover letter from `data/session/letter_data.py` |
| `src/best_foot_forward/cli.py` | Reporting CLI (see below) |
| `src/best_foot_forward/mcp_server.py` | MCP server exposing profile, leads, and story reads |

## Reports

`python3 src/best_foot_forward/cli.py` opens an interactive menu; any key can also be passed as an argument (`cli.py gaps`).

| Key | Report |
|---|---|
| `upcoming` | Upcoming dates |
| `ghosts` | Ghost candidates |
| `followup` | Follow-up queue |
| `leads` | Pending leads (sourced) |
| `declined` | Declined leads |
| `patterns` | Decline patterns |
| `weekly` | Weekly activity |
| `matches` | JD match scores |
| `passes` | Pass/decline analysis (companies that rejected you) |
| `skills` | Top demanded skills |
| `gaps` | Skill gaps |
| `companies` | Skills by company |
| `salaries` | Salary ranges |
| `full` | All four skills reports at once |

---

## Secondary mode — sourcing leads with a collaborator

BFF supports a two-machine workflow where a collaborator, say a sourcer or a recruiter, evaluates job descriptions on their own machine and sends scored leads back for review. It runs over the **`best-foot-forward` MCP server**, with no file bundles to hand-carry, and a local grounding cache so scoring still works offline.

### One-time setup

**On the primary machine**, run the MCP server over the LAN and mint a token for the collaborator:

```bash
uv sync --group http                               # aiohttp, needed for --serve
python3 scripts/mint_token.py --name alex          # prints a bearer token (once)
python3 src/best_foot_forward/mcp_server.py --serve 8765
```

**On the collaborator's machine**, clone and `uv sync`, set `BFF_ROLE=secondary` in the environment, and register the `best-foot-forward` MCP server pointing at `http://<primary-LAN-IP>:8765/mcp` with the bearer token.

### Each sourcing session

**Step 1 — the collaborator runs `/secondary`.** It pulls the current grounding bundle over MCP (`get_profile_bundle`) and writes the local `data/_bullets*.json`, `_skills.json`, `_employers.json`, and `memory/user_profile.md`. Scoring is now calibrated to the primary's live inventory, and keeps working if the connection drops.

**Step 2 — the collaborator evaluates JDs normally**, from pasted text, a file, or a URL. For each scored lead:

- **Online**, it pushes straight to the primary via the `sync_leads` MCP tool. The lead is inserted into `jds` as `lead_status='pending'`, attributed to the caller's authenticated identity, with the posting `url` and fit `summary`.
- **Offline**, it queues as a `#Lead` page (`pushed:: false`) in a local `bff-leads` Logseq graph.

**Step 3 — the collaborator runs `/push-leads`** (or `/cleanup`) before quitting. It drains any queued `#Lead` pages to the primary and marks them `pushed:: true`. Dedupe is by `(company, role)`: new leads insert, re-scored ones update, so re-running is safe.

The primary sees new leads immediately in the web Leads report, the Logseq Leads Dashboard, the `get_active_leads` MCP tool, or the CLI:

```bash
python3 src/best_foot_forward/cli.py leads
```

From there, decide which to pursue and run `/resume-tailor` on the ones that warrant it.

---

## Migrating from an existing resume system

If you've been managing resumes outside BFF — a folder of tailored Word docs, a Google Docs library, a spreadsheet of bullet points — the agent can bring that history in rather than starting from scratch.

Run `/onboard` first to establish your profile and base resume. Then share your existing materials in a follow-up session and ask for them to be extracted and loaded. Prompts that work well:

- **Bulk bullet extraction** — "I have a folder of tailored resumes at `~/Documents/Resumes/`. Read through them and add any bullets not already in the library to SQLite, tagged with the appropriate employer, tracks, and themes."
- **Single resume import** — "Here's a tailored resume I wrote for a product manager role. Extract the bullets that differ from my base resume and add them, tagged for management scope."
- **Skills consolidation** — "Compare the skills sections across these three resumes and suggest how to consolidate them into the skills library."

The agent reads the files, diffs against the existing library, inserts new records via `db_query.py`, and runs `export_cache.py` to regenerate the JSON caches. The result is a bullet library that reflects everything you've already written, not just what you produce going forward.

`/intake-artifacts` does the same job for non-resume material: git logs, PR descriptions, architecture docs, performance reviews.
