"""Automatic age-out: on CLI start and exit, flip stale applications
(reports.applications.ghost_candidates' criteria) to status='ghosted',
concluded_at=date('now'). No confirmation prompt is possible in an
unattended hook, so every change is appended to the shared audit log
instead of printed.

Reuses the existing 'ghosted' status already recognized by
utils/generate_home.py's DEAD tuple — no new status value, no schema change.

Safe to call twice in one process lifetime (CLI start + exit): the second
call's candidate query excludes rows already flipped, since
ghost_candidates() filters status='applied'.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))  # src/best_foot_forward/
del _sys, _os

import logging

from reports.applications import ghost_candidates
from utils.audit_log import log_event

_logger = logging.getLogger("bff.auto_ghost")


def auto_ghost_stale_applications(conn, days=30):
    """Find + ghost stale applications. Returns the list of application ids
    actually changed (empty list if none, or on internal error)."""
    try:
        candidates = ghost_candidates(conn, days)
        if not candidates:
            return []

        ghosted_ids = []
        for row in candidates:
            cur = conn.execute(
                "UPDATE applications SET status='ghosted', concluded_at=date('now') "
                "WHERE id=? AND status='applied'",
                (row["id"],),
            )
            if cur.rowcount:
                ghosted_ids.append(row["id"])
                log_event(
                    "auto_ghost", "ghost",
                    application_id=row["id"], company=row["company"], role=row["role"],
                    old_status="applied", new_status="ghosted",
                    days_stale=row["days_out"], stage=row["stage"] or "none",
                    threshold_days=days,
                )
        conn.commit()
        return ghosted_ids
    except Exception:
        _logger.exception("auto_ghost_stale_applications failed")
        return []
