"""Record a triage decision on a lead — the single write path for `jds.lead_status`.

A lead lands `pending` when it's evaluated, and leaves that state when the seeker
decides: `approved` (want it, not right now), `declined` (passed on it), or
`applied` (tailored and submitted — set by track_application.py). Three columns
move together on that transition, which is why they get one entry point instead of
a hand-written UPDATE per caller:

    lead_status       the decision
    lead_decided_at   when it was made (NOT evaluated_at, which is when it was scored)
    decline_reason    why, in the seeker's own words — declines only
    decline_category  the same why, as one groupable slug — declines only

Usage:
    python3 -m best_foot_forward.utils.triage_lead --file-path <abs path> \\
        --status declined --category comp --reason "Salary band tops out below my floor"
    python3 -m best_foot_forward.utils.triage_lead --jd-id 4 --status approved
    python3 -m best_foot_forward.utils.triage_lead --company Keyfactor --status declined \\
        --category role_type --reason "Support track, not engineering"
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from best_foot_forward.db import get_conn, resolve_jd_path
from best_foot_forward.utils.audit_log import log_event

TRIAGE_STATES = ("pending", "approved", "declined", "applied")
# States that represent a decision having been made. 'pending' is the absence of
# one, so it clears the decision columns rather than stamping them.
DECIDED_STATES = ("approved", "declined", "applied")

# The decline vocabulary, slug -> gloss. This is the single definition: the
# interactive prompt below, the Decline Patterns report, the Logseq board, and the
# evaluate-job workflow all render from it, so the wording cannot drift between
# where a category is chosen and where it is later explained.
#
# Deliberately one *primary* category per decline, not a set. Most declines are
# layered (Interra Health was stack + role_type + level); the rule is to pick the
# decisive one and let `decline_reason` carry the rest in the seeker's own words.
# A single column also keeps this script's one atomic UPDATE — the whole reason the
# module exists — and keeps reconcile_graph's scalar property map unchanged.
#
# 'strategy' is not 'other'. A strategy decline is fully explained; there was
# nothing wrong with the posting, the seeker was spending the effort elsewhere.
# 'other' means genuinely unclassified. Reports keep them apart so declines that
# say something about the market can be counted separately from pipeline choices.
DECLINE_CATEGORIES = {
    "domain":    "industry/sector outside your target",
    "stack":     "hard-requirement tech you don't have",
    "role_type": "wrong KIND of job (support, mgmt, platform vs product QA)",
    "level":     "right job, wrong seniority (over- or under-leveled)",
    "comp":      "salary below your floor",
    "location":  "geo or onsite requirement",
    "strategy":  "the posting was fine; you're focusing elsewhere",
    "other":     "none of these; the reason text carries it",
}


def set_lead_status(conn, jd_id: int, status: str, reason: str | None = None,
                    decided_at: str | None = None, category: str | None = None) -> dict:
    """Apply a triage decision to one lead. Returns the row's before/after state.

    Re-triaging overwrites `lead_decided_at` — the latest decision is the one the
    "recently declined" views should order by. Pass `decided_at` to preserve an
    existing date when the re-triage is only adding detail (a category on an
    already-declined lead) rather than making a fresh decision.

    Moving off `declined` clears both `decline_reason` and `decline_category`, so a
    stale explanation can't outlive the decision it explained.
    """
    if status not in TRIAGE_STATES:
        raise ValueError(f"status must be one of {TRIAGE_STATES}, got {status!r}")
    if reason and status != "declined":
        raise ValueError(f"--reason applies to a decline; status is {status!r}")
    if category and status != "declined":
        raise ValueError(f"--category applies to a decline; status is {status!r}")
    if category and category not in DECLINE_CATEGORIES:
        raise ValueError(
            f"category must be one of {tuple(DECLINE_CATEGORIES)}, got {category!r}"
        )

    row = conn.execute(
        "SELECT id, company, role, lead_status, lead_decided_at FROM jds WHERE id = ?",
        (jd_id,),
    ).fetchone()
    if not row:
        raise LookupError(f"No jds row with id={jd_id}")

    if status in DECIDED_STATES:
        stamp = decided_at or datetime.now().isoformat(timespec="seconds")
    else:
        stamp = None

    conn.execute(
        "UPDATE jds SET lead_status = ?, lead_decided_at = ?, decline_reason = ?, "
        "decline_category = ? WHERE id = ?",
        (status, stamp,
         reason if status == "declined" else None,
         category if status == "declined" else None,
         jd_id),
    )
    conn.commit()

    return {
        "jd_id": jd_id,
        "company": row["company"],
        "role": row["role"],
        "was": row["lead_status"],
        "now": status,
        "decided_at": stamp,
        "reason": reason if status == "declined" else None,
        "category": category if status == "declined" else None,
    }


def resolve_jd_id(conn, jd_id=None, file_path=None, company=None, role=None) -> int:
    """Find exactly one jds row from whichever selector the caller gave."""
    if jd_id is not None:
        return jd_id

    if file_path:
        path = resolve_jd_path(file_path)
        row = conn.execute("SELECT id FROM jds WHERE file_path = ?", (path,)).fetchone()
        if not row:
            raise LookupError(
                f"No jds row with file_path={path}\n"
                "  (paths are compared exact-match — check the row with: "
                "SELECT id, company, file_path FROM jds)"
            )
        return row["id"]

    sql = "SELECT id, company, role FROM jds WHERE company = ? COLLATE NOCASE"
    params: list = [company]
    if role:
        sql += " AND role = ? COLLATE NOCASE"
        params.append(role)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        raise LookupError(f"No jds row for company={company!r}" + (f", role={role!r}" if role else ""))
    if len(rows) > 1:
        listing = "\n".join(f"    --jd-id {r['id']}  {r['company']} — {r['role']}" for r in rows)
        raise LookupError(
            f"{len(rows)} leads match company={company!r}; narrow with --role or --jd-id:\n{listing}"
        )
    return rows[0]["id"]


def category_menu() -> str:
    """Render the decline vocabulary as a numbered menu, glossed."""
    width = max(len(k) for k in DECLINE_CATEGORIES)
    lines = [f"  {i} {slug:<{width}}  {gloss}"
             for i, (slug, gloss) in enumerate(DECLINE_CATEGORIES.items(), 1)]
    return "\n".join(lines)


def prompt_for_category() -> str | None:
    """Ask which category applies. Returns None if the seeker skips.

    Only called on a TTY. A decline recorded from a script or a hook has nobody to
    answer, so those leave the column NULL and the report counts them as
    uncategorized rather than this blocking on stdin forever.
    """
    slugs = list(DECLINE_CATEGORIES)
    print("\nDeclined — what was the main reason?\n")
    print(category_menu())
    print("\n  (Layered decline? Pick the decisive one; --reason carries the rest.)")
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not raw:
            return None
        if raw in DECLINE_CATEGORIES:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(slugs):
            return slugs[int(raw) - 1]
        print(f"  Not a choice. Enter 1-{len(slugs)}, a slug, or blank to skip.")


def main():
    p = argparse.ArgumentParser(
        description="Record a triage decision on a lead.",
        epilog="decline categories:\n" + category_menu(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sel = p.add_mutually_exclusive_group(required=True)
    sel.add_argument("--jd-id", type=int, help="jds.id of the lead")
    sel.add_argument("--file-path", help="jds.file_path of the lead (canonicalized before lookup)")
    sel.add_argument("--company", help="company name (add --role if it has more than one open lead)")
    p.add_argument("--role", help="role name, to disambiguate --company")
    p.add_argument("--status", required=True, choices=TRIAGE_STATES, help="the triage decision")
    p.add_argument("--reason", help="one-line decline reason in the seeker's words (declines only)")
    p.add_argument("--category", choices=list(DECLINE_CATEGORIES), metavar="SLUG",
                   help="groupable decline category (declines only); see the list below. "
                        "Omit on a TTY and you'll be asked.")
    p.add_argument("--decided-at",
                   help="override the decision timestamp. Pass the row's existing "
                        "lead_decided_at when re-triaging only to add detail, so the real "
                        "decision date survives (a re-triage overwrites it by default).")
    args = p.parse_args()

    if args.role and not args.company:
        p.error("--role only applies with --company")

    category = args.category
    if args.status == "declined" and not category and sys.stdin.isatty():
        category = prompt_for_category()

    conn = get_conn()
    try:
        jd_id = resolve_jd_id(conn, args.jd_id, args.file_path, args.company, args.role)
        result = set_lead_status(conn, jd_id, args.status, args.reason,
                                 decided_at=args.decided_at, category=category)
    except (LookupError, ValueError) as e:
        print(f"[triage_lead] {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    log_event("triage-lead", "set_lead_status", **result)

    line = (f"[triage_lead] {result['company']} — {result['role']}: "
            f"{result['was']} → {result['now']}")
    if result["decided_at"]:
        line += f" (decided {result['decided_at'][:10]})"
    print(line)
    if result["category"]:
        print(f"  category: {result['category']} — {DECLINE_CATEGORIES[result['category']]}")
    if result["reason"]:
        print(f"  reason: {result['reason']}")
    if result["now"] == "declined" and not result["category"]:
        print("  (uncategorized — add one with --category so it counts in the "
              "Decline Patterns report)")


if __name__ == "__main__":
    main()
