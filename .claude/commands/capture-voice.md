# capture-voice

## Purpose
Derive `memory/voice_guide.md` — a guide to how the seeker actually writes — from samples of their own writing, so cover letters (`resume-tailor`) and interview answers (`interview-prep`, `screening-prep`) sound like them instead of a template. Optional, non-blocking: those commands already tolerate `voice_guide.md` being absent, so this is a polish layer, not a prerequisite. Skipping it just means tone keeps getting inferred from accumulated `/star-story` `raw_transcript`s over time instead.

## Input
The user invokes `/capture-voice` any time after they have a profile started. They may also trigger this naturally by saying "capture my voice", "voice guide", "learn how I write", or "sound like me".

## Workflow

### 1. Frame it
> "I'll build a voice guide — how you naturally write — so cover letters and interview answers sound like you, not a template. Best input is 2-3 short samples of your own writing. Takes about 5 minutes, and it's optional — you can skip it and I'll infer tone from your STAR stories as you capture more of them."

### 2. Ask for samples
Offer a menu, since "writing sample" isn't obvious on its own:
- A past cover letter or application email
- A Slack or email message where you explained a decision or gave feedback
- A LinkedIn post, blog paragraph, README, or design-doc/RFC intro you wrote
- Notes or answers from a prior interview-prep session
- A captured STAR story's `raw_transcript` (if one exists — check `stories` table)

Guidance on quantity: 2 samples is the floor, 3-4 is the sweet spot, 5+ has diminishing returns. Variety of register (one formal, one casual) matters more than volume. If the user has nothing to paste, say so and move to step 2b.

### 2b. Freeform fallback (no samples available)
Ask these prompts one at a time — the answers themselves become the writing sample:
1. "Describe a project you're proud of, the way you'd tell a colleague over coffee."
2. "You disagree with a decision your team is about to make. Write the message you'd actually send."
3. "A teammate did great work. Write how you'd recognize it."
4. "Something you shipped broke or failed. How do you talk about that?"
5. "Any phrases or opinions you catch yourself repeating at work?"

### 3. Optional clarifying round
If everything gathered is one register (e.g. all formal), ask once for the missing register (a casual message, or an opinion). At most one round — don't over-interview for a polish layer.

### 4. Draft and review
Analyze the sample(s) — reasoning about tone directly, not running any external tool — and draft the guide in this shape:

```
# Voice Guide

_Derived <date> from N samples: <source types>._

## Communication Characteristics
- [traits actually evidenced by the samples — confident/tentative, collaborative/individual, plain/jargon-heavy, evidence-driven/assertive]

## Writing Tendencies
- [mechanics — active/passive voice, sentence length, buzzword use, hedging, structure]

## <Work Philosophy | Design Philosophy | Leadership Philosophy — pick the header that fits their domain>
- [stated beliefs/principles, only if the samples actually surfaced opinions — keep short or omit rather than invent]

## Communication Preferences
- **Disagreement:** [only if sampled]
- **Praise:** [only if sampled]
- **Discussing failure:** [only if sampled]

## Representative Expressions
- [verbatim phrases lifted from the samples, lightly cleaned — never invented]

## Voice Guidance
- [meta-instructions for a future drafting agent — concrete imperatives, e.g. "favor clarity over cleverness," "confidence from evidence, not assertion"]
- This is evidence of how they write, not text to quote. Newer accumulated writing (more STAR stories, more tailored letters) is stronger evidence than this seed — a future re-run should supersede it, not just append.
```

Every line must trace back to something in the samples. Thin signal produces a shorter, more hedged guide — not padding. Show the full draft and ask: "Does this sound like you? Anything overstated, missing, or wrong?" Iterate until approved — same review-before-write pattern as `/onboard`'s Phase 3.

### 5. Write and confirm
Write the approved draft to `memory/voice_guide.md`. Do not persist the raw pasted samples anywhere — only the derived guide.

Log the capture: `python3 -m best_foot_forward.utils.log_action --actor capture-voice --action write --entity-type memory-file --entity-id voice_guide --details '{"sample_count": <N>}'`

Report: confirm the file was written, note the section count, suggest `/resume-tailor` as a natural next step.

## Notes
- Don't fabricate. If a section has no evidence (e.g. no failure-discussion sample was offered), omit it or say so rather than inventing a plausible-sounding entry.
- Representative Expressions is the highest-risk section for hallucination — verbatim-or-omit, never a paraphrase presented as a quote.
- If `memory/voice_guide.md` already exists, this is a refresh: show the existing guide, ask what's changed or feels stale, and only overwrite after the same review gate.
- Never read or copy an existing hand-written example voice guide (e.g. anything under `docs/example/`) as a shortcut — the guide must be derived from this conversation's actual samples every time, real user or otherwise.
