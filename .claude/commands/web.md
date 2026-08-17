# web

## Purpose
Launch "BFF-Web" — a local, self-contained mystery6 web UI for browsing BFF's live database, with
the BFF-Chat plugin embedded — no manual cloning, config-copying, or process management required,
and safe to run repeatedly. Read-only (bff/Viewers permissions enforced at the app layer).
Auto-logs in when the cloned mystery6 checkout supports `NO_AUTH`; otherwise reports the
`bff`/`bff` login.

## Input
Optional port number as the command argument (e.g. `/web 3072`). Defaults to `3071`.

Set `BFF_DATA_DIR` before invoking to point the whole UI at a different dataset (e.g. a
demo/UAT fixture) instead of the real `data/` — same override `db.py` and the UAT harness
use. Since the underlying clone and its `.env` are shared, don't run two `/web` instances
against two different `BFF_DATA_DIR`s at once; the later one's `setup.mjs` run wins for any
new server process. Reasonable to use the same port each time if you're switching between
"real" and "demo" rather than running both simultaneously.

## Workflow

Run from the BFF project root:
```bash
./web/mystery/start.sh "${1:-3071}"
```
`start.sh` is the single-script version of this whole workflow (already-running check, dedicated
clone, dependency install, symlink wiring, DB config, detached launch, readiness poll) — kept as
one script specifically so this collapses to **one** permission prompt instead of one per step.
See the script itself for the step-by-step breakdown; the notes below cover the *why* behind
choices baked into it.

It prints exactly one line on success or failure:
- `ALREADY_RUNNING http://localhost:$PORT` — stop here, do not re-clone/re-install/reconfigure/
  restart, just show the user the link.
- `PORT_CONFLICT $PORT` — something other than our tracked instance is already listening on
  `$PORT`. Report the conflict and ask the user to free the port or pass a different one. Do not
  silently pick another port or kill an unrelated process.
- `UP http://localhost:$PORT NO_AUTH=1` or `NO_AUTH=0` — success.
- `FAILED_TO_START` followed by a `server.log` tail — surface that tail to the user and stop.

### Design notes carried over from the step-by-step version
- **Dedicated clone**: never touches any personal `mystery6` checkout you might separately
  have on this machine — always the disposable `web/mystery/app/`.
- **`setup.mjs`**: idempotent — reuses `data/mystery-config.db` if it exists (table/permission
  setup only ever happens once, across any number of clone rebuilds), but always rewrites
  `web/mystery/app/.env` since that lives inside the disposable clone. Auto-detects `NO_AUTH`
  support in the cloned checkout (see [[Mystery/NO_AUTH Localhost Mode]] in the BWS knowledge
  graph).
- **Detached launch**: `node src/server.js` directly (no `npm start` indirection), absolute path,
  no `cd` first — combining `cd dir && nohup ... &` on one line would background the whole
  `cd && nohup` pipeline as a subshell, and `$!` would capture the *subshell's* PID rather than
  the real node process, leaving a stale pidfile.

### Report to the user
On `UP`, reply with exactly this shape:
```
BFF-Web is Online!
Visit http://localhost:$PORT

      __|__
     | n_n |
     |_____| 4/
    --[ <3]--/
   /  [___]
       |  \
       /_ /_

{{BFF-Web Summary}}
```
Where `{{BFF-Web Summary}}` is the same "N applications complete. Last: Company — Role." line
used for the session-startup greeting (derive from `memory/project_status.md`, same as CLAUDE.md's
"Session Startup" step — no new DB query needed).

Add "log in as `bff` / `bff`, read-only viewer" only if `NO_AUTH=0`; omit entirely when
`NO_AUTH=1` (auto-login). No mention of WAL journal mode or other implementation detail — this is
meant to read as a fun one-liner, not a status report.

The ASCII art is hand-tuned — reproduce it verbatim, character for character, rather than
regenerating or "fixing" its alignment.

## Notes
- Never touches any personal `mystery6` checkout you might separately have — always a
  fresh, disposable clone at `web/mystery/app/`, fully gitignored.
- No auto-shutdown: a server spawned by `/web` keeps running until stopped manually — by design,
  so multiple instances (e.g. on different ports, for testing) can coexist without one session's
  cleanup taking down another's server.
- To stop the server manually at any time: `./web/mystery/stop.sh` (only acts on the PID in its
  own `server.pid`, never hunts for other mystery6 instances) or
  `kill $(cat web/mystery/server.pid) && rm web/mystery/server.pid`.
- To force a hard refresh of the clone (e.g. after a mystery6 upstream change like NO_AUTH
  landing): `rm -rf web/mystery/app web/mystery/server.pid web/mystery/node_modules` and re-run
  `/web`. `data/mystery-config.db` (the permissions/table config) survives this and does not
  need to be recreated.
- If `npm start`'s script in mystery6 ever stops being a bare `node src/server.js` passthrough,
  switch step 6 to launch via `npm start` and discover the real PID afterward with
  `lsof -t -iTCP:$PORT -sTCP:LISTEN` instead of relying on `$!`.
- **Resolved — the old "`server.pid` goes missing between turns" issue** (observed 2026-07-08)
  was root-caused 2026-07-10: it wasn't a pidfile bug at all. This project's `.claude/settings.json`
  used to register a `SessionEnd` hook running `stop.sh` on every session end — including the
  one-shot headless `claude -p` sessions spawned per-turn by the `bff-chat` plugin, each of which
  could kill the mystery6 server out from under it. The hook (and `stop.sh`'s cross-process
  `pgrep` fallback that made it dangerous) has been removed; see
  `~/.claude/plans/bff-story-bot-issue-elegant-otter.md` for the full writeup.
