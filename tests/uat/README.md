# UAT harness

Three tiers (design: `~/.claude/plans/i-put-an-example-groovy-zephyr.md`):

- **Tier 0** — the deterministic pytest suite (`tests/test_jd_skills.py`,
  `test_docs_grounding_paths.py`, etc.). Runs in the normal `pytest tests/`
  invocation, zero cost. Most of the value; not in this directory.
- **Tier 1** — this directory's `run_uat.sh` + `test_uat_pipeline.py`. Real
  headless `claude -p` calls against a throwaway `BFF_DATA_DIR` seeded from
  `examples/leia-organa`. Real API cost (roughly a few minutes and a few
  dollars for a full pass with the model comparison). **Not run in CI.** Run
  before a release, or after touching `.claude/commands/evaluate-job.md`,
  `save_lead_jd.py`, or `jd_skills.py`.
- **Tier 2** — `CHECKLIST.md`. Qualitative, human-read.

## Running Tier 1

```
BFF_DATA_DIR=/tmp/uat-$(date +%s) tests/uat/run_uat.sh
BFF_DATA_DIR=<same dir> .venv/bin/python3 -m pytest tests/uat/test_uat_pipeline.py -v
```

`run_uat.sh` refuses to run unless `BFF_DATA_DIR` is set, its basename starts
with `uat-`, and it doesn't resolve to the real repo's `data/` — see the
script for why. It seeds the persona (which alone loads the real 7-posting
`examples/leia-organa` fixture — no live call needed for that part), then
runs one real `/evaluate-job` call against `fixtures/gap_posting.txt` (a
posting with three deliberate, unambiguous gaps against the Leia persona's
skills: GCP, ArgoCD, Snowflake).

`test_uat_pipeline.py` then asserts against the resulting DB and never makes
a network call itself — it only inspects what `run_uat.sh` already left
behind, so it's safe to include in a normal `pytest tests/` run (it
self-skips when `BFF_DATA_DIR` isn't pointed at a real run).

As of 2026-08-16, `examples/leia-organa` carries **7** postings — the
original 6 from the real roleplay session, plus Coruscant Systems Group
(the same posting as `fixtures/gap_posting.txt`, folded into the fixture as
its own scored-but-undecided lead so the onboarding demo itself shows a
posting with real, unambiguous gaps). Because of that, **every assertion in
this file now passes off the free seeding step alone** — `BFF_DATA_DIR=<dir>
python3 -m best_foot_forward.utils.load_example_data examples/leia-organa`,
no live `claude -p` call required. The live call in `run_uat.sh` still has
real value beyond that: it's the only thing that exercises the actual
`.claude/commands/evaluate-job.md` prompt end to end and *overwrites*
Coruscant's seeded score with a fresh live one, which is what makes
`test_gap_posting_scored` / `test_gap_posting_names_the_real_gaps` a live
regression check rather than a fixture tautology when a real run backs them.
Groups of assertions:
- **From the fixture load alone**: the six original postings' known scores
  match `examples/leia-organa/README.md`'s provenance table, exactly one
  `jds` row per company (the 2026-08-15 duplicate-row regression check),
  `jd_required_skills` indexed for all six, the two tailored applications
  (Obroa-skai, Scarif) actually produced `.docx` files and an `applications`
  row, Nar Shaddaa's real decline and Obroa-skai's real screen-stage +
  contact replayed (the 2026-08-16 loader extension), and the one
  `/star-story` capture loaded with its theme links.
- **Coruscant Systems Group / `gap_posting.txt`**: scored, and its three
  deliberate gaps (GCP/ArgoCD/Snowflake) indexed. True from the static seed
  alone; a live `run_uat.sh` pass re-verifies it against the real model.

## Haiku vs Sonnet model comparison

```
tests/uat/compare_eval_models.sh
```

Re-runs `/evaluate-job` against the same `gap_posting.txt` twice — once per
model, via the `BFF_EVAL_MODEL` override `evaluate-job.md`'s subagent-spawn
step honors — each in its own isolated data dir. Prints a banned-phrase scan
and a named-gap check for both, then points at the full saved replies. See
`CHECKLIST.md` §2 for how to read the output; the scan is a lead, not a
verdict.

This isn't re-deciding the model — Sonnet already won and is the shipped
default; see the numbers documented in `evaluate-job.md`'s Workflow step 3.
It exists so that decision has durable, re-runnable evidence instead of
living only in a session transcript.

## Driving the harness with a non-Claude agent (local models)

`run_uat.sh` hardcoded `claude -p` until 2026-08-17. It now takes a runner:

```
BFF_DATA_DIR=/tmp/uat-$(date +%s) \
BFF_UAT_RUNNER=custom \
BFF_UAT_OUTER_MODEL="ollama:qwen3.5" \
BFF_UAT_AGENT_CMD='codex exec --oss --local-provider ollama -m qwen3.5 --sandbox workspace-write --skip-git-repo-check -' \
  tests/uat/run_uat.sh
```

The command gets the prompt on **stdin** and must print the agent's final reply
on stdout; the script wraps that in the same envelope the `claude` path emits,
so every downstream check (banned-phrase scan, named-gap check, history row) is
identical. Runs land in history as harness `run_uat_custom` — a separate value
so a local-model run never averages in with the hosted baseline. Cost is
recorded as `$0`, which is the literal truth and the point of the exercise.

`BFF_UAT_RUNNER` defaults to `claude`, and that path is unchanged.
`BFF_UAT_HISTORY_DB` redirects history writes, for smoke-testing the harness
itself without dirtying the tracked DB.

**`BFF_EVAL_MODEL` is not the knob for this.** It only reaches the scoring
subagent `evaluate-job.md` spawns, which is a Claude `Agent()` call and accepts
Claude aliases only. A local model has to replace the *harness*, not the
subagent.

### What was measured, 2026-08-17 (Toussaint: Quadro M1200 4GB, 31GB RAM)

Stage 0 (`can the model drive a two-step tool loop at all`) **passed** on
`qwen3.5` (9.7B Q4_K_M): correct tool order, second call's arguments derived
from the first call's result, distractor rejected. `codex exec --oss` connects
to Ollama with no proxy and issues real shell tool calls.

The blocker is throughput, not capability:

| | measured |
|---|---|
| generation | **~1 tok/s** |
| prefill | **~45 tok/s** |
| GPU offload | 36% (model exceeds 4GB VRAM) |
| 2-turn, 420-token toy loop | **184 s** |

A Leia-fixture `/evaluate-job` needs ~17k tokens of context before tool
definitions and turn accumulation — so one run is plausibly **30–90 minutes**
against ~2.5 minutes and $1.63 for Sonnet. Viable as a proof, not as a workflow,
on *this* hardware.

Two Codex/Ollama warnings that are noise, not faults: `Model metadata for
qwen3.5 not found` (Codex has no context-window entry for it, so set one
explicitly rather than trusting the fallback), and a `failed to refresh
available models` error because Ollama's `/v1/models` returns `data` where
Codex expects `models`.

`glm-4.7-flash` is **not** a candidate on this box: 19GB against ~5GB free RAM.

## UAT history

Both `run_uat.sh` and `compare_eval_models.sh` record every live run to
`tests/uat/uat_history.db` (tracked in git, schema in `uat_history.py`) — git
sha, tier, fixture, outer/eval model, score, cost, duration, banned-phrase
hits, and which of the deliberate gaps got named. This is what makes
"did evaluate-job get better or worse" a query instead of a memory:

```
.venv/bin/python3 tests/uat/uat_history.py report
.venv/bin/python3 tests/uat/uat_history.py report --fixture "Coruscant Systems Group" --limit 10
```

Recording happens automatically as part of a live run; nothing auto-commits
the updated `.db` file. Commit it (a normal commit, like any other change)
when a run is worth keeping as part of the project's history — a routine
pre-release check you don't care to keep doesn't need one.
