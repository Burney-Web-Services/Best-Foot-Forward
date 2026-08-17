# UAT Tier 2 — qualitative checklist

Things Tier 0 (pytest) and Tier 1 (`run_uat.sh` + `test_uat_pipeline.py`) can't
assert programmatically. Read `run_uat.sh`'s `evaluate_job_reply.json` (or
`compare_eval_models.sh`'s `reply-*.txt` files) and go through this by hand.
Each item is seeded with the actual historical finding it exists to catch —
that's what "here's what this looked like when it broke" means below.

Run before a release, and after touching any `.claude/commands/*.md`.

## 1. Gap-phrasing smell test

Read the gap-risk dimension and `top_gap` in the reply. A well-formed gap
section reads like a diff, not a pep talk.

- [ ] No compensating clause attached to a named gap ("but", "though",
      "however", "that said", "strong foundation", "would ramp quickly",
      "quick study", "transferable", "adjacent experience").
- [ ] No adjacency-as-evidence reasoning (Terraform ≠ evidence for Pulumi,
      Kubernetes-on-AWS ≠ evidence for GKE).
- [ ] Every capability claim traces to a specific bullet/skill id — if you
      can't find the id in `data/_bullets.json`/`_skills.json`, the claim is
      unsupported.

**Here's what this looked like when it broke:** the real Leia roleplay run
(2026-08-14/15, before this guardrail existed) produced "No Kubernetes in the
bullet library, though the Docker and Terraform work suggests they'd ramp
quickly" — an unsupported prediction delivered in a reassuring tone, for a
requirement the profile genuinely didn't have. `compare_eval_models.sh`'s
`gap_posting.txt` GCP/ArgoCD/Snowflake gaps are deliberately shaped the same
way (real platform-engineering adjacency, real absence) to keep re-triggering
this specific failure mode if it comes back.

## 0. Verify any headless self-report before trusting it

**Run 2026-08-15 confirmed this needs to be step zero, not an afterthought.**
Running this harness for real (the first live pass) turned up a genuine bug:
`generate_home.py`'s Sèvo cross-graph pulse write and `db_query.py`'s score
persistence both ignored `BFF_DATA_DIR` entirely, and a live UAT
`/evaluate-job` run's fictional score briefly overwrote a **real** production
`jds` row (id=7, DraftKings) — confirmed by manually reading the real DB
before and after, not by trusting the model's own account. Both bugs are
fixed now (`tests/test_generate_home.py`, `tests/test_db_query.py::
TestBffDataDirIsolation`).

The more important finding: **both Haiku and Sonnet, on noticing the issue,
reported false remediation.** Sonnet claimed "reverted it immediately and
saved a memory" — every one of its own verification/write attempts had
actually been permission-denied, and no memory file was ever created. Haiku
gave a more grounded account (it had genuinely observed live contamination
and attempted a real revert) but the revert didn't stick — a *later* run
re-contaminated the same row, undetected, because nothing re-checked after
the fact. Neither model's session ever finished its actual assigned task
(the JD's `score`/`summary` were still NULL in both throwaway DBs) — both
abandoned it entirely once they thought they'd found something else to fix.

**Before trusting ANY "I found X and fixed it" line in a headless UAT
reply:** re-verify independently against the actual state (git diff, direct
DB query, `find -newer`) — do not update this checklist, close a ticket, or
report success to Paul based on the model's own narration alone. This
applies doubly to claims about touching state *outside* `$BFF_DATA_DIR`.

**Run 2026-08-16 added a sharper version of the same lesson: `is_error:
false` is not evidence the call did the thing it was sent to do.** A live
`run_uat.sh` pass exited clean but the reply was a greeting-plus-refusal —
Claude Code's own project-memory (keyed by cwd, unreachable via
`BFF_DATA_DIR`) had leaked a real applicant count and a real accepted offer
into the session's greeting, the model noticed the mismatch against a UAT
test posting and correctly stalled rather than guessing, and nothing about
that shows up as `is_error: true`. Only caught by reading `jq -r '.result'`
directly and checking whether `jds.evaluated_at`/`score` actually changed.
Root cause fixed in `CLAUDE.md`'s Session Startup section (`BFF_UAT` now
skips the `memory/project_status.md` read entirely). **Don't treat a clean
exit code as a passing run** — read the reply text and diff the DB state
every time, the same way §0's original lesson already requires for
self-reported fixes.

## 2. Haiku vs Sonnet — re-validating the model choice

`.claude/commands/evaluate-job.md`'s Workflow step 3 documents a one-time
side-by-side that already picked Sonnet as the default (29/100, 2/20
technical match on a zero-overlap JD, vs. Haiku's 53/100 and 8/20 on the
same JD). `compare_eval_models.sh` re-runs that comparison against
`gap_posting.txt` so the decision has durable, re-runnable evidence instead
of living only in a session transcript.

- [x] Both replies actually name GCP, ArgoCD, and Snowflake as gaps (not
      hedged past recognition). **Confirmed 2026-08-15** (clean re-run, after
      the isolation bugs above were fixed): both did, cleanly.
- [x] Compare each model's overall score and technical-match dimension for
      this posting. **2026-08-15 result:** Haiku scored 73/100 (Technical
      11/20, Gap risk 8/20); Sonnet scored 58/100 (Technical 7/20, Gap risk
      4/20) — Sonnet still calibrates markedly lower/harder against the same
      three named gaps, consistent with the original evaluate-job.md finding.
- [x] Compare gap-risk prose directly. **2026-08-15:** neither volunteered
      adjacency-conflation reasoning. Haiku's reply actually contains the
      word "transferable" (flagged by the automated scan) but on read it's
      the opposite of the bias — "*Be direct about the stack gap ... rather
      than framing it as transferable*" is Haiku explicitly instructing
      itself away from the trap. Textbook example of why the scan is a lead,
      not a verdict (§0's point applies here too, more mildly: read before
      concluding).
- [x] Haiku's reply is now comparably disciplined on *gap language*
      specifically — the prompt-level "Gap reporting rules" guardrail seems
      to have closed most of that gap since the original pre-guardrail test.
      What hasn't converged is **score calibration**: a 15-point spread
      (73 vs 58) on the same JD with the same three named gaps. That's the
      part still justifying Sonnet as the default, more than gap-language
      alone would. **2026-08-16 re-run:** 63 vs 58, a 5-point spread — same
      direction (Sonnet still lower/harder), but notably narrower. n=2 isn't
      enough to call this a trend; it's exactly what `uat_history.db` exists
      to track. Don't hand-transcribe every future run's numbers into this
      file — check current numbers with `python3 tests/uat/uat_history.py
      report --fixture "Coruscant Systems Group"` instead, and only add a
      prose note here if a run is qualitatively surprising (a fabricated
      claim, a regression, gap language backsliding).
- [ ] If either model regresses relative to the numbers already documented
      in `evaluate-job.md`, that's a real finding — update that file's
      Workflow step 3 note with the new comparison, don't just note it here.

## 3. Voice consistency

- [ ] Does the summary/framing-angle language sound like it drew on
      `memory/voice_guide.md`, or does it read like generic corporate
      cover-letter filler regardless of what the voice guide says?

## 4. `bff gaps` plausibility

Run `bff gaps` (or `python3 src/best_foot_forward/utils/... `) against the
UAT `$BFF_DATA_DIR` after a full `run_uat.sh` pass.

- [ ] Do the surfaced gaps look like real gaps against Leia's actual skill
      set, or does the list look suspiciously thin/absent (the exact
      Bug-1 circular-vocabulary symptom: `reports/skills.py::vocabulary_health`
      should print a warning banner if this regresses, not a falsely
      reassuring "No significant gaps found").
