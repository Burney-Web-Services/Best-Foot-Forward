import json
from datetime import date, timedelta

from best_foot_forward.utils.triage_lead import DECLINE_CATEGORIES


def hr(char="─", width=72):
    print(char * width)


def lead_urls(row) -> list[str]:
    """Every posting link known for a lead, best source first.

    `file_registry.source_urls` can hold several and is preferred, but it only
    exists once a JD *file* has been registered — which happens during tailoring.
    A lead you evaluated and passed on never gets a file, so for the whole declined
    pile that join is empty while `jds.url` has held the link all along. Falling
    back to it is the difference between the declined report showing every posting
    and showing none.
    """
    raw = row.get("source_urls")
    if raw:
        try:
            urls = json.loads(raw)
            if urls:
                return list(urls)
        except (ValueError, TypeError):
            pass
    return [row["url"]] if row.get("url") else []


def fmt_salary(sal_min, sal_max) -> str:
    if sal_min and sal_max:
        return f"${sal_min//1000}K–${sal_max//1000}K"
    if sal_min:
        return f"${sal_min//1000}K+"
    return "—"


def _activity_label(status, stage):
    stage = stage or ""
    if status == "rejected":
        return "Declined"
    if status == "accepted":
        return "ACCEPTED"
    if status == "offer_declined":
        return "Turned down"
    if status == "offer":
        return "Offer"
    if stage.startswith("interview"):
        return "Interviewed"
    if stage in ("screen", "phone_screen"):
        return "Screened"
    return "Applied"


def view_weekly(conn, days=7):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    today = date.today().isoformat()

    rows = conn.execute("""
        SELECT j.company, j.role, a.status, a.stage,
               date(a.applied_at)   AS applied_at,
               date(a.concluded_at) AS concluded_at
        FROM applications a
        JOIN jds j ON a.jd_id = j.id
        WHERE date(a.applied_at) >= ?
           OR (a.concluded_at IS NOT NULL AND date(a.concluded_at) >= ?)
        ORDER BY COALESCE(date(a.concluded_at), date(a.applied_at)) DESC, j.company
    """, (cutoff, cutoff)).fetchall()

    print(f"\n{'WEEKLY ACTIVITY REPORT':^72}")
    print(f"{'Last ' + str(days) + ' days  (' + cutoff + ' – ' + today + ')':^72}")
    hr()
    print(f"  {'Company':<22} {'Position':<35} {'Activity':<12} {'Date'}")
    hr("-")

    if not rows:
        print(f"  No activity in the past {days} days.")
        return

    for r in rows:
        r = dict(r)
        activity = _activity_label(r["status"], r["stage"])
        date_val = (r["concluded_at"] if r["status"] in
                   ("rejected", "offer", "accepted", "offer_declined") else r["applied_at"]) or "?"
        print(f"  {r['company'][:20]:<22} {r['role'][:33]:<35} {activity:<12} {date_val}")

    print(f"\n  {len(rows)} application(s) with activity in the past {days} days.")


def view_passes(conn):
    print(f"\n{'PASS / DECLINE ANALYSIS':^72}")
    hr()

    rows = conn.execute("""
        SELECT
            j.company,
            j.role,
            a.applied_at,
            a.concluded_at,
            a.stage,
            CASE
                WHEN a.applied_at IS NULL OR a.concluded_at IS NULL THEN NULL
                ELSE CAST(julianday(date(a.concluded_at)) - julianday(date(a.applied_at)) AS INTEGER)
            END AS days_to_pass
        FROM applications a
        JOIN jds j ON a.jd_id = j.id
        WHERE a.status = 'rejected'
        ORDER BY a.concluded_at DESC NULLS LAST
    """).fetchall()

    print(f"  {'Company':<22} {'Role':<42} {'Applied':<12} {'Passed':<12} {'Stage':<12} {'Days'}")
    print("  " + "-" * 108)

    for r in rows:
        r = dict(r)
        applied   = (r["applied_at"]   or "?")[:10]
        concluded = (r["concluded_at"] or "?")[:10]
        stage     = r["stage"] or "—"
        days      = str(r["days_to_pass"]) if r["days_to_pass"] is not None else "?"
        print(f"  {r['company']:<22} {r['role'][:40]:<42} {applied:<12} {concluded:<12} {stage:<12} {days}")

    total     = len(rows)
    with_days = [dict(r)["days_to_pass"] for r in rows if dict(r)["days_to_pass"] is not None]
    if with_days:
        avg = sum(with_days) / len(with_days)
        print(f"\n  Total: {total}  |  With known dates: {len(with_days)}  |  Avg days to pass: {avg:.1f}")
    else:
        print(f"\n  Total passes: {total}")


def view_matches(conn):
    print(f"\n{'JD MATCH SCORES':^80}")
    hr(width=80)

    rows = conn.execute("""
        SELECT j.company, j.role, j.score, j.evaluated_at,
               a.status, a.stage, a.applied_at
        FROM jds j
        LEFT JOIN applications a ON a.jd_id = j.id
        WHERE j.score IS NOT NULL
        ORDER BY j.score DESC
    """).fetchall()

    if not rows:
        print("  No scored JDs found. Run /evaluate-job to score a JD.")
        return

    STATUS_LABELS = {
        "applied":        "Applied",
        "interviewing":   "Interviewing",
        "rejected":       "Declined",
        "offer":          "Offer",
        "accepted":       "Accepted",
        "offer_declined": "Turned down",
    }

    print(f"  {'Score':<7} {'Company':<22} {'Role':<36} {'Status':<14} {'Applied'}")
    print("  " + "─" * 76)

    for r in rows:
        r = dict(r)
        score   = str(r["score"])
        status  = STATUS_LABELS.get(r["status"], "Not Applied")
        applied = (r["applied_at"] or "")[:10] or "—"
        print(f"  {score:<7} {r['company'][:20]:<22} {r['role'][:34]:<36} {status:<14} {applied}")

    applied_count      = sum(1 for r in rows if dict(r)["status"] == "applied")
    interviewing_count = sum(1 for r in rows if dict(r)["status"] == "interviewing")
    declined_count     = sum(1 for r in rows if dict(r)["status"] == "rejected")
    not_applied_count  = sum(1 for r in rows if dict(r)["status"] is None)
    avg_score          = sum(dict(r)["score"] for r in rows) / len(rows)

    print(f"\n  {len(rows)} scored JD(s)  |  Avg score: {avg_score:.0f}  |  "
          f"Applied: {applied_count}  Interviewing: {interviewing_count}  "
          f"Declined: {declined_count}  Not Applied: {not_applied_count}")


def view_leads(conn):
    print(f"\n{'PENDING LEADS':^72}")
    hr()

    rows = conn.execute("""
        SELECT j.company, j.role, j.score, j.evaluated_at,
               j.salary_min, j.salary_max, j.salary_currency, j.source,
               j.url, fr.source_urls
        FROM jds j
        LEFT JOIN file_registry fr ON fr.jd_id = j.id AND fr.file_type = 'jd'
        WHERE j.lead_status = 'pending'
        ORDER BY j.score DESC NULLS LAST, j.evaluated_at DESC
    """).fetchall()

    if not rows:
        print("  No pending leads. Pending leads are freshly-evaluated JDs awaiting a keep/decline decision —")
        print("  from your own evaluate-job runs, or pushed by a secondary sourcer via the sync_leads MCP tool (/push-leads).")
        return

    print(f"  {'Score':<7} {'Company':<22} {'Role':<36} {'Salary':<18} {'Evaluated'}")
    print("  " + "─" * 80)

    for r in rows:
        r = dict(r)
        score  = str(r["score"]) if r["score"] is not None else "—"
        salary = fmt_salary(r["salary_min"], r["salary_max"])
        eval_date = (r["evaluated_at"] or "")[:10] or "—"
        print(f"  {score:<7} {r['company'][:20]:<22} {r['role'][:34]:<36} {salary:<18} {eval_date}")
        for url in lead_urls(r):
            print(f"  {'':7}   {url}")

    # Route triage through triage_lead rather than a raw UPDATE: the decision
    # writes lead_status, lead_decided_at and decline_reason together.
    print(f"\n  {len(rows)} pending lead(s). To triage one:")
    print("    python3 -m best_foot_forward.utils.triage_lead --company '<Company>' --status approved")
    print("    python3 -m best_foot_forward.utils.triage_lead --company '<Company>' --status declined \\")
    print("        --reason '<why you passed, in your words>'")


def view_declined(conn):
    print(f"\n{'DECLINED LEADS':^72}")
    hr()

    # COALESCE: leads triaged before lead_decided_at existed fall back to their
    # eval date, the proxy this column replaced.
    rows = conn.execute("""
        SELECT j.company, j.role, j.score, j.evaluated_at,
               COALESCE(j.lead_decided_at, j.evaluated_at) AS decided_at,
               j.salary_min, j.salary_max, j.salary_currency, j.source,
               j.summary, j.decline_reason, j.decline_category,
               j.url, fr.source_urls
        FROM jds j
        LEFT JOIN file_registry fr ON fr.jd_id = j.id AND fr.file_type = 'jd'
        WHERE j.lead_status = 'declined'
        ORDER BY j.score DESC NULLS LAST, decided_at DESC
    """).fetchall()

    if not rows:
        print("  No declined leads. Declined leads are JDs you evaluated and passed on")
        print("  (lead_status='declined'); they're kept with their score and fit analysis,")
        print("  distinct from applications a company rejected (see Pass/Decline Analysis).")
        return

    print(f"  {'Score':<7} {'Company':<22} {'Role':<36} {'Salary':<18} {'Declined'}")
    print("  " + "─" * 80)

    uncategorized = 0
    for r in rows:
        r = dict(r)
        score  = str(r["score"]) if r["score"] is not None else "—"
        salary = fmt_salary(r["salary_min"], r["salary_max"])
        dec_date = (r["decided_at"] or "")[:10] or "—"
        print(f"  {score:<7} {r['company'][:20]:<22} {r['role'][:34]:<36} {salary:<18} {dec_date}")
        # Three voices, labelled so they don't read as one note: `why` is the
        # groupable category, `reason` is why *you* passed in your own words, and
        # `fit` is what evaluate-job scored.
        if r.get("decline_category"):
            gloss = DECLINE_CATEGORIES.get(r["decline_category"], "")
            print(f"  {'':7}   why:    {r['decline_category']} — {gloss}")
        else:
            uncategorized += 1
        if r.get("decline_reason"):
            print(f"  {'':7}   reason: {r['decline_reason'][:88]}")
        if r.get("summary"):
            print(f"  {'':7}   fit:    {r['summary'][:88]}")
        for url in lead_urls(r):
            print(f"  {'':7}   {url}")

    print(f"\n  {len(rows)} declined lead(s). To reconsider one:")
    print("    python3 -m best_foot_forward.utils.triage_lead --company '<Company>' --status approved")
    if uncategorized:
        print(f"\n  {uncategorized} have no category, so they sit out of the Decline Patterns")
        print("  report. Add one without restamping the decision date:")
        print("    python3 -m best_foot_forward.utils.triage_lead --jd-id <id> --status declined \\")
        print("        --category <slug> --decided-at '<existing lead_decided_at>' --reason '<existing reason>'")


# Bands are coarse on purpose: with a few dozen leads, finer buckets produce noise
# rather than signal. Ordered high-to-low for display.
SCORE_BANDS = [("80+", 80, 101), ("70–79", 70, 80), ("60–69", 60, 70), ("<60", 0, 60)]


def _band(score):
    if score is None:
        return None
    for label, lo, hi in SCORE_BANDS:
        if lo <= score < hi:
            return label
    return None


def _midpoint(sal_min, sal_max):
    """One comparable number per lead. Midpoint when a range is posted, otherwise
    the single end that is known — better than dropping the lead from the average."""
    if sal_min and sal_max:
        return (sal_min + sal_max) // 2
    return sal_min or sal_max or None


def decline_patterns(conn) -> dict:
    """Aggregate the declined pile. Split out from the printing so it can be tested
    and reused (the Logseq board renders the same tallies)."""
    rows = [dict(r) for r in conn.execute("""
        SELECT j.id, j.company, j.role, j.score, j.decline_category,
               j.salary_min, j.salary_max
        FROM jds j
        WHERE j.lead_status = 'declined'
    """).fetchall()]

    by_category = {}
    for r in rows:
        slot = by_category.setdefault(r["decline_category"], {"count": 0, "scores": [], "salaries": []})
        slot["count"] += 1
        if r["score"] is not None:
            slot["scores"].append(r["score"])
        pay = _midpoint(r["salary_min"], r["salary_max"])
        if pay:
            slot["salaries"].append(pay)

    by_company = {}
    for r in rows:
        by_company[r["company"]] = by_company.get(r["company"], 0) + 1

    # Applied-per-band comes from whether an application exists, not from
    # lead_status: a lead can sit at 'approved' while its application row is real
    # (that is exactly the tvScientific case), and the point of this split is
    # "what did I actually pursue".
    applied_bands = {}
    for r in conn.execute("""
        SELECT j.score FROM jds j
        WHERE EXISTS (SELECT 1 FROM applications a WHERE a.jd_id = j.id)
    """):
        b = _band(r["score"])
        if b:
            applied_bands[b] = applied_bands.get(b, 0) + 1

    declined_bands = {}
    for r in rows:
        b = _band(r["score"])
        if b:
            declined_bands[b] = declined_bands.get(b, 0) + 1

    # 'strategy' declines say nothing about the roles on offer — the posting was
    # fine and the seeker spent the effort elsewhere. Counting them as market
    # signal would overstate how many jobs are a poor fit. Uncategorized declines
    # are unknown, not signal, so they are excluded from the numerator too.
    signal = sum(v["count"] for k, v in by_category.items()
                 if k is not None and k != "strategy")

    return {
        "rows": rows,
        "total": len(rows),
        "by_category": by_category,
        "by_company": by_company,
        "declined_bands": declined_bands,
        "applied_bands": applied_bands,
        "signal": signal,
        "strategy": by_category.get("strategy", {}).get("count", 0),
        "uncategorized": by_category.get(None, {}).get("count", 0),
    }


def view_decline_patterns(conn):
    print(f"\n{'DECLINE PATTERNS':^72}")
    hr()
    # Easy to confuse with "Pass/Decline Analysis", which is the mirror image.
    print("  What YOU passed on, and why. (Jobs that passed on you: see Pass/Decline Analysis.)")

    d = decline_patterns(conn)
    if not d["total"]:
        print("\n  No declined leads yet.")
        return

    print(f"\n  BY REASON  ({d['total']} declined)")
    print(f"  {'':2}{'Category':<11} {'n':>3}  {'avg score':>9}  {'avg salary':>10}   what it means")
    print("  " + "─" * 92)
    ordered = sorted(d["by_category"].items(),
                     key=lambda kv: (-kv[1]["count"], kv[0] or "zz"))
    for slug, s in ordered:
        label = slug or "(none)"
        gloss = DECLINE_CATEGORIES.get(slug, "not yet categorized") if slug else "not yet categorized"
        avg_s = f"{sum(s['scores'])/len(s['scores']):.0f}" if s["scores"] else "—"
        avg_p = f"${sum(s['salaries'])//len(s['salaries'])//1000}K" if s["salaries"] else "—"
        print(f"  {'':2}{label:<11} {s['count']:>3}  {avg_s:>9}  {avg_p:>10}   {gloss}")

    print(f"\n  SIGNAL vs CHOICE")
    known = d["total"] - d["uncategorized"]
    if known:
        print(f"    {d['signal']} of {d['total']} declines say something about the roles you're seeing.")
    if d["strategy"]:
        print(f"    {d['strategy']} were pipeline choices — nothing wrong with the posting.")
    if d["uncategorized"]:
        print(f"    {d['uncategorized']} uncategorized, so not counted either way.")

    repeats = sorted(((c, n) for c, n in d["by_company"].items() if n > 1),
                     key=lambda kv: (-kv[1], kv[0]))
    if repeats:
        print(f"\n  REPEAT DECLINES  (same company, more than once)")
        for company, n in repeats:
            cats = sorted({r["decline_category"] or "(none)" for r in d["rows"]
                           if r["company"] == company})
            print(f"    {n}×  {company:<24} {', '.join(cats)}")

    print(f"\n  BY SCORE BAND")
    print(f"    {'Band':<8} {'declined':>9} {'applied':>9}")
    for label, _lo, _hi in SCORE_BANDS:
        dec = d["declined_bands"].get(label, 0)
        app = d["applied_bands"].get(label, 0)
        if dec or app:
            print(f"    {label:<8} {dec:>9} {app:>9}")

    if d["uncategorized"]:
        print(f"\n  {d['uncategorized']} declined lead(s) have no category. Add one without")
        print("  restamping the decision date:")
        print("    python3 -m best_foot_forward.utils.triage_lead --jd-id <id> --status declined \\")
        print("        --category <slug> --decided-at '<existing lead_decided_at>' --reason '<existing reason>'")


def ghost_candidates(conn, days=30):
    """Applications silent >= `days` days with no active-stage signal.
    Single source of truth for staleness — used by the manual 'Ghost
    Candidates' report (view_ghosts) and the automatic age-out hook
    (utils/auto_ghost.py)."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT a.id, j.company, j.role, a.stage,
               CAST(julianday('now') - julianday(a.applied_at) AS INTEGER) AS days_out
        FROM applications a
        JOIN jds j ON a.jd_id = j.id
        WHERE a.status = 'applied'
          AND date(a.applied_at) <= ?
          AND (a.stage IS NULL OR a.stage NOT IN ('screen', 'phone_screen', 'interview_1',
                                                   'interview_2', 'interview_3', 'onsite', 'final',
                                                   'final_interview_complete', 'assessment_submitted',
                                                   'cold_outreach', 'offer_received', 'offer_accepted'))
        ORDER BY days_out DESC
    """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def view_ghosts(conn, days=30):
    print(f"\n{'GHOST CANDIDATES':^72}  ({days}+ days silent)")
    hr()

    rows = ghost_candidates(conn, days)

    if not rows:
        print(f"  No applications silent for {days}+ days. Nothing to ghost.")
        return

    print(f"  {'Days':<6} {'Company':<22} {'Role':<36} {'Stage':<14} {'ID'}")
    hr("-")

    for r in rows:
        stage = r["stage"] or "—"
        print(f"  {r['days_out']:<6} {r['company'][:20]:<22} {r['role'][:34]:<36} {stage:<14} {r['id']}")

    print(f"\n  {len(rows)} application(s) silent {days}+ days.")
    print(f"  These are auto-ghosted at the next CLI start/exit — see data/audit_log.jsonl for the audit trail.")
    print(f"  (Seeing candidates here means the automatic hook hasn't run yet this session, or is disabled.)")


def view_followup(conn):
    print(f"\n{'FOLLOW-UP QUEUE':^72}")
    hr()

    today = date.today().isoformat()

    rows = conn.execute("""
        SELECT a.id, j.company, j.role, a.follow_up_date, a.follow_up_count,
               a.stage, date(a.applied_at) AS applied_at
        FROM applications a
        JOIN jds j ON a.jd_id = j.id
        WHERE a.status = 'applied'
          AND a.follow_up_date IS NOT NULL
          AND a.follow_up_date <= ?
        ORDER BY a.follow_up_date ASC
    """, (today,)).fetchall()

    if not rows:
        print("  No follow-ups due. Set follow_up_date on an application to schedule one.")
        print("\n  Example:")
        print("    UPDATE applications SET follow_up_date=date('now', '+14 days') WHERE id=?")
        return

    print(f"  {'Due':<12} {'Company':<22} {'Role':<34} {'Stage':<14} {'Sent':<6} {'Applied'}")
    hr("-")

    for r in rows:
        r = dict(r)
        stage = r["stage"] or "—"
        count = str(r["follow_up_count"] or 0)
        print(f"  {r['follow_up_date']:<12} {r['company'][:20]:<22} {r['role'][:32]:<34} {stage:<14} {count:<6} {r['applied_at']}")

    print(f"\n  {len(rows)} follow-up(s) due.")
    print(f"\n  After sending, update the record:")
    print(f"    UPDATE applications")
    print(f"    SET follow_up_count=follow_up_count+1, follow_up_date=date('now', '+14 days')")
    print(f"    WHERE id=?")
    print(f"  Or clear the queue: SET follow_up_date=NULL, follow_up_count=follow_up_count+1")


def view_upcoming(conn):
    print(f"\n{'UPCOMING DATES':^72}")
    hr()

    today = date.today().isoformat()

    interviews = conn.execute("""
        SELECT c.interview_date AS dt, c.interview_time AS tm,
               j.company, j.role,
               c.name AS contact, c.interview_stage AS detail,
               'Interview' AS kind
        FROM contacts c
        JOIN jds j ON c.jd_id = j.id
        WHERE c.interview_date IS NOT NULL AND c.interview_date >= ?
        ORDER BY c.interview_date, c.interview_time NULLS LAST
    """, (today,)).fetchall()

    assessments = conn.execute("""
        SELECT ass.deadline AS dt, NULL AS tm,
               j.company, j.role,
               ass.type AS contact, ass.description AS detail,
               'Assessment' AS kind
        FROM assessments ass
        JOIN applications a ON ass.application_id = a.id
        JOIN jds j ON a.jd_id = j.id
        WHERE ass.deadline IS NOT NULL AND ass.submitted_at IS NULL AND ass.deadline >= ?
        ORDER BY ass.deadline
    """, (today,)).fetchall()

    rows = sorted(
        [dict(r) for r in interviews] + [dict(r) for r in assessments],
        key=lambda r: (r["dt"], r["tm"] or "")
    )

    if not rows:
        print("  No upcoming interviews or assessment deadlines.")
        return

    print(f"  {'Date':<12} {'Time':<8} {'Kind':<12} {'Company':<20} {'Role':<30} {'Detail'}")
    hr("-")

    for r in rows:
        tm      = (r["tm"] or "")[:5] or "—"
        detail  = (r["detail"] or "")[:35]
        print(f"  {r['dt']:<12} {tm:<8} {r['kind']:<12} {r['company'][:18]:<20} {r['role'][:28]:<30} {detail}")

    print(f"\n  {len(rows)} item(s).")
