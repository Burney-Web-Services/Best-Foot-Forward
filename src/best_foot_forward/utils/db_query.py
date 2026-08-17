"""
Run a SQL query against best_foot_forward.db.

Usage:
    python3 src/best_foot_forward/utils/db_query.py "SELECT * FROM applications LIMIT 5"

    python3 src/best_foot_forward/utils/db_query.py \\
        "UPDATE jds SET summary = ? WHERE id = ?" \\
        --params-json '["Strong platform fit; team\\u2019s stated priority is reliability work.", 42]'

--params-json is required for any value containing an apostrophe or a newline —
narrative prose (an evaluate-job summary, a decline reason in the seeker's own
words) routinely does. Never hand-escape quotes into the SQL string itself; a
long summary with a stray apostrophe is exactly the input that silently
truncates mid-string and produces a corrupted or partial write. Bind it instead.
"""
import argparse
import json
import os
import sqlite3
import sys

# This script is invoked as a direct file path (see module docstring), which
# only adds its own directory (utils/) to sys.path, not src/best_foot_forward/
# where db.py lives -- same fix audit_log.py already needed for the same reason.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from db import DATA_DIR  # noqa: E402

# Was a hand-rolled path relative to this file, ignoring BFF_DATA_DIR entirely
# -- every other script here resolves through db.py's DATA_DIR (which honors
# the override), but this one didn't, so a scripted/UAT run's score UPDATE
# landed on the real production DB instead of the isolated one. Confirmed
# happening for real: a UAT run's fictional score overwrote real jds.id=7
# (DraftKings) before this fix, caught and reverted from a pre-session backup.
DB_PATH = os.path.join(DATA_DIR, 'best_foot_forward.db')


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run a SQL query against best_foot_forward.db.")
    ap.add_argument("sql", help="SQL statement. Use ? placeholders with --params-json "
                                 "for any value that isn't a safe bare literal.")
    ap.add_argument("--params-json", help="JSON array of bind parameters for ? placeholders.")
    args = ap.parse_args(argv)

    params = json.loads(args.params_json) if args.params_json else []

    conn = sqlite3.connect(os.path.normpath(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        c.execute(args.sql, params)
        if args.sql.strip().upper().startswith('SELECT'):
            rows = c.fetchall()
            if not rows:
                print("(no rows)")
            else:
                headers = rows[0].keys()
                col_widths = [max(len(h), max(len(str(r[h])) for r in rows)) for h in headers]
                fmt = '  '.join(f'{{:<{w}}}' for w in col_widths)
                print(fmt.format(*headers))
                print('  '.join('-' * w for w in col_widths))
                for row in rows:
                    print(fmt.format(*[str(row[h]) for h in headers]))
        else:
            conn.commit()
            print(f"OK — {c.rowcount} row(s) affected")
    except sqlite3.Error as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
