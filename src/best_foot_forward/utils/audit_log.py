"""Shared append-only audit trail for automatic/unattended actions.
One JSON line per event — any hook or workflow calls log_event() instead
of inventing its own logging setup. Lives in data/ (blanket-gitignored)
since entries can contain PII (company/role names)."""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..')))  # src/best_foot_forward/
del _sys, _os

import json
import os
from datetime import datetime, timezone

from db import DATA_DIR

LOG_PATH = os.path.join(DATA_DIR, "audit_log.jsonl")


def log_event(actor, action, **fields):
    """Append one line: {"ts": ISO8601 UTC, "actor": ..., "action": ..., **fields}."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action, **fields}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
