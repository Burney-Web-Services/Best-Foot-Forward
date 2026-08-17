# interview-debrief

## Purpose
Capture what actually happened in an interview — what was asked, how it went, what you missed — and feed that learning back into the database. Produces a structured debrief that updates `applications.notes`, optionally surfaces new STAR stories, and stages the application correctly. This is the feedback loop that makes each subsequent prep round smarter.

## Input
The user provides a company name (e.g., `/interview-debrief Amazon`) and optionally the round (screen, interview_1, interview_2, etc.). If not specified, infer the round from `applications.stage`.

The user may also provide a transcript file path or mention that a transcript exists — use it if available. Otherwise, work from the conversation.

## Workflow

### Phase 1 — Orient

1. Look up the company in the `jds` table (case-insensitive, partial match OK). Retrieve `jd_id`, `file_path`, and `output_dir`. If multiple matches, list and ask.
2. Find the matching application via `jd_id`. Read: `stage`, `status`, `notes` (prior debrief notes if any), `applied_at`.
3. Read the most recent prep file for this round from the output directory:
   - For a screen: `{Company}ScreenPrep.docx` (or `.txt` equivalent)
   - For interview_1 or later: `{Company}InterviewPrep.docx` or `{Company}STARPrep.docx`
   - If the file is a `.docx`, read it directly — `python-docx` can extract text. If unreadable, note it and proceed without it.
4. Check for a transcript in the output directory: look for `.md` files matching `*transcript*` or `*_{date}*`. If found, read it. If multiple, list them and ask which to use (or use the most recent by filename timestamp).

### Phase 2 — Debrief conversation

Ask the following questions conversationally — one or two at a time, not as a batch form. Listen and follow up.

- "What questions came up that you weren't expecting?"
- "Where did you feel thin or under-prepared?"
- "What responses landed well — where did you feel the conversation click?"
- "Anything you wish you'd said, or a moment where you knew the answer but didn't get it out cleanly?"
- "What's your read on the interviewer — what seemed to matter most to them?"

If a transcript is available, do this *after* reading it — use the transcript to inform follow-up questions ("I see they spent a lot of time on X — how did that go?") rather than asking about things the transcript already answers.

### Phase 3 — Difference analysis

Compare what was prepped against what actually happened. Produce three sections:

**Questions asked vs. questions prepped**
- Questions that appeared in prep and came up: confirm they landed
- Questions in prep that didn't come up: note for possible next round
- Questions that came up that weren't in prep: flag for next round prep

**How your answers compared**
- Where the prepped response and the actual response were aligned: note as validated
- Where you went off-script (better or worse than prepped): note specifically
- Any area where you said something that contradicts what's on the resume: flag clearly

**Key takeaways for next round**
- 2–4 specific things to address if there's another conversation: gaps to close, stories to sharpen, framings to adjust
- If the round is a screen and there's a hiring manager interview ahead: what to emphasize
- If this was a final round: what the outcome signals regardless of result

### Phase 4 — Write to DB

Construct the debrief note. Format:

```
[Round: screen | interview_1 | interview_2 | ...] [Date: YYYY-MM-DD]

WHAT WAS ASKED: [3–8 bullet points — actual questions, paraphrased]
WHAT LANDED: [2–4 specific moments that went well]
GAPS EXPOSED: [2–4 specific areas that felt thin or were probed hard]
NEXT ROUND FOCUS: [2–4 items to address if there's another conversation]
TRANSCRIPT: [filename if available, else "no transcript"]
```

If `applications.notes` is already non-empty (prior round debrief exists), **append** this debrief below the existing content — separate with `\n\n---\n\n`. Do not overwrite prior notes.

Run via `db_query.py`:
```sql
UPDATE applications SET notes = '<debrief text>' WHERE jd_id = <jd_id>;
```

### Phase 5 — Stage and status update

Update `applications.stage` to reflect where things stand now:
- After a screen, if invited to next round: leave at `screen` (interview-prep will advance it)
- After interview_1 with next round scheduled: leave at `interview_1`
- After a final round: update `status` to `interviewing` (or `awaiting_decision` if that's defined)
- If explicitly rejected: update `status = 'rejected'` and `stage = 'rejected'`

Only update what you know for certain. If the outcome is unclear, leave status as-is and note it.

Log the debrief: `python3 -m best_foot_forward.utils.log_action --actor interview-debrief --action debrief --entity-type application --entity-id <application_id> --details '{"company": "<Company>", "round": "<round>", "stage": "<stage>", "status": "<status>"}'`

### Phase 6 — STAR story prompt (optional)

Scan the debrief for responses that sound like strong, specific stories — moments where the user described a concrete situation, action, and outcome.

If you find 1–3 candidates, list them briefly:
> "These responses sounded like strong stories worth capturing: [title 1], [title 2]. Want to add any of them to the STAR corpus now?"

If the user says yes for any, transition directly into the `star-story` workflow for each one. Pass the relevant context from the debrief so the interview doesn't start from scratch.

If no strong candidates, skip this step.

### Phase 7 — Report

Summarize what was written:
- Debrief saved to `applications.notes` (appended or created)
- Stage/status updates made (if any)
- STAR stories captured (if any)
- Key next-round focus items (repeat the 2–4 items from the debrief)

## Notes
- The debrief conversation should feel like a post-game with a coach — curious, specific, not judgmental. Push for concrete details, not "it went fine."
- If the user is talking about a rejection, adjust tone accordingly. Still extract the learning, but don't be clinical about it.
- Do not ask for confirmation before writing to the DB — write and report.
- If no prep doc and no transcript exist, work entirely from conversation. The debrief is still worth capturing.
- The `applications.notes` field is the institutional memory for this application — treat it as append-only. Never overwrite prior round notes.
