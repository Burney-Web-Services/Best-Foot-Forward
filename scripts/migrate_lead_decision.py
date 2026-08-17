#!/usr/bin/env python3
"""One-off, idempotent migration for lead triage-decision capture (phase 2 of the
declined-leads feature).

Adds two columns to `jds`:
  • `lead_decided_at` — ISO datetime the lead left 'pending' for a triage decision.
    Until now the declined views ordered by `evaluated_at` (when it was *scored*)
    as a proxy for "recently declined", which misleads once a lead scored weeks
    ago is declined today.
  • `decline_reason` — the seeker's own words for why they passed, distinct from
    `summary` (Claude's evaluate-job fit analysis).

Backfill: existing `declined` rows get `lead_decided_at = evaluated_at`, so the
column is populated for every lead already triaged. That date is really the
scoring date, not the decision date — accepted deliberately, since the two were
same-session for all existing declines. Rows triaged from here on get a true
decision timestamp from `utils/triage_lead.py`.

`db.init_db()` uses CREATE TABLE IF NOT EXISTS, so it will not retro-add columns
to an existing table — this script does. Safe to run more than once.

Usage:  python3 scripts/migrate_lead_decision.py
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src", "best_foot_forward")))

from db import get_conn  # noqa: E402


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


NEW_COLUMNS = [
    ("lead_decided_at", "TEXT"),
    ("decline_reason", "TEXT"),
]


def main():
    conn = get_conn()
    try:
        for name, coltype in NEW_COLUMNS:
            if column_exists(conn, "jds", name):
                print(f"• jds.{name} already present — skipping ALTER")
            else:
                conn.execute(f"ALTER TABLE jds ADD COLUMN {name} {coltype}")
                print(f"✓ added jds.{name}")

        cur = conn.execute(
            "UPDATE jds SET lead_decided_at = evaluated_at "
            "WHERE lead_status = 'declined' AND lead_decided_at IS NULL "
            "AND evaluated_at IS NOT NULL"
        )
        print(f"✓ backfilled lead_decided_at from evaluated_at on {cur.rowcount} declined lead(s)")

        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM jds WHERE lead_status='declined' AND lead_decided_at IS NOT NULL"
        ).fetchone()[0]
        print(f"✓ migration complete — {n} declined lead(s) now carry a decision date")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
