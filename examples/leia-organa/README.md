# Leia Organa — example dataset

Fictional persona, real workflows. This is what `load_example_data.py` loads for
`/onboard`'s "explore" path, so a new open-source user's first run has something real
to look at instead of an empty database.

## Provenance

Everything here is **replayed from actual Claude Code sessions**, not hand-invented.
Paul roleplayed as Leia Organa — and later had Claude drive both sides — running her
through BFF's real commands (`/onboard`, `/capture-voice`, `/evaluate-job`,
`/star-story`, `/resume-tailor`, `/screening-prep`) against her own real database, on
real (anonymized) job postings. The scores, gaps, declines, and outcomes below are what
those runs actually produced.

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

## Known limitations

`load_example_data.py` replays most of what actually happened (declined leads, pipeline
stage, scheduled interviews) but doesn't yet carry screening-prep docs — the real
`ScreenPrep.docx`/`.txt` and its `prep_data.py` exist in the source session but aren't
part of the loader's fixture contract. Would need a `prep/` slot added, similar to how
`applications/` works today.
