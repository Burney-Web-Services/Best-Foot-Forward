#!/usr/bin/env python3
"""One-off, idempotent migration for offer-acceptance tracking.

Adds 8 columns to `applications` — offer_received_at, offer_salary,
offer_total_comp, offer_currency, offer_title, offer_start_date,
offer_deadline, offer_notes — see the "Offer terms" comment block in
schema.sql for the full reasoning (columns on `applications`, not a
separate `offers` table).

Calls `db.init_db()` first, unlike the prior migration scripts. `init_db()`
only runs `CREATE TABLE IF NOT EXISTS` statements, so on an existing,
populated database it's a genuine no-op — but on a brand-new empty database
(no `applications` table at all yet) it's what makes the table exist in the
first place. Without this, the ALTERs below would fail with "no such table:
applications" on a fresh clone, making this migration a special case for
existing users only.

No backfill: there is no offer data anywhere to backfill from. Offer terms
land only through `utils/record_offer.py` going forward.

Usage:
    python3 scripts/migrate_offer_columns.py [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src", "best_foot_forward")))

from db import DATA_DIR, get_conn, init_db  # noqa: E402


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


NEW_COLUMNS = [
    ("offer_received_at", "TEXT"),
    ("offer_salary", "INTEGER"),
    ("offer_total_comp", "INTEGER"),
    ("offer_currency", "TEXT"),
    ("offer_title", "TEXT"),
    ("offer_start_date", "TEXT"),
    ("offer_deadline", "TEXT"),
    ("offer_notes", "TEXT"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the planned ALTERs without committing.")
    args = parser.parse_args()

    # get_conn()/init_db() assume DATA_DIR already exists (true for every
    # existing installation, since some earlier step always created it first —
    # but not guaranteed on a truly untouched clone). Making that explicit here
    # is what actually delivers on running cleanly against a brand-new DB.
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    conn = get_conn()
    try:
        pending = [(n, t) for n, t in NEW_COLUMNS if not column_exists(conn, "applications", n)]

        if args.dry_run:
            if not pending:
                print("✓ dry run — all 8 offer columns already present, nothing to do")
                return
            print("Dry run — would add:")
            for name, coltype in pending:
                print(f"  ALTER TABLE applications ADD COLUMN {name} {coltype}")
            return

        for name, coltype in NEW_COLUMNS:
            if column_exists(conn, "applications", name):
                print(f"• applications.{name} already present — skipping ALTER")
            else:
                conn.execute(f"ALTER TABLE applications ADD COLUMN {name} {coltype}")
                print(f"✓ added applications.{name}")

        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE offer_received_at IS NOT NULL"
        ).fetchone()[0]
        print(f"✓ migration complete — {n} application(s) carry offer terms")
        print("  Record one with:")
        print("    python3 -m best_foot_forward.utils.record_offer --company '<Company>' --state accepted ...")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
