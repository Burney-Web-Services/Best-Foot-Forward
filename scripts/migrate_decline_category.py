#!/usr/bin/env python3
"""One-off, idempotent migration adding `jds.decline_category`.

`decline_reason` captures why the seeker passed, in their own words — which reads
well in a list and aggregates not at all. `decline_category` is the groupable
counterpart: one slug from `triage_lead.DECLINE_CATEGORIES`, so a report can answer
"what do I keep passing on?" rather than only "what did I say about each one?".

No backfill here. The categories for already-declined leads are inferred from each
lead's `summary` prose and confirmed by the seeker one at a time — a judgement call,
not something a migration should guess. They land via `triage_lead --category`,
which is also the only supported write path for this column.

A nullable ADD COLUMN needs no table rebuild, so unlike
`migrate_lead_status_default.py` this is a plain ALTER — no create/copy/drop/rename
dance, no view juggling.

`db.init_db()` uses CREATE TABLE IF NOT EXISTS, so it will not retro-add the column
to an existing table — this script does. Safe to run more than once.

Usage:  python3 scripts/migrate_decline_category.py
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src", "best_foot_forward")))

from db import get_conn  # noqa: E402


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def main():
    conn = get_conn()
    try:
        if column_exists(conn, "jds", "decline_category"):
            print("• jds.decline_category already present — nothing to do")
        else:
            conn.execute("ALTER TABLE jds ADD COLUMN decline_category TEXT")
            conn.commit()
            print("✓ added jds.decline_category")

        total = conn.execute(
            "SELECT COUNT(*) FROM jds WHERE lead_status = 'declined'"
        ).fetchone()[0]
        done = conn.execute(
            "SELECT COUNT(*) FROM jds "
            "WHERE lead_status = 'declined' AND decline_category IS NOT NULL"
        ).fetchone()[0]
        print(f"✓ migration complete — {done} of {total} declined lead(s) categorized")
        if done < total:
            print("  Categorize the rest with:")
            print("    python3 -m best_foot_forward.utils.triage_lead --jd-id <id> "
                  "--status declined --category <slug> --decided-at <existing lead_decided_at>")
            print("  Pass --decided-at (and the existing --reason) so re-triaging does not "
                  "overwrite the real decision date or blank a reason already recorded.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
