"""Offer transitions and the withdraw/not-pursue closeout: applications.stage,
status, concluded_at, and offer_* move together, only through record_offer /
close_applications.
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils.record_offer import (
    close_applications,
    record_offer,
    resolve_application_id,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def add_application(conn, company="Acme", role="Engineer", stage="final_interview_complete",
                    status="applied", applied_at="2026-06-29", **cols):
    conn.execute("INSERT INTO jds (company, role) VALUES (?, ?)", (company, role))
    jd_id = conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()["id"]
    fields = {"jd_id": jd_id, "created_at": "2026-06-29T00:00:00", "resume_summary": "",
              "status": status, "stage": stage, "applied_at": applied_at, **cols}
    conn.execute(
        f"INSERT INTO applications ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
        list(fields.values()),
    )
    conn.commit()
    return conn.execute("SELECT id FROM applications ORDER BY id DESC LIMIT 1").fetchone()["id"]


def get(conn, app_id):
    return conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()


def test_schema_has_offer_columns():
    conn = make_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(applications)")}
    assert {"offer_received_at", "offer_salary", "offer_total_comp", "offer_currency",
            "offer_title", "offer_start_date", "offer_deadline", "offer_notes"} <= cols


class TestRecordOffer:
    def test_received_sets_stage_and_status_not_concluded(self):
        conn = make_db()
        app_id = add_application(conn)
        result = record_offer(conn, app_id, "received", salary=250000, deadline="2026-08-20")
        row = get(conn, app_id)
        assert row["stage"] == "offer_received"
        assert row["status"] == "offer"
        assert row["concluded_at"] is None
        assert row["offer_salary"] == 250000
        assert row["offer_deadline"] == "2026-08-20"
        assert result["concluded_at"] is None

    def test_accepted_concludes(self):
        conn = make_db()
        app_id = add_application(conn)
        record_offer(conn, app_id, "accepted", salary=250000, decided_at="2026-08-07")
        row = get(conn, app_id)
        assert row["stage"] == "offer_accepted"
        assert row["status"] == "accepted"
        assert row["concluded_at"] == "2026-08-07"

    def test_declined_sets_offer_declined_and_concludes(self):
        conn = make_db()
        app_id = add_application(conn)
        record_offer(conn, app_id, "declined", decided_at="2026-08-10")
        row = get(conn, app_id)
        assert row["stage"] == "declined_offer"
        assert row["status"] == "offer_declined"
        assert row["concluded_at"] == "2026-08-10"

    def test_received_then_accepted_preserves_terms(self):
        """The COALESCE behavior: accepting after receiving must not blank
        terms already captured, and should let the accept call add new ones."""
        conn = make_db()
        app_id = add_application(conn)
        record_offer(conn, app_id, "received", salary=240000, currency="USD",
                     title="Senior Manager", deadline="2026-08-20")
        record_offer(conn, app_id, "accepted", total_comp=300000, start_date="2026-09-08",
                     decided_at="2026-08-07")
        row = get(conn, app_id)
        assert row["offer_salary"] == 240000          # preserved from the received call
        assert row["offer_currency"] == "USD"          # preserved
        assert row["offer_title"] == "Senior Manager"  # preserved
        assert row["offer_deadline"] == "2026-08-20"    # preserved
        assert row["offer_total_comp"] == 300000        # added by the accept call
        assert row["offer_start_date"] == "2026-09-08"  # added by the accept call
        assert row["stage"] == "offer_accepted"
        assert row["status"] == "accepted"

    def test_notes_append_not_overwrite(self):
        conn = make_db()
        app_id = add_application(conn)
        record_offer(conn, app_id, "received", notes="Verbal offer over the phone")
        record_offer(conn, app_id, "accepted", notes="Signed offer letter received")
        row = get(conn, app_id)
        assert "Verbal offer over the phone" in row["offer_notes"]
        assert "Signed offer letter received" in row["offer_notes"]

    def test_offer_received_at_defaults_once(self):
        conn = make_db()
        app_id = add_application(conn)
        record_offer(conn, app_id, "received")
        first = get(conn, app_id)["offer_received_at"]
        assert first is not None
        record_offer(conn, app_id, "accepted", decided_at="2026-08-07")
        assert get(conn, app_id)["offer_received_at"] == first  # not clobbered

    def test_unknown_state_raises(self):
        conn = make_db()
        app_id = add_application(conn)
        with pytest.raises(ValueError):
            record_offer(conn, app_id, "maybe")

    def test_missing_application_raises(self):
        conn = make_db()
        with pytest.raises(LookupError):
            record_offer(conn, 9999, "accepted")


class TestCloseApplications:
    def test_closes_as_withdrawn(self):
        conn = make_db()
        app_id = add_application(conn, company="Vector", stage="interview_2")
        results = close_applications(conn, [app_id], "withdrawn", reason="Accepted elsewhere")
        row = get(conn, app_id)
        assert row["status"] == "withdrawn"
        assert row["concluded_at"] is not None
        assert "Accepted elsewhere" in row["notes"]
        assert results == [{"id": app_id, "company": "Vector", "role": "Engineer", "status": "withdrawn"}]

    def test_closes_as_not_pursued(self):
        conn = make_db()
        app_id = add_application(conn, company="Peloton")
        close_applications(conn, [app_id], "not_pursued")
        assert get(conn, app_id)["status"] == "not_pursued"

    def test_skips_already_concluded(self):
        """Re-run safety: a row already concluded (e.g. rejected) is left alone,
        not silently overwritten with a different terminal status."""
        conn = make_db()
        app_id = add_application(conn, status="rejected", concluded_at="2026-07-01")
        results = close_applications(conn, [app_id], "withdrawn")
        row = get(conn, app_id)
        assert row["status"] == "rejected"          # unchanged
        assert row["concluded_at"] == "2026-07-01"  # unchanged
        assert results == []

    def test_rejects_bad_status(self):
        conn = make_db()
        app_id = add_application(conn)
        with pytest.raises(ValueError):
            close_applications(conn, [app_id], "ghosted")

    def test_requires_explicit_ids(self):
        conn = make_db()
        with pytest.raises(ValueError):
            close_applications(conn, [], "withdrawn")

    def test_missing_id_raises(self):
        conn = make_db()
        with pytest.raises(LookupError):
            close_applications(conn, [9999], "withdrawn")

    def test_closes_orphaned_application_with_no_jd(self):
        """An application with jd_id NULL (its jds row was deleted) is still a
        real row the caller explicitly named — must not raise LookupError as
        if the id didn't exist."""
        conn = make_db()
        conn.execute(
            "INSERT INTO applications (jd_id, created_at, resume_summary, status, applied_at) "
            "VALUES (NULL, '2026-05-20T00:00:00', '', 'applied', '2026-05-20')"
        )
        conn.commit()
        app_id = conn.execute("SELECT id FROM applications ORDER BY id DESC LIMIT 1").fetchone()["id"]
        results = close_applications(conn, [app_id], "not_pursued")
        assert results == [{"id": app_id, "company": None, "role": None, "status": "not_pursued"}]
        assert get(conn, app_id)["status"] == "not_pursued"


class TestResolveApplicationId:
    def test_by_application_id_passthrough(self):
        conn = make_db()
        app_id = add_application(conn)
        assert resolve_application_id(conn, application_id=app_id) == app_id

    def test_by_jd_id(self):
        conn = make_db()
        app_id = add_application(conn)
        jd_id = get(conn, app_id)["jd_id"]
        assert resolve_application_id(conn, jd_id=jd_id) == app_id

    def test_by_company(self):
        conn = make_db()
        app_id = add_application(conn, company="Kuat Design Systems")
        assert resolve_application_id(conn, company="Kuat Design Systems") == app_id

    def test_multi_match_raises(self):
        conn = make_db()
        add_application(conn, company="Acme", role="Engineer")
        add_application(conn, company="Acme", role="Manager")
        with pytest.raises(LookupError):
            resolve_application_id(conn, company="Acme")

    def test_multi_match_disambiguated_by_role(self):
        conn = make_db()
        add_application(conn, company="Acme", role="Engineer")
        app_id2 = add_application(conn, company="Acme", role="Manager")
        assert resolve_application_id(conn, company="Acme", role="Manager") == app_id2

    def test_no_match_raises(self):
        conn = make_db()
        with pytest.raises(LookupError):
            resolve_application_id(conn, company="Nonexistent")
