#!/usr/bin/env python3
"""One-off, idempotent migration for the skill-gap-vocabulary fix.

Adds two columns to `jd_required_skills`:
  - canonical_label: alias-normalized display form ("k8s" -> "Kubernetes"),
    what lets reports/skills.py aggregate equivalent mentions instead of each
    staying a singleton HAVING demand >= 2 filters out.
  - source: 'lexicon' | 'profile' | 'llm' — where the term's vocabulary came from.

No backfill of *values* here — canonicalizing 507+ existing rows against the
real JD text (or re-deriving it for imported rows with no file_path) is a
judgment-bearing operation, not a schema migration. That's
utils/reindex_jd_skills.py; run it after this.

Note: schema.sql's `CREATE TABLE IF NOT EXISTS jd_required_skills` already
declares canonical_label/source (for fresh installs), so on a real
pre-existing DB that CREATE TABLE is a no-op and running db.init_db()
directly against it would crash on the schema's own
`CREATE INDEX ... ON jd_required_skills(canonical_label)` — the column
genuinely isn't there yet. So this script ALTERs first (real runs only;
--dry-run never touches the DB) and only calls init_db() once the column is
guaranteed to exist, or the table doesn't exist yet at all (in which case
init_db() creates it fresh, columns included).

Usage:  python3 scripts/migrate_jd_skill_canonical.py [--dry-run]
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src", "best_foot_forward")))

from db import DATA_DIR, DB_PATH, get_conn, init_db  # noqa: E402


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def table_exists(conn, table):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


NEW_COLUMNS = [
    ("canonical_label", "TEXT"),
    ("source", "TEXT"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the planned ALTERs without touching the DB.")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    db_exists = os.path.exists(DB_PATH)
    table_already_exists = False
    pending = list(NEW_COLUMNS)
    if db_exists:
        probe = sqlite3.connect(DB_PATH)
        probe.row_factory = sqlite3.Row
        try:
            table_already_exists = table_exists(probe, "jd_required_skills")
            if table_already_exists:
                pending = [(n, t) for n, t in NEW_COLUMNS if not column_exists(probe, "jd_required_skills", n)]
        finally:
            probe.close()

    if args.dry_run:
        if not db_exists or not table_already_exists:
            print("Dry run — jd_required_skills doesn't exist yet; "
                  "init_db() will create it fresh with both columns already present.")
        elif not pending:
            print("✓ dry run — both columns already present, nothing to do")
        else:
            print("Dry run — would add:")
            for name, coltype in pending:
                print(f"  ALTER TABLE jd_required_skills ADD COLUMN {name} {coltype}")
            print("  CREATE INDEX IF NOT EXISTS idx_jd_required_skills_canonical ON jd_required_skills(canonical_label)")
        return

    # Real run: ALTER any missing columns directly first, so init_db()'s
    # CREATE INDEX (which assumes canonical_label exists) doesn't crash
    # against a pre-existing table that predates this migration.
    if table_already_exists:
        if pending:
            alter_conn = sqlite3.connect(DB_PATH)
            try:
                for name, coltype in pending:
                    alter_conn.execute(f"ALTER TABLE jd_required_skills ADD COLUMN {name} {coltype}")
                    print(f"✓ added jd_required_skills.{name}")
                alter_conn.commit()
            finally:
                alter_conn.close()
        else:
            for name, _ in NEW_COLUMNS:
                print(f"• jd_required_skills.{name} already present — skipping ALTER")

    init_db()
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM jd_required_skills").fetchone()[0]
        canonicalized = conn.execute(
            "SELECT COUNT(*) FROM jd_required_skills WHERE canonical_label IS NOT NULL"
        ).fetchone()[0]
        print(f"✓ migration complete — {canonicalized}/{total} existing row(s) have a canonical_label")
        if total and not canonicalized:
            print("  Backfill with: python3 -m best_foot_forward.utils.reindex_jd_skills --all")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
