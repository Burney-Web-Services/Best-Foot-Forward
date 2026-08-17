"""Triage decisions on leads: lead_status, lead_decided_at, decline_reason and
decline_category move together, and only through set_lead_status.
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils.triage_lead import (
    DECLINE_CATEGORIES,
    resolve_jd_id,
    set_lead_status,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def add_lead(conn, company="Acme", role="QA Engineer", **cols):
    fields = {"company": company, "role": role, "lead_status": "pending",
              "evaluated_at": "2026-07-01T09:00:00", "score": 70, **cols}
    conn.execute(
        f"INSERT INTO jds ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
        list(fields.values()),
    )
    conn.commit()
    return conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()["id"]


def get(conn, jd_id):
    return conn.execute("SELECT * FROM jds WHERE id=?", (jd_id,)).fetchone()


def test_schema_has_decision_columns():
    conn = make_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(jds)")}
    assert {"lead_decided_at", "decline_reason", "decline_category"} <= cols


def test_decline_stamps_timestamp_and_reason():
    conn = make_db()
    jd_id = add_lead(conn)
    result = set_lead_status(conn, jd_id, "declined", reason="Support track, not engineering")

    row = get(conn, jd_id)
    assert row["lead_status"] == "declined"
    assert row["decline_reason"] == "Support track, not engineering"
    # The decision date is its own fact, not a copy of the eval date.
    assert row["lead_decided_at"] is not None
    assert row["lead_decided_at"] != row["evaluated_at"]
    assert result["was"] == "pending" and result["now"] == "declined"


def test_approve_and_apply_stamp_timestamp_without_reason():
    conn = make_db()
    for status in ("approved", "applied"):
        jd_id = add_lead(conn)
        set_lead_status(conn, jd_id, status)
        row = get(conn, jd_id)
        assert row["lead_status"] == status
        assert row["lead_decided_at"] is not None
        assert row["decline_reason"] is None


def test_back_to_pending_clears_the_decision():
    conn = make_db()
    jd_id = add_lead(conn)
    set_lead_status(conn, jd_id, "declined", reason="Salary too low")
    set_lead_status(conn, jd_id, "pending")

    row = get(conn, jd_id)
    assert row["lead_status"] == "pending"
    assert row["lead_decided_at"] is None
    assert row["decline_reason"] is None


def test_reconsidering_a_decline_clears_the_stale_reason():
    conn = make_db()
    jd_id = add_lead(conn)
    set_lead_status(conn, jd_id, "declined", reason="Salary too low")
    set_lead_status(conn, jd_id, "approved")
    assert get(conn, jd_id)["decline_reason"] is None


def test_retriage_overwrites_the_decision_date():
    conn = make_db()
    jd_id = add_lead(conn)
    set_lead_status(conn, jd_id, "approved", decided_at="2026-07-01T10:00:00")
    set_lead_status(conn, jd_id, "declined", reason="Filled internally",
                    decided_at="2026-07-20T10:00:00")
    assert get(conn, jd_id)["lead_decided_at"] == "2026-07-20T10:00:00"


def test_decline_stamps_category_alongside_the_reason():
    conn = make_db()
    jd_id = add_lead(conn)
    result = set_lead_status(conn, jd_id, "declined", category="role_type",
                             reason="Support track, not engineering")

    row = get(conn, jd_id)
    assert row["decline_category"] == "role_type"
    assert row["decline_reason"] == "Support track, not engineering"
    assert result["category"] == "role_type"


def test_category_is_optional_on_a_decline():
    """A decline with no category is uncategorized, not rejected — the report
    counts those and nudges, rather than the write path blocking."""
    conn = make_db()
    jd_id = add_lead(conn)
    set_lead_status(conn, jd_id, "declined", reason="Just no")
    assert get(conn, jd_id)["decline_category"] is None


def test_category_rejected_on_non_decline():
    conn = make_db()
    jd_id = add_lead(conn)
    with pytest.raises(ValueError, match="category"):
        set_lead_status(conn, jd_id, "approved", category="comp")


def test_unknown_category_rejected():
    conn = make_db()
    jd_id = add_lead(conn)
    with pytest.raises(ValueError, match="category must be one of"):
        set_lead_status(conn, jd_id, "declined", category="vibes")


def test_reconsidering_a_decline_clears_the_stale_category():
    conn = make_db()
    jd_id = add_lead(conn)
    set_lead_status(conn, jd_id, "declined", category="comp", reason="Below floor")
    set_lead_status(conn, jd_id, "approved")
    row = get(conn, jd_id)
    assert row["decline_category"] is None
    assert row["decline_reason"] is None


def test_adding_a_category_can_preserve_the_original_decision_date():
    """Backfilling a category onto an old decline must not restamp it as decided
    today — that would reorder every 'recently declined' view."""
    conn = make_db()
    jd_id = add_lead(conn)
    set_lead_status(conn, jd_id, "declined", reason="Below floor",
                    decided_at="2026-07-24T10:00:00")
    set_lead_status(conn, jd_id, "declined", category="comp", reason="Below floor",
                    decided_at="2026-07-24T10:00:00")

    row = get(conn, jd_id)
    assert row["lead_decided_at"] == "2026-07-24T10:00:00"
    assert row["decline_category"] == "comp"
    assert row["decline_reason"] == "Below floor"


def test_strategy_is_a_category_distinct_from_other():
    """'strategy' means the posting was fine and the seeker chose elsewhere;
    'other' means unclassified. Reports count them separately, so both must exist."""
    assert "strategy" in DECLINE_CATEGORIES
    assert "other" in DECLINE_CATEGORIES


def test_reason_rejected_on_non_decline():
    conn = make_db()
    jd_id = add_lead(conn)
    with pytest.raises(ValueError, match="reason"):
        set_lead_status(conn, jd_id, "approved", reason="wrong place for this")


def test_unknown_status_rejected():
    conn = make_db()
    jd_id = add_lead(conn)
    with pytest.raises(ValueError, match="status"):
        set_lead_status(conn, jd_id, "rejected")  # applications.status value, not a lead state


def test_missing_lead_raises():
    conn = make_db()
    with pytest.raises(LookupError):
        set_lead_status(conn, 9999, "declined", reason="nope")


def test_resolve_by_company_is_case_insensitive():
    conn = make_db()
    jd_id = add_lead(conn, company="Keyfactor")
    assert resolve_jd_id(conn, company="keyfactor") == jd_id


def test_resolve_by_company_needs_role_when_ambiguous():
    conn = make_db()
    add_lead(conn, company="Acme", role="QA Engineer")
    add_lead(conn, company="Acme", role="SDET")
    with pytest.raises(LookupError, match="narrow with --role"):
        resolve_jd_id(conn, company="Acme")
    assert resolve_jd_id(conn, company="Acme", role="SDET")
