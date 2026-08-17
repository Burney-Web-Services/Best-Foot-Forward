# Leia Organa — example dataset

Fictional persona, real workflows. This is what `load_example_data.py` loads for
`/onboard`'s "explore" path, so a new open-source user's first run has something real
to look at instead of an empty database.

## Provenance

Everything here is **replayed from actual Claude Code sessions**, not hand-invented.

**Phase 1 (2026-08-14, Paul roleplaying as Leia):** Paul roleplayed as Leia Organa in
an isolated sandbox clone (`BestFootForward-Leia-Sandbox`, `origin` deliberately unset
— see `BFF-2026-0723-LeiaExampleDataset`) and ran her through BFF's real commands
against her real database:
1. `/onboard` — Type 2 (Resume Freshening) intake from
   [`../../docs/example/LeiaOrgana/EngineerResume.txt`](../../docs/example/LeiaOrgana/EngineerResume.txt),
   producing `intake_data.py` verbatim (this directory's copy is the literal file
   `/onboard` wrote, byte for byte).
2. `/capture-voice` — drafted `voice_guide.md` from three real writing samples
   (a template cover letter, her own words during intake, a reconstructed
   peer-recognition note).
3. `/evaluate-job`, run four times against real job postings.

**Phase 2 (2026-08-15, Claude driving both sides):** Paul had been manually
orchestrating two Claude Code sessions to continue the roleplay — one running BFF's
real commands, one generating Leia's in-character answers, copying between them by
hand. He asked Claude to do both roles directly instead. This session:
- Scored the two postings the original roleplay never got to (Kuat Design Systems,
  Theed Agent Systems) — see below.
- Spawned a persistent **Leia Organa persona subagent** (`claude-fable-5`, grounded in
  `voice_guide.md`, the full resume, and her metric-provenance/attribution-discipline
  rules) as the actual conversational partner for the interactive workflows, in place
  of a second human-run session.
- Ran the real `/star-story` interview against that persona — full S/T/A/R, follow-up
  questions on room size and pushback, genuine hedging on old numbers — producing
  `stories.json`.
- Ran `/resume-tailor` against Obroa-skai Analytics and Scarif Identity Systems, each
  with real clarifying-question exchanges with the persona before drafting (see each
  `TAILORING_NOTES` for what she said about her own gaps).
- Ran `/resume-tailor`'s clarifying questions against Nar Shaddaa Exchange Group too —
  and the persona said no. Real-money betting isn't an industry she wants her name
  next to; a values call, not a skills one. That became a `triage_lead` decline
  (`domain`, reason in her own words) instead of a third tailored application — a more
  useful fixture outcome than three uniform successes, and the honest one given what
  she actually said.
- Advanced Obroa-skai to "traction": `/screening-prep` moved its `applications.stage`
  to `screen` and added a scheduled-call `contacts` row, then generated the real prep
  doc (tell-me-about-yourself, likely questions with her actual answers, questions to
  ask).

**Phase 3 (2026-08-16, folded in from the UAT harness):** `tests/uat/`'s Tier 1 harness
(`BFF-2026-0815-UatHarnessAndDataLeak`) already drove a real `/evaluate-job` call against
a purpose-built posting (Coruscant Systems Group — a GCP/ArgoCD/Prometheus·Grafana/
Snowflake stack the persona genuinely doesn't have) every time it ran, but that posting
never made it into the persistent fixture — a fresh `/onboard` explore run never saw it.
Folded it in as the fixture's 7th posting, scored by Claude directly (same standard as
Kuat/Theed below, not a live subagent call) against the real `intake_data.py` profile.
`tests/uat/fixtures/gap_posting.txt` and this posting's `JobDesc.md` share the identical
posting body by construction — see `tests/uat/README.md` for how the two now double as
each other's regression coverage.

## The seven postings

[`../../docs/example/LeiaOrgana/jds/`](../../docs/example/LeiaOrgana/jds/) holds the six
real job postings from Phase 1/2 with the employer's identity replaced by a fictional one
(see that directory's own README and `scripts/anonymize_example_jds.py` for how); the 7th
(Coruscant Systems Group) is purpose-built rather than anonymized from a real posting, so
it lives only under `applications/`, not in that directory. `applications/` pairs each
with the actual `/evaluate-job` output — and, for three of them, the downstream outcome:

| Company | Role | Score | Outcome |
|---|---|---|---|
| Obroa-skai Analytics | Staff Platform Engineer, Cloud DX | 82 | tailored, applied, **screen scheduled 2026-08-21** |
| Scarif Identity Systems | Senior/Staff SRE, Platform Engineering | 81 | tailored, applied |
| Nar Shaddaa Exchange Group | Staff Platform Engineer, Nar Shaddaa Markets | 76 | **declined** — domain (gambling), her own words |
| Kuat Design Systems | Director/VP of Software | 65 | scored for this fixture, pending |
| Coruscant Systems Group | Staff Platform Engineer, Observability & Data Cloud | 62 | scored for this fixture, pending — also `tests/uat/`'s live regression target |
| Chandrila Data Collective | Platform Engineering Manager | 59 | pending |
| Theed Agent Systems | Engineering Manager, Observe/Eval | 58 | scored for this fixture, pending |

Four of the seven (Obroa-skai, Scarif, Nar Shaddaa, Chandrila) carry the actual scores,
summaries, and `jd_required_skills` rows the original roleplay session produced.
Kuat, Theed, and Coruscant weren't in that session — scored afterward by Claude, same
rubric, against the same real `intake_data.py` profile: full bullet-by-bullet evidence
check, gaps stated plainly with no compensating clause. Not a live subagent call for
these three, but held to the same standard — see each `jd_eval.json`'s `summary`.
Coruscant's score is the one exception worth flagging: a live `tests/uat/run_uat.sh` pass
overwrites it with a fresh `/evaluate-job` result, by design — the seeded 62 is only the
value a plain `/onboard` explore run (no live UAT pass) will see.

Deliberate spread across all seven: five individual-contributor/manager platform roles
plus two executive-leaning ones, so the corpus exercises more than one tailoring angle,
score band (58–82), and outcome (tailored-and-applied, tailored-and-scheduled,
declined, and still-pending).

## Fixture contract

Matches `load_example_data.py`'s documented shape:

```
leia-organa/
  README.md              — this file
  intake_data.py          — CONTACT, EDUCATION, EMPLOYERS, BULLETS, SKILLS
  user_profile.md         — drafted by /onboard Phase 7 from the intake above
  voice_guide.md          — drafted by /capture-voice
  stories.json             — one real /star-story capture (Corellian reliability story)
  applications/
    <Company>/<Role_Slug>/
      JobDesc.md           — property block + the anonymized posting text
      jd_eval.json          — {score, summary, url, salary_min/max/currency, required_skills}
      resume_data.py        — present only for Obroa-skai and Scarif (the two tailored)
      letter_data.py        — same
```

No `document_prefs.json` — never set during either session.

## Known gaps between this fixture and what actually happened

`load_example_data.py` (merged via `BFF-2026-0814-OnboardingEvalFixes`, extended
2026-08-16) still can't carry everything this fixture represents:

- ~~Declined leads~~ — **fixed 2026-08-16.** `_load_not_yet_loadable_lead_state()`
  now replays `jd_eval.json`'s `_not_yet_loadable.lead_status` through
  `triage_lead.set_lead_status()`, the same documented write path a real decline
  goes through. Nar Shaddaa loads as `lead_status='declined'`, `decline_category='domain'`,
  her actual `decline_reason`, and the real `lead_decided_at` (2026-08-14).
- ~~Pipeline stage and scheduled interviews~~ — **fixed 2026-08-16.** Obroa-skai's
  `applications.stage` now lands as `'screen'` (not the default `'application'`), and
  its real screening contact (Toman Feyn, 2026-08-21 10:00 AM PT) is seeded into
  `contacts`. Both replays are idempotent — re-running the loader with `--force`
  doesn't duplicate the contact row or reset the decision date.
  Regression tests: `tests/test_load_example_data.py::test_not_yet_loadable_lead_state_replays`,
  `::test_not_yet_loadable_replay_is_idempotent_on_force_reload`.
- **Screening prep docs.** Still not part of the fixture contract — the real
  `ScreenPrep.docx`/`.txt` and its `prep_data.py` exist in the sandbox session but
  aren't replayable through the loader. Would need a `prep/` slot added to the
  contract, similar to how `applications/` works today.
- **Three loader bugs found while building and loading this fixture — fixed 2026-08-15**
  (`load_example_data.py`, same day as the DB migration/reindex pass for
  BFF-2026-0814-OnboardingEvalFixes):
  - **Duplicate `jds` rows for every tailored application** — the serious one.
    `_load_application()` used to build `asset_dir`/`jd_dest` from the raw, underscored
    `company` directory-name string, but insert the DB row with
    `company.replace("_", " ")`. That was fine in isolation — but when the fixture also
    has `resume_data.py` (i.e. a tailored application), `_load_application` copies it
    into `data/session/` and shells out to `generate_resume.py`, which reads
    `JD_FILE_PATH` back out of that file — the *space*-formatted path the fixture author
    wrote, following the documented convention everywhere else in the codebase
    (`resolve_or_create_jd` etc. all expect spaces). Since that didn't string-match the
    underscored path `_load_application` had already inserted, a second orphaned `jds`
    row got created. Reproduced exactly by loading this fixture: `Obroa-skai Analytics`
    landed as jds 4 *and* 5, `Scarif Identity Systems` as jds 6 *and* 7 — the tailored
    resume/letter and the real score ended up on different rows. This was the same
    duplicate-row failure class `CLAUDE.md`'s JD-file-conventions section already
    documents recurring three times elsewhere — a fourth instance, inside the loader
    itself, only surfacing once a fixture includes real tailored content.
    **Fixed** by reading the real `company`/`role` back from `JobDesc.md`'s own
    `company::`/`role::` property-block lines (see next bug) and reusing
    `save_lead_jd.jd_paths()` for `asset_dir`/`jd_dest` instead of hand-rolling a second,
    divergent copy of that path logic — the two now structurally cannot disagree.
    Verified against this exact fixture: all 6 companies now land as exactly 6 `jds` rows.
  - `_load_application()` used to derive each JD's `role` from the slugified directory
    name rather than reading it back from `JobDesc.md`'s `role::` line, losing
    punctuation ("Director/VP of Software" → "Director VP of Software" in the DB).
    **Fixed** — role (and company) are now read straight from the property block;
    verified `jds.role` for Kuat Design Systems is `Director/VP of Software` intact.
  - It used to re-pass an already-header-prefixed `JobDesc.md` through
    `save_lead_jd.py --text-file`, which writes its own property-block header —
    doubling it. **Fixed** — the posting body is now stripped of its existing header
    before being re-passed via `--text`; verified the written file has exactly one
    `type::`/`company::`/`role::` block.
  - Regression test: `tests/test_load_example_data.py::test_tailored_application_with_spaced_punctuated_name_loads_once`.

None of these block using the fixture — `/onboard`'s explore path already loaded a
real, populated example even before the fix. They're just where the fixture's real
richness (the decline, the traction, the prep doc) currently exceeds what the loader
replays.
