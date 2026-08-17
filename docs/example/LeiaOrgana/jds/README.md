# Leia Organa example job descriptions

Six job postings for the example/demo dataset — the jobs Leia Organa **applies to**.
Pair them with `../EngineerResume.txt` (her history), `../StarStory.md`, and `../voice.md`.

Each one is a **real job posting with the employer's identity replaced by a fictional
in-universe one.** The structure, tech stack, seniority bars, responsibilities, and
salary figures are left verbatim so that `/evaluate-job` scoring and `/resume-tailor`
exercise realistic matching rather than toy input. Everything that could identify the
actual company is gone.

Regenerate or re-check with [`scripts/anonymize_example_jds.py`](../../../../scripts/anonymize_example_jds.py):

```bash
python3 scripts/anonymize_example_jds.py --verify              # check what's committed
python3 scripts/anonymize_example_jds.py --src <real-postings> # rebuild from source
```

The real source postings are **deliberately not in this repo** and must stay out of it.

## The employers

| File | Employer | Role | Shape |
|---|---|---|---|
| `one.odt` | Chandrila Data Collective | Platform Engineering Manager | Remote; human-data infrastructure for AI |
| `two.odt` | Nar Shaddaa Exchange Group | Staff Platform Engineer, Nar Shaddaa Markets | Prediction markets / real-money trading |
| `three.odt` | Scarif Identity Systems | Senior / Staff SRE, Platform Engineering | Identity security SaaS, hybrid |
| `four.odt` | Obroa-skai Analytics | Staff Platform Engineer, Cloud Developer Experience | Market intelligence; CI/CD + DevEx |
| `five.odt` | Theed Agent Systems | Engineering Manager | AI voice agents, Series B–D, salaried range |
| `six.odt` | Kuat Design Systems | Director/VP of Software | Hardware/ECAD collaboration, Series A |

Deliberate spread: five individual-contributor platform roles plus one
manager/director-track posting (`six.odt`), so the corpus exercises more than one
tailoring angle. Names were chosen to match each real company's actual domain — Scarif
was the Imperial data vault, Obroa-skai is canonically the galaxy's information world,
Nar Shaddaa is the gambling moon, Kuat and Fondor are the shipbuilding worlds.

## Names that are already taken

These appear in Leia's own résumé and STAR story. **A new example employer must not
reuse them** — she worked *at* these; she is applying *to* the ones above:

> The Resistance · Ajan Kloss · Corellian Freight Analytics · Corellia · HoloNet Commerce
> Group · Coruscant · Alderaan Civic Systems · Alderaan · University of Alderaan ·
> Galactic Platform Engineering Summit · Young Engineers of the New Republic ·
> **Cloud City / Bespin** (her home address)

Avoid the `Holo-` prefix generally, so nothing reads as a sibling of HoloNet Commerce Group.
`Kuat Drive Yards` is intentionally still unused if another example job is ever needed.

## What gets stripped, and why it isn't obvious

Reading an `.odt` shows you almost none of what identifies it. The three leaks that
mattered here were all invisible on the page:

- **Linked logo images.** Three postings referenced a live
  `https://s*-recruiting.cdn.greenhouse.io/.../<Company>_Logo.png` — an external fetch on
  open, with the company name in the URL path *and* in an `<svg:title>` alt-text.
- **ATS location bookmarks.** `<text:bookmark text:name="secondary-additional-location-Milpitas,
  California"/>` stores real cities in an **attribute name**, which survives any amount of
  visible-text rewriting.
- **Page thumbnails.** `Thumbnails/thumbnail.png` is a rendered preview of page 1 and still
  showed the original company name.

Also removed: all hyperlink hrefs (ATS boards on both Greenhouse and Ashby, tracking
tokens, press coverage, LinkedIn, careers pages), investor and partner-brand names,
founder names, funding/revenue figures, and legal boilerplate (privacy notices, EEO,
recruiting-scam warnings, `#LI-` tags).

Kept on purpose: real tooling and OSS names that identify a *stack*, not an employer —
Kubernetes, Terraform, ArgoCD, Kafka, Istio, Go/Rust/Vue, Claude Code, Cursor, Copilot,
KiCad, LTSpice, and the one surviving link, `github.com/go-gitea/gitea` in `six.odt`.

`tests/test_example_jds_anonymized.py` enforces all of the above on every test run.
