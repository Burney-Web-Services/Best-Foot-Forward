#!/usr/bin/env python3
"""
Best Foot Forward CLI
Run interactively: python3 src/best_foot_forward/cli.py
Run a specific report: python3 src/best_foot_forward/cli.py <command>

Commands: upcoming, ghosts, followup, leads, declined, patterns, weekly,
matches, passes, skills, gaps, companies, salaries, full
"""

import sys as _sys, os as _os
# src/ on the path, so the package-absolute imports inside reports/ resolve.
# Running this file as a script only puts src/best_foot_forward/ on sys.path,
# which is enough for `from db import ...` here but not for
# `from best_foot_forward.utils...` inside reports/applications.py — so the
# invocation the docs give (python3 src/best_foot_forward/cli.py) died on
# ModuleNotFoundError before this line existed.
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '../')))
del _sys, _os

import sys
from db import get_conn
from reports import skills as sk
from reports import applications as ap
from utils.auto_ghost import auto_ghost_stale_applications

WIDTH = 52

MENU = [
    ("upcoming",   "Upcoming Dates",            lambda c: ap.view_upcoming(c)),
    ("ghosts",     "Ghost Candidates",          lambda c: ap.view_ghosts(c)),
    ("followup",   "Follow-up Queue",           lambda c: ap.view_followup(c)),
    ("leads",      "Pending Leads (sourced)",   lambda c: ap.view_leads(c)),
    ("declined",   "Declined Leads",            lambda c: ap.view_declined(c)),
    ("patterns",   "Decline Patterns",          lambda c: ap.view_decline_patterns(c)),
    ("weekly",     "Weekly Activity Report",    lambda c: ap.view_weekly(c)),
    ("matches",    "JD Match Scores",           lambda c: ap.view_matches(c)),
    ("passes",     "Pass/Decline Analysis",       lambda c: ap.view_passes(c)),
    ("skills",     "Top Demanded Skills",       lambda c: sk.view_frequency(c)),
    ("gaps",       "Skill Gaps",               lambda c: sk.view_gaps(c)),
    ("companies",  "Skills by Company",        lambda c: sk.view_by_company(c)),
    ("salaries",   "Salary Ranges",            lambda c: sk.view_salaries(c)),
    ("full",       "Full Skills Report",       lambda c: (sk.view_frequency(c), sk.view_gaps(c), sk.view_by_company(c), sk.view_salaries(c))),
]


def print_menu():
    print("\n" + "═" * WIDTH)
    print(f"{'Best Foot Forward':^{WIDTH}}")
    print("═" * WIDTH)
    for i, (_, label, _) in enumerate(MENU, 1):
        print(f"  {i}.  {label}")
    print(f"  0.  Quit")
    print("─" * WIDTH)


def _require_initialized_db():
    """A fresh clone has no data/ at all, and get_conn() will happily create an
    empty DB file rather than fail. Every report then dies on `no such table`,
    which reads as a broken tool rather than "you haven't onboarded yet"."""
    from db import DB_PATH
    import os
    import sqlite3 as _sqlite3
    if not os.path.exists(DB_PATH):
        return f"No database yet at {DB_PATH}."
    try:
        probe = _sqlite3.connect(DB_PATH)
        has_jds = probe.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='jds'"
        ).fetchone()
        probe.close()
    except _sqlite3.Error as exc:
        return f"Could not read {DB_PATH}: {exc}"
    return None if has_jds else f"The database at {DB_PATH} has no tables yet."


def main():
    problem = _require_initialized_db()
    if problem:
        print(problem)
        print("Run the onboarding workflow in your coding agent first "
              "(`/onboard` in Claude Code, `$onboard` in Codex).")
        sys.exit(1)

    conn = get_conn()
    try:
        auto_ghost_stale_applications(conn)

        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            dispatch = {key: fn for key, _, fn in MENU}
            fn = dispatch.get(cmd)
            if fn:
                fn(conn)
            else:
                print(f"Unknown command: {cmd!r}")
                print(f"Available: {', '.join(dispatch)}")
                sys.exit(1)
            return

        while True:
            print_menu()
            choice = input("  Choice: ").strip()
            if choice == "0":
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(MENU):
                    MENU[idx][2](conn)
                    input("\n  [Enter to continue]")
                else:
                    print("  Invalid choice.")
            except ValueError:
                print("  Enter a number.")
    finally:
        auto_ghost_stale_applications(conn)
        conn.close()


if __name__ == "__main__":
    main()
