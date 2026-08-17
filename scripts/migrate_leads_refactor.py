#!/usr/bin/env python3
"""One-off, idempotent migration for the leads refactor.

Adds `jds.summary` (evaluate-job narrative) and the `active_leads` view to the
live DB. `db.init_db()` uses CREATE TABLE IF NOT EXISTS, so it will not retro-add
the column to an existing table — this script does. Safe to run more than once.

Usage:  python3 scripts/migrate_leads_refactor.py
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src", "best_foot_forward")))

from db import get_conn  # noqa: E402


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


ACTIVE_LEADS_VIEW = """
CREATE VIEW IF NOT EXISTS active_leads AS
    SELECT j.id, j.company, j.role, j.score, j.source, j.url, j.summary,
           j.salary_min, j.salary_max, j.salary_currency, j.lead_status,
           date(j.evaluated_at) AS evaluated
    FROM jds j
    LEFT JOIN applications a ON a.jd_id = j.id
    WHERE j.lead_status IN ('pending', 'approved') AND a.id IS NULL
    ORDER BY (j.score IS NULL), j.score DESC, j.company;
"""


def main():
    conn = get_conn()
    try:
        if column_exists(conn, "jds", "summary"):
            print("• jds.summary already present — skipping ALTER")
        else:
            conn.execute("ALTER TABLE jds ADD COLUMN summary TEXT")
            print("✓ added jds.summary")

        # A view definition can drift from schema.sql; drop + recreate so this
        # script is the reliable way to sync the live view to the current shape.
        conn.execute("DROP VIEW IF EXISTS active_leads")
        conn.executescript(ACTIVE_LEADS_VIEW)
        print("✓ (re)created active_leads view")

        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM active_leads").fetchone()[0]
        print(f"✓ migration complete — active_leads currently returns {n} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
