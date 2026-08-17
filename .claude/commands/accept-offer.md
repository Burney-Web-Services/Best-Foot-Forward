# accept-offer

## Purpose
Record an accepted job offer — the single event this whole system exists to produce, and the one BFF has never been able to represent. Writes the offer terms, concludes the application, and closes out the rest of the pipeline in a way that scales to however many open applications and leads exist, without turning into a per-item interrogation.

## Input
The user provides a company name (e.g., `/accept-offer Kuat Design Systems`). The user may also trigger this naturally by saying "I accepted the offer from X", "I'm taking the job at X", "accepted X's offer", or "I got the job at X" (see `CLAUDE.md` → Natural language routing).

## Workflow

### Phase 1 — Orient
Resolve the company in `jds` (case-insensitive, partial match OK — use `canonical_company()` from `best_foot_forward.utils.company_normalize`). Find the application via `jd_id`. Read `stage`, `status`, `applied_at`, `notes`, and the JD's `salary_min`/`salary_max`/`salary_currency`. If multiple applications match, list them and ask. If there's no application row at all, stop and say so plainly — an offer with no application is a data problem to fix first, not something to paper over.

### Phase 2 — Congratulate, then capture terms
Open with an actual congratulations — this is the good outcome. Then ask for the offer terms in two batches, not eight separate questions:

> "Congratulations — that's the whole point of this thing. Let me get the terms down.
> **First: the money.** Base salary, and total first-year comp if there's a bonus or equity on top?"

Then:

> "**And the practicalities:** what's the title as offered, when's your start date, and was there a deadline to respond by?"

Then one open catch-all:

> "Anything else in the package worth recording — sign-on, equity vesting, PTO, remote terms, level?"

Rules:
- Every field is nullable. Accept partial answers and never re-ask for something the user declined to give.
- If the user already stated terms conversationally before the command fired (e.g. "I accepted Kuat's offer, $100K base"), echo them back for confirmation instead of asking again.
- If the offered salary is below the JD's `salary_target` or `salary_min`, note it in one neutral line — worth having in the record for a future benchmark lookback, but this is not the day to editorialize about it.
- If the acceptance happened in the past (the common case — this command usually runs after the fact), ask when it was actually decided so `--decided-at` reflects the real date, not today.

### Phase 3 — Write the offer
Before any cleanup below, so an interrupted session still leaves the offer recorded:
```
python3 -m best_foot_forward.utils.record_offer --application-id <id> --state accepted \
    --salary <n> [--total-comp <n>] --currency <ccy> --title '<title>' \
    --start-date <iso> [--deadline <iso>] [--received-at <iso>] --decided-at <iso> [--notes '<...>']
```
Report the one-line result it prints.

### Phase 4 — Close out the rest
**Exactly three questions, regardless of how large the pipeline is.** Do not loop per application — with dozens or hundreds of open items, that's not a conversation, it's a chore.

Run one read-only query to split the still-open applications (`concluded_at IS NULL`, excluding the one just accepted) into two buckets:

```sql
-- Bucket A: LIVE — worth a real note, since they spent real time on the candidate
SELECT a.id, j.company, j.role, a.stage, date(a.applied_at) AS applied
FROM applications a JOIN jds j ON a.jd_id = j.id
WHERE a.concluded_at IS NULL AND a.id != <accepted_id>
  AND ( a.stage IN ('screen','phone_screen','interview_1','interview_2','interview_3','onsite','final','assessment_submitted','offer_received')
     OR date(a.applied_at) > date('now','-30 day')
     OR a.follow_up_date IS NOT NULL
     OR EXISTS (SELECT 1 FROM contacts c WHERE c.jd_id = j.id AND c.interview_date >= date('now')) )
ORDER BY a.applied_at DESC
```
Everything else still open is Bucket B.

**Question 1 — Bucket A, itemized:**
> "N of these had real momentum. Worth an actual note to each — they spent time on you:
> 1. Company — Role (applied Jul 16)
> 2. Company — Role (applied Jul 28)
> Withdraw from all / none / pick numbers?"

Accept `all`, `none`, or a comma list. Then:
```
python3 -m best_foot_forward.utils.record_offer --close-ids <picked ids> --close-status withdrawn --close-reason '<one line>'
```
Offer once, without looping: *"Want me to draft withdrawal notes for those? `/write-thank-you` handles the tone."*

**Question 2 — Bucket B, count only, never the full list:**
> "The other N never came back — Company, Company, Company and M more. Close them as not_pursued? (Nothing gets sent; this just stops them showing up as open.)"

Show three sample companies and a count. One call:
```
python3 -m best_foot_forward.utils.record_offer --close-ids <all Bucket B ids> --close-status not_pursued
```
`not_pursued`, not `withdrawn` — nothing was ever told to these companies, so `withdrawn` would misrepresent what happened.

**Question 3 — open leads, count only:**
> "You've also got N evaluated leads you never applied to. Mark them declined?"

Reuse the existing lead write path per lead — `record_offer` never touches `jds`:
```
python3 -m best_foot_forward.utils.triage_lead --jd-id <id> --status declined --category strategy --reason 'Accepted an offer elsewhere'
```
`strategy` ("the posting was fine; you're focusing elsewhere") is the exact fit here, not `other`.

Defaults if the user just says "yes, close everything": Bucket A → withdrawn, Bucket B → not_pursued, leads → declined/strategy. If they say "leave it" — skip all three; the offer is already recorded, which is the part that matters.

### Phase 5 — Log
```
python3 -m best_foot_forward.utils.log_action --actor accept-offer --action accept \
    --entity-type application --entity-id <id> \
    --details '{"company":"<C>","role":"<R>","salary":<n>,"start_date":"<iso>","withdrawn":<n>,"not_pursued":<n>,"leads_declined":<n>}'
```
(`record_offer` and `triage_lead` also log their own events — this is the workflow-level summary line, matching how `interview-debrief` and `evaluate-job` both log despite their utils doing so too.)

### Phase 6 — Post-offer hooks
Scan and run every `.md` hook file found, in order: `.claude/hooks/on_offer/*.md`, then `.claude/hooks/on_offer/local/*.md`, then `data/hooks/on_offer/*.md`. See "Post-offer hooks" in `CLAUDE.md`.

### Phase 7 — Report
One closing block — real numbers pulled from the DB, shaped like this:

> **{Company} — {Role}. Accepted.**
> Applied {applied date} → accepted {accepted date} — **{N} days**, {N} stages.
> Offered {currency} {base salary} (posted range {low}–{high}, if known).
> Starts {start date}.
> Closed out: {N} withdrawn, {N} not pursued, {N} leads declined.
> {N} applications, {N} passes, 1 offer. That's the search.

## Notes
- Do not fabricate offer terms. Only record what the user actually states.
- The withdraw/not-pursue sweep is real, irreplaceable data — never guess at which bucket an application belongs in beyond the query above; when in doubt about whether something had "real momentum," ask rather than assume.
- If the user wants to record an offer that arrived but hasn't been decided yet, that's `record_offer --state received`, not this command — see the natural-language routing entry in `CLAUDE.md`. This command is specifically for acceptance.
- Turning an offer *down* is the mirror case and deliberately has no command file — see the "declined" routing entry in `CLAUDE.md`, which is a single `record_offer --state declined` call with no fan-out (the rest of the pipeline stays open).
