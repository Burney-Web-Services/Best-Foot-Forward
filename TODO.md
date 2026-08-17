# BFF — Open-Source Release Checklist

_Last reviewed 2026-08-16 (launch hygiene pass — see §10)._

## 10. Launch hygiene — [x] DONE 2026-08-16

Found by re-auditing the tracked tree after the docs voice pass, which had swept
`.claude/commands/` and the ADRs but not `TODO.md`, `docs/roadmap.md`, or `docs/architecture.md`.

- [x] **Residual personal data in tracked docs.** This file's §8 carried real compensation
      figures (base, first-year total, start date) and named the employer; `docs/roadmap.md` and
      `docs/architecture.md` named a real collaborator, cited a specific personal job application
      as a feature's motivation (including a live `jds` row id), and linked a private memory page.
      `CLAUDE.md` and `.claude/commands/resume-tailor.md` used the maintainer's actual home town
      as the `LOCATION_OVERRIDE` example, and framed the whole feature as NYC-specific when it's
      really "role's metro differs from your home city." All generalized.
- [x] **`uv run pytest` did not work** — a bare `pytest` invocation failed at *collection*, not
      on a test: `tests/uat/test_uat_history.py` imports `tests.uat`, which needs the repo root on
      `sys.path`. `python -m pytest` adds cwd implicitly and so masked it; `pytest` and
      `uv run pytest` don't. `CONTRIBUTING.md` has documented `uv run pytest` the whole time, so
      the first thing any new contributor ran would have errored out. Fixed by adding `"."` to
      `[tool.pytest.ini_options] pythonpath`. 432 passed, 14 skipped.
- [x] **No `.github/` at all.** Added: a `tests` workflow (Python 3.11/3.12/3.13 matrix, `dev`
      group only — `conftest.py` stubs the ML imports so the multi-GB `audio` group is
      unnecessary), three issue templates (bug, feature, and field feedback for the coaches /
      recruiters / early users `CONTRIBUTORS.md` asks for), a PR template, `SECURITY.md`, and
      `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1).
- [ ] **Not done, and the actual blocker: the public repo doesn't exist yet.**
      `Burney-Web-Services/Best-Foot-Forward` is private and empty, while
      `best-foot-forward.com` is live, indexed, and links to it from five places (including the
      JSON-LD `codeRepository` and the footer). Every "get the code" link 404s for the public
      until that repo is cut. Also then worth setting: repo topics, the homepage field, and a
      `v0.1.0` tag.

## 11. Local-model (Ollama) support — investigated, blocked, not yet a ticket

2026-08-17: tested whether BFF can run on a local Ollama model instead of a paid Claude/Codex
plan — "free as in beer" as well as freedom. Full writeup:
`bws` graph page `BFF-2026-0817-OllamaUAT`.

**Likely to work eventually, not proven yet.** `qwen3.5` (9.7B) correctly drove a multi-step
tool-call loop (read a catalog, then write a derived selection using the first result) — so
capability isn't the blocker. Two things are:

- **Throughput on current hardware (Toussaint, Quadro M1200 4GB VRAM).** ~1 tok/s generation.
  A Leia-fixture `/evaluate-job` needs ~17k tokens of context, extrapolating to 30–90 min per
  run vs. ~2.5 min / $1.63 for Sonnet. Proof-of-concept, not a usable workflow, on this box.
- **Harness integration.** Neither `codex exec --oss` nor `opencode` could be pointed at an
  Ollama server with an adequate context window: Codex's `--oss` path hardcodes its endpoint
  and force-pulls from the registry (rejects locally-built Modelfiles), and its custom
  `model_providers` path requires the Responses API, which Ollama doesn't serve. Default
  Ollama context is 4096 regardless of the model's advertised ceiling, and truncates
  **silently** rather than erroring — a real hazard if this is retried casually.

**Not opening a formal ticket yet** — needs a machine with real GPU headroom (Baldwin? a
future box) before Stage 2 (`/resume-tailor`, which must produce valid Python with real
bullet IDs — the actual product-blocking test) is worth attempting. When that hardware
exists, promote this to a ticket and pick up from the `bws` writeup.

## 1. History rewrite (required before public release) — [x] DONE 2026-07-23

Turned out `git filter-repo` was the right tool after all — the "too intertwined" note above
was overcautious. Actual scope, found by grepping full history (not just `memory/`/`data/`
paths, which undercounted it): PII lived in `memory/user_profile.md` + `memory/project_status.md`
(4 commits) **and** in several early, since-deleted root-level files (`migrate.py`, `config.py`,
`resume_data-pwb-original.py`, `resume_data-pwb-postscript.py`) that predate the `data/`
restructure. A live-looking Cloudflare token was also found in `.claude/settings.local.json`
history (17 commits, before it was gitignored) — same token flagged in §2 below, GitHub's push
protection caught it on the first push attempt.

**What actually ran:**
1. Full mirror backup before touching anything: `../BestFootForward-preScrub-backup.git` (still
   has the old history + dead token — local only, never pushed; fine to delete once you're
   confident you won't need it).
2. `git filter-repo --path memory/user_profile.md --path memory/project_status.md --invert-paths`
3. `git filter-repo --replace-text <file>` — content-redaction pass for the literal email/phone/
   city strings and the old Cloudflare token, across every blob on every branch (not just `main`).
4. Verified with `git rev-list --all | xargs git grep` for all four strings — zero hits.
5. Deleted and recreated `pburney/BestFootForward` on GitHub (same name/URL) — this was the actual
   fix for something a pure history-rewrite can't touch: merged PRs #1–#5 had left
   `refs/pull/N/head` refs on GitHub that stayed fetchable regardless of force-pushing `main`.
   Confirmed via `git ls-remote` before/after — old repo had 5 PR refs, new repo has none.
6. Pushed cleaned `main` only (12 other local feature branches, all already scrubbed too, were
   left unpushed — nothing in flight on any of them; push later if ever needed).
7. Real commit history preserved (89 commits) rather than squashed to one — better portfolio value
   than the original squash-to-orphan plan, and 197 tests still pass post-rewrite.

## 2. Security

- [x] **Rotated the Cloudflare API token** in `.claude/settings.local.json` (2026-07-23) — old
      token confirmed dead via Cloudflare's own verify endpoint, new token confirmed active.
- [x] Old token also purged from git history (see §1) — GitHub push protection caught it on
      first push attempt, which is what surfaced that it had been committed before the file was
      gitignored.
- [x] `.claude/settings.local.json`, `data/`, `memory/` are gitignored (no secrets/PII in tracked files).

## 3. Hardcoded paths

- [x] Migration tooling scrubbed: `export_graph` uses a local `title_to_filename` (no cross-repo
      import); `generate_home`'s Sèvo pulse is env-driven (`BFF_SEVO_GLANCE`, off by default).
- [x] `src/` is clean — path anchors derive from `db._root` (project-relative).
- [x] `web/mystery/start.sh` now clones `Mystery-Database-Administration` over **HTTPS** (was
      `git@github.com:...`, requiring an SSH deploy key on every machine that runs `/web`). The
      "never touch Paul's personal mystery6 checkout" doc language in `web.md` was already
      accurate — it never cloned from a local path, just referenced it in prose.
- [x] `.claude/commands/evaluate-job.md`'s personal absolute-path example replaced with an
      instruction to compute the current checkout's root rather than copy a literal path.

## 3a. `jds.file_path` matching (2026-07-20)

Root cause of the repeated silent-duplicate-row bug (Teaching Strategies, Beacon Biosignals,
Pfizer): `jds.file_path` is matched with exact-string SQL (`WHERE file_path = ?`) across
independently-run processes (`evaluate-job`'s raw SQL, `scan_jds.py`, `track_application.py`,
`generate_resume.py`/`generate_letter.py`) with no shared canonicalization — a path built relative
to a different cwd produces a different string and misses the lookup.

- [x] Added `db.resolve_jd_path()` — anchors a relative path at the project root and normalizes;
      wired into `scan_jds.py`, `track_application.py`, `generate_resume.py`, `generate_letter.py`.
      `evaluate-job.md`'s raw-SQL stub insert still must write absolute (it doesn't go through the
      helper), but is no longer the *only* thing standing between a typo and a duplicate row.
- [x] `track_application.py`'s "fail loudly on lookup miss" behavior (item 6 below) — done
      2026-08-16. See §6 for detail.

## 4. Example data & onboarding

- [x] `/onboard` offers an **explore-vs-build** entry (Phase 0): for a new user just kicking the
      tires, the AI loads sample data and **picks** a representative role to demo — the user
      doesn't choose a specific application.
- [x] **Create the bundled anonymized example dataset**: a fictional candidate + a few example
      `jds`/`applications`/pages — shipped in a tracked `examples/` (not gitignored `data/`), with a
      loader the explore path calls. _(This is the piece that makes the explore path real.)_
      Done via `examples/leia-organa/` + `load_example_data.py` (BFF-2026-0723-LeiaExampleDataset).
- [x] Replace any real sample data referenced in `docs/` with the anonymized example.
      `docs/example/LeiaOrgana/jds/*.odt` (anonymized via `scripts/anonymize_example_jds.py`,
      checked by `tests/test_example_jds_anonymized.py`) is now the only fixture under `docs/example/`.

## 5. Documentation

- [x] ADR-0008 (Logseq graph as pipeline master) written; ADR-0001 amended.
- [x] `docs/architecture.md` + `docs/reference.md` graph sections; `README.md` graph mention.
- [x] Slash-command session-path drift fixed (`data/session/…`).
- [x] Document env vars in `README`/`docs` — done 2026-08-16, `docs/reference.md`'s new
      "Environment variables" section (`BFF_ROLE`, `BFF_SEVO_GLANCE` for normal optional use;
      `BFF_DATA_DIR`, `BFF_UAT`, `BFF_CHAT_HEADLESS`, `BFF_EVAL_MODEL`, `BFF_CHAT_CLAUDE_BIN`,
      `BFF_UAT_CLAUDE_BIN` for dev/testing), linked from `docs/README.md`'s docs-structure list.
      `BFF_JD_ROOT` and `BFF_ILITIES_OUTPUT` were dropped from the list when the two one-off
      scripts that read them were deleted (see §10).
- [x] Review all `.claude/commands/` for user-specific context to templatize — done 2026-08-16.
      Real fixes, not just cosmetic: `star-prep.md`/`interview-prep.md`/`screening-prep.md` had a
      hardcoded personal absolute `PYTHONPATH=/data/BUSINESS/Burnilab/BestFootForward/src` that
      would have broken for any other clone (now a portable relative `PYTHONPATH=src`, matching
      how every other script invocation in these same files already works). `interview-prep.md`/
      `screening-prep.md`'s Section 1 instructions and example dicts referenced real prior
      employers (now generic: "your most recent employer" / "prior employers" / "WHY DID YOU
      LEAVE YOUR LAST ROLE?"). `write-thank-you.md` hardcoded the signature as `"-Paul"` in two
      places (now derived from `contact.name`; the stale hardcoded voice-guide snapshot section
      was also removed — the workflow already reads the real `memory/voice_guide.md` live).
      `web.md` referenced a specific personal absolute path as the "never touched" guarantee (now
      generic — the guarantee is about not touching *any* personal checkout, not one specific
      path). `accept-offer.md`'s worked example exposed real compensation figures and dates (now
      a `{placeholder}`-shaped template). `secondary.md` named a specific real person as the
      illustrative "who runs this" example (now generic).
      **The "which ship" decision — resolved 2026-08-16:** reviewed all 17 with Paul; conclusion
      was everything ships (all 17 are generic job-search workflows now that content is cleaned),
      but two categories are niche enough to call out rather than let a new user assume they're
      required: `/web` (pulls in a disposable Node.js clone) and multi-machine sync (`/secondary`,
      `/push-leads`) — both now flagged in a new README "Optional features" section. Also found
      and closed a real parity gap while reviewing: `.agents/skills/` (the Codex/Gemini/Antigravity
      mirror) was missing 4 of 17 (`accept-offer`, `capture-voice`, `push-leads`, `secondary`), and
      2 of the 13 that did exist had drifted from the established thin-pointer pattern —
      `cleanup/SKILL.md` was a stale 83-line full duplicate (predating the global-skill + BFF-
      extension unification `.claude/commands/cleanup.md` now uses) and `write-thank-you/SKILL.md`
      used a relative link one directory level short of resolving. All 17 now use the same
      `Read and execute the workflow defined in [X.md](../../../.claude/commands/X.md)` pointer,
      verified to actually resolve.
- [x] Confirm `README` setup instructions work from a clean clone — done 2026-08-16, and it
      wasn't just confirmation: found and fixed a real bug that would have hit every new user.
      `data/` is entirely gitignored, so a genuine fresh clone has no `data/` directory at all —
      `db.get_conn()` called `sqlite3.connect(DB_PATH)` straight away, which can create the DB
      *file* but not a missing parent directory, so the very first `init_db()` call (step one of
      `/onboard`) raised `sqlite3.OperationalError` before a single table existed. Fixed:
      `get_conn()` now `os.makedirs(DATA_DIR, exist_ok=True)` before connecting — one fix at the
      single chokepoint every DB access already goes through, rather than requiring each of its
      several dozen callers to remember to `mkdir` first. Regression test:
      `tests/test_db_data_dir_override.py::TestBffDataDirOverride::test_get_conn_creates_a_missing_data_dir`.
      Verified end to end: copied the full working tree to an unrelated path, ran `uv sync` clean,
      confirmed `init_db()` and the full test suite (428 passed) both pass with zero references
      back to the real checkout location.

## 6. Known bugs

- [x] **`track_application` JD-lookup mismatch** — fixed 2026-08-16. `evaluate-job` already
  specified **absolute** stub `file_path`s and the `/`-in-filename crash was already fixed; the
  remaining piece (a lookup miss silently inserting a duplicate scoreless `jds` row) is done: a
  `resolve_or_create_jd()` result of `"created"` inside `track_application.py` now rolls back and
  exits nonzero with an explanatory message instead of proceeding, since by the point this script
  runs (after `generate_resume.py`/`generate_letter.py` in the resume-tailor pipeline) a matching
  row should already exist — a miss means something upstream diverged, not a genuinely new JD.
  Tests: `tests/test_track_application.py`.
- [x] **`scan_jds` re-registers orphaned JD files** as duplicate rows — fixed 2026-08-16 (files
  left on disk when a `jds` row is deleted; surfaced with Commerce 2026-07-16). Both halves done:
  `scan_jds.py` now builds a canonical-company/role index (`company_normalize.canonical_company()` +
  `alnum_key()`) before walking the directory, and skips a file with no `file_path` match if an
  existing row already canonically covers the same company+role, rather than inserting a fresh
  duplicate — tests in `tests/test_scan_jds.py`. And row-deletion tooling now exists at all:
  `src/best_foot_forward/utils/delete_lead.py`, the single write path for removing a `jds` row,
  which also removes the JD file(s) on disk (so a later scan has nothing orphaned left to
  rediscover) and refuses to delete a lead with any `applications`/`contacts` row still attached —
  tests in `tests/test_delete_lead.py`. Documented in `CLAUDE.md`'s Database section.
- [x] **`db_query.py` ignored `BFF_DATA_DIR` entirely** — hardcoded `DB_PATH` relative to its own
      file instead of resolving through `db.py`'s `DATA_DIR` like every other script here. Found
      2026-08-15 building `tests/uat/`: a live UAT `/evaluate-job` run's score-persistence step
      (which writes via `db_query.py`) landed on the **real production DB**, silently overwriting
      real `jds.id=7` (DraftKings) with a fictional Leia Organa score/summary. Caught only by
      manually verifying the real DB after a headless self-report claimed (falsely, unverified)
      that it had already been reverted — see `tests/uat/CHECKLIST.md` §2 for the fuller story.
      Restored from a pre-session backup; swept the rest of the DB/audit log for other
      contamination (none found — blast radius was exactly this one row/columns). Fixed by
      resolving `DB_PATH` through `db.py`'s `DATA_DIR`, matching every sibling script; regression
      tests in `tests/test_db_query.py::TestBffDataDirIsolation`. `generate_home.py`'s
      `write_sevo_pulse()` had the same class of gap (a real, if self-healed, leak into
      `/data/Sèvo/pages/Home.md`) — also fixed, `tests/test_generate_home.py`.

## 8. Application lifecycle — offer acceptance

- [x] **BFF has no way to record an offer.** — Tooling DONE (BFF-2026-0813-OfferAcceptance).
      Eight offer columns on `applications` (not a separate table — see `docs/reference.md`'s
      "Offer acceptance" section), `offer_received`/`offer_accepted`/`declined_offer` stages,
      `record_offer.py` as the single write path (idempotent migration:
      `scripts/migrate_offer_columns.py`), and `/accept-offer` — records terms, concludes the
      application, and closes out the rest of the pipeline in exactly three questions
      regardless of size.
      - Surfaced 2026-08-07 by a real accepted offer with nowhere to go: the application sat at
        `stage = final_interview_complete`, `status = applied`, because no later stage existed.
        Exercised end to end 2026-08-13 — the application moved to `stage = offer_accepted`,
        `status = accepted`, with `concluded_at` and offer terms recorded. The closeout sweep ran
        in the same pass: applications with recent momentum withdrawn, stale ones marked
        `not_pursued`, open leads declined (`strategy`). 0 in motion afterward — a concluded
        search is now fully representable, which it wasn't before.
      - A related, more urgent bug was found while scoping this: `ghost_candidates()` didn't
        exclude `final_interview_complete` (or several other late-pipeline stages) from its
        staleness check, so the next `cli.py` run of any kind would have silently ghosted that
        exact application. Fixed and merged separately, first (PR #17).
      - Deferred, not built in this pass: a `/decline-offer` command file (routing-only, mirrors
        how rejection-logging already has no command file), a standalone Offers CLI report, and
        the salary-benchmark/scoring-calibration lookback this now makes possible — fast-follow.

## 7. Graph migration follow-ups (non-blocking)

- [ ] Optional: run `sync_files.py` to register the ~57 unregistered asset docs (thank-yous /
      LinkedIn notes) so they surface on pages.
- [ ] Optional: the transcribe/media pipeline still writes new recordings to `data/media/` (raw
      audio stays out of the graph by design; revisit if you want new transcripts auto-linked).

## 9. No test harness for the mystery6 plugins

_(Numbered 9 rather than 8 because the unmerged `todo/offer-acceptance` branch already claims
section 8.)_

- [ ] **BFF's four `web/mystery/plugins/` plugins have zero tests**, and there is no runner that
      could execute them. Deferred deliberately (2026-08-13) rather than skipped silently — the
      Burnilab tests-with-fixes default says a new endpoint ships with a test, and this is the
      standing exception.
      - Current state: `bff-reports`, `bff-chat`, `bff-graph`, `bff-about`. The reports plugin is
        the one that actually matters — its five reports were hand-verified for parity against
        `cli.py` once, in 2026-07-09, and nothing re-checks that they haven't drifted since.
      - Newest untested logic: `bff-graph`'s `/stats` endpoint and its `classify()` helper, which
        infers a page's kind from the `___` triple-lowbar filename convention. That convention has
        already broken twice (the 2026-07-16 `:file/name-format` bug, the 2026-07-22 basename
        collision) — it is exactly the kind of thing worth pinning down with a test.
        **A third instance, found 2026-08-16 (this is the "zero tests" gap making itself felt, not
        a coincidence): `bff-graph`'s own `GRAPH_ROOT` used `resolve(__dirname, '..', '..', '..')`
        — three levels, one short of the four `bff-chat`'s equivalent constant correctly uses —
        so it resolved to a path that never existed and `/stats` silently reported
        `available:false, total:0` for every single user, not just under `BFF_DATA_DIR`. Found
        while adding `BFF_DATA_DIR` support to `setup.mjs` and this plugin (so `/web` can point at
        a demo/UAT dataset, e.g. `BFF_DATA_DIR=/path/to/demo ./web/mystery/start.sh`) and actually
        checking the result instead of assuming the endpoint already worked. Fixed; no test exists
        to catch a regression, which is exactly this item's point.**
      - **The structural blocker**: BFF is a Python project (pytest). The plugins are JS, and they
        live outside mystery6's test root — they're symlinked into a *disposable* clone at
        `web/mystery/app/src/plugins/`, which `link.sh` rebuilds. So mystery6's own vitest run
        can't be relied on to cover them, and BFF has no JS runner of its own.
      - Two ways out, both real decisions rather than chores: (a) add vitest to BFF and colocate
        `plugins/<key>/tests/*.test.js`, following the pattern mystery6's own `mixtape` example
        plugin already uses; or (b) push the plugins upstream into mystery6 proper, where the
        harness already exists — which only makes sense for ones that aren't BFF-specific.
