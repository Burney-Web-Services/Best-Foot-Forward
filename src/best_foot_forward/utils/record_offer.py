"""Record an offer transition, or close out other applications — the single write
path for `applications.offer_*`/`stage`/`status`/`concluded_at` around an offer.

Three states, each moving `stage`/`status` together and setting `concluded_at`
only once a decision is final:

    received   offer_received / offer            (concluded_at stays NULL — deciding, not done)
    accepted   offer_accepted / accepted          (concluded_at set)
    declined   declined_offer / offer_declined    (concluded_at set)

Offer terms (`offer_salary`, `offer_total_comp`, `offer_currency`, `offer_title`,
`offer_start_date`, `offer_deadline`) are combined with `COALESCE` against the
existing value on every call — a `--state accepted` call after an earlier
`--state received` call adds the final numbers without blanking whatever was
already captured. `offer_notes` appends instead, matching `applications.notes`'s
existing append-only convention.

`close_applications` is the withdraw/not-pursue sweep run alongside an acceptance
(see `.claude/commands/accept-offer.md`). It always takes explicit ids — never a
blind `WHERE status='applied'` sweep — and is guarded by `concluded_at IS NULL` so
re-running it is a no-op on rows it already closed.

Usage:
    python3 -m best_foot_forward.utils.record_offer --company 'Acme Corp' \\
        --state accepted --salary 100000 --total-comp 120000 --title 'Senior Manager' \\
        --start-date 2026-09-08 --decided-at 2026-08-07

    python3 -m best_foot_forward.utils.record_offer --close-ids 180,190 \\
        --close-status withdrawn --close-reason 'Accepted the Acme Corp offer'
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from best_foot_forward.db import get_conn
from best_foot_forward.utils.audit_log import log_event

# state -> (stage, status, concludes)
OFFER_STATES = {
    "received": ("offer_received", "offer", False),
    "accepted": ("offer_accepted", "accepted", True),
    "declined": ("declined_offer", "offer_declined", True),
}

CLOSE_STATUSES = ("withdrawn", "not_pursued")


def record_offer(conn, application_id: int, state: str, *, salary=None, total_comp=None,
                 currency=None, title=None, start_date=None, deadline=None,
                 received_at=None, decided_at=None, notes=None) -> dict:
    if state not in OFFER_STATES:
        raise ValueError(f"state must be one of {tuple(OFFER_STATES)}, got {state!r}")
    stage, status, concludes = OFFER_STATES[state]

    row = conn.execute(
        "SELECT a.id, a.stage, a.status, a.concluded_at, a.offer_notes, j.company, j.role "
        "FROM applications a JOIN jds j ON a.jd_id = j.id WHERE a.id = ?",
        (application_id,),
    ).fetchone()
    if not row:
        raise LookupError(f"No applications row with id={application_id}")

    new_concluded_at = (decided_at or date.today().isoformat()) if concludes else row["concluded_at"]

    new_notes = row["offer_notes"]
    if notes:
        new_notes = f"{new_notes}\n\n---\n\n{notes}" if new_notes else notes

    conn.execute(
        "UPDATE applications SET stage = ?, status = ?, concluded_at = ?, "
        "offer_received_at = COALESCE(?, offer_received_at, ?), "
        "offer_salary = COALESCE(?, offer_salary), "
        "offer_total_comp = COALESCE(?, offer_total_comp), "
        "offer_currency = COALESCE(?, offer_currency), "
        "offer_title = COALESCE(?, offer_title), "
        "offer_start_date = COALESCE(?, offer_start_date), "
        "offer_deadline = COALESCE(?, offer_deadline), "
        "offer_notes = ? "
        "WHERE id = ?",
        (stage, status, new_concluded_at,
         received_at, date.today().isoformat(),
         salary, total_comp, currency, title, start_date, deadline,
         new_notes, application_id),
    )
    conn.commit()

    return {
        "application_id": application_id,
        "company": row["company"],
        "role": row["role"],
        "was_stage": row["stage"],
        "was_status": row["status"],
        "stage": stage,
        "status": status,
        "concluded_at": new_concluded_at,
        "salary": salary,
        "total_comp": total_comp,
        "start_date": start_date,
    }


def close_applications(conn, ids: list[int], status: str, reason: str | None = None) -> list[dict]:
    """Close a named set of applications as withdrawn or not_pursued. Skips ids
    that are already concluded (re-run safe) but raises on an id that doesn't
    exist — a typo in an id the caller explicitly named should surface, not
    silently vanish."""
    if status not in CLOSE_STATUSES:
        raise ValueError(f"status must be one of {CLOSE_STATUSES}, got {status!r}")
    if not ids:
        raise ValueError("close_applications requires explicit ids")

    results = []
    for app_id in ids:
        # LEFT JOIN, not JOIN: an application can have jd_id NULL (an orphaned
        # row whose jds record was deleted) and still be a real row worth
        # closing. An inner join would silently exclude it from "found" and
        # make an explicitly-named id raise LookupError as if it never existed.
        row = conn.execute(
            "SELECT a.id, a.concluded_at, a.notes, j.company, j.role "
            "FROM applications a LEFT JOIN jds j ON a.jd_id = j.id WHERE a.id = ?",
            (app_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"No applications row with id={app_id}")
        if row["concluded_at"] is not None:
            continue  # already concluded — idempotent no-op

        new_notes = row["notes"]
        if reason:
            new_notes = f"{new_notes}\n\n---\n\n{reason}" if new_notes else reason

        conn.execute(
            "UPDATE applications SET status = ?, concluded_at = date('now'), notes = ? "
            "WHERE id = ? AND concluded_at IS NULL",
            (status, new_notes, app_id),
        )
        results.append({"id": app_id, "company": row["company"], "role": row["role"], "status": status})

    conn.commit()
    return results


def resolve_application_id(conn, application_id=None, jd_id=None, company=None, role=None) -> int:
    """Find exactly one applications row from whichever selector the caller gave."""
    if application_id is not None:
        return application_id

    if jd_id is not None:
        row = conn.execute(
            "SELECT id FROM applications WHERE jd_id = ? ORDER BY id DESC LIMIT 1", (jd_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"No applications row for jd_id={jd_id}")
        return row["id"]

    sql = ("SELECT a.id, j.company, j.role FROM applications a JOIN jds j ON a.jd_id = j.id "
           "WHERE j.company = ? COLLATE NOCASE")
    params: list = [company]
    if role:
        sql += " AND j.role = ? COLLATE NOCASE"
        params.append(role)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        raise LookupError(f"No applications row for company={company!r}" + (f", role={role!r}" if role else ""))
    if len(rows) > 1:
        listing = "\n".join(f"    --application-id {r['id']}  {r['company']} — {r['role']}" for r in rows)
        raise LookupError(
            f"{len(rows)} applications match company={company!r}; narrow with --role or --application-id:\n{listing}"
        )
    return rows[0]["id"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--state", choices=list(OFFER_STATES), help="record an offer transition")
    mode.add_argument("--close-ids", help="comma-separated applications.id to close")

    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--application-id", type=int)
    sel.add_argument("--jd-id", type=int)
    sel.add_argument("--company")
    p.add_argument("--role", help="disambiguates --company when it matches more than one application")

    p.add_argument("--salary", type=int, help="base salary as offered/accepted")
    p.add_argument("--total-comp", type=int, help="first-year total incl. bonus/equity")
    p.add_argument("--currency", help="defaults to USD if --salary or --total-comp is given")
    p.add_argument("--title", help="title as offered")
    p.add_argument("--start-date", help="ISO date")
    p.add_argument("--deadline", help="ISO date to respond by")
    p.add_argument("--received-at", help="ISO date the offer landed (defaults to today, once)")
    p.add_argument("--decided-at", help="ISO date accepted/declined (defaults to today) — pass "
                                        "the real date when recording after the fact")
    p.add_argument("--notes", help="appended to offer_notes, not overwritten")

    p.add_argument("--close-status", choices=CLOSE_STATUSES)
    p.add_argument("--close-reason", help="appended to each closed application's notes")

    p.add_argument("--dry-run", action="store_true", help="print what would happen; write nothing")
    args = p.parse_args()

    if args.role and not args.company:
        p.error("--role only applies with --company")
    if args.close_ids and not args.close_status:
        p.error("--close-ids requires --close-status")

    conn = get_conn()
    try:
        if args.state:
            app_id = resolve_application_id(conn, args.application_id, args.jd_id, args.company, args.role)
            currency = args.currency or ("USD" if (args.salary or args.total_comp) else None)

            if args.dry_run:
                print(f"[record_offer] DRY RUN — would set application {app_id} to state={args.state}")
                return

            result = record_offer(
                conn, app_id, args.state,
                salary=args.salary, total_comp=args.total_comp, currency=currency,
                title=args.title, start_date=args.start_date, deadline=args.deadline,
                received_at=args.received_at, decided_at=args.decided_at, notes=args.notes,
            )
            log_event("record-offer", "record_offer", **result)
            print(f"[record_offer] {result['company']} — {result['role']}: "
                  f"{result['was_stage']}/{result['was_status']} → {result['stage']}/{result['status']}")
            if result["salary"]:
                comp = f"{currency} {result['salary']:,}"
                if result["total_comp"]:
                    comp += f" ({currency} {result['total_comp']:,} total)"
                print(f"  offer: {comp}")
        else:
            ids = [int(x) for x in args.close_ids.split(",")]
            if args.dry_run:
                print(f"[record_offer] DRY RUN — would close {ids} as {args.close_status}")
                return
            results = close_applications(conn, ids, args.close_status, reason=args.close_reason)
            log_event("record-offer", "close_applications",
                      ids=[r["id"] for r in results], status=args.close_status)
            if not results:
                print(f"[record_offer] nothing to close — all {len(ids)} already concluded")
            for r in results:
                print(f"[record_offer] closed {r['company']} — {r['role']} as {args.close_status}")
    except (LookupError, ValueError) as e:
        print(f"[record_offer] {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
