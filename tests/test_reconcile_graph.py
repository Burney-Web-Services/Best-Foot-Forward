"""reconcile_graph.py: the pages -> DB direction of the Logseq sync.

export_graph (DB -> pages) has had tests since the migration; this side did not,
even though it is the direction that *writes to the database* from hand-edited
files. The properties it reconciles include lead_status, decline_reason, score,
salary and application status/stage — the fields every report and MCP tool reads.

The design commitments worth pinning down, from the module docstring:
  - column-level UPDATE keyed on the id echoed in the page, never drop-and-rebuild
    (a rebuild would orphan application_bullets / file_registry FKs)
  - idempotent
  - --dry-run reports the diff without writing
  - a date-only page value must not truncate a stored timestamp on a no-op
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils import reconcile_graph as m

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute(
        "INSERT INTO jds (id, company, role, file_path, lead_status, score) "
        "VALUES (1, 'Kuat Design Systems', 'Staff Engineer', '/tmp/jd.md', 'pending', 70)"
    )
    conn.execute(
        "INSERT INTO applications "
        "(id, jd_id, status, stage, applied_at, created_at, resume_summary) "
        "VALUES (10, 1, 'applied', 'application', '2026-07-01T09:30:00', "
        "'2026-07-01T09:30:00', 'summary')"
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def pages(tmp_path, monkeypatch):
    d = tmp_path / "pages"
    d.mkdir()
    monkeypatch.setattr(m, "PAGES", str(d))
    return d


def write_page(pages, filename, props):
    body = "\n".join(f"{k}:: {v}" for k, v in props.items())
    (pages / filename).write_text(body + "\n\n- ## Notes\n")


def fetch(db_path, table, id_val):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (id_val,)).fetchone()
    conn.close()
    return row


class TestClean:
    def test_strips_page_links_and_tags(self):
        assert m._clean("[[Kuat Design Systems]]", str) == "Kuat Design Systems"
        assert m._clean("#declined", str) == "declined"

    def test_empty_and_dash_become_none(self):
        assert m._clean("", str) is None
        assert m._clean("   ", str) is None
        assert m._clean("-", str) is None
        assert m._clean(None, str) is None

    def test_slash_and_dash_dates_both_normalize(self):
        # Pages render dates as [[YYYY/MM/DD]] to match the graph's journal format.
        assert m._clean("[[2026/07/16]]", "date") == "2026-07-16"
        assert m._clean("2026-07-16", "date") == "2026-07-16"

    def test_unparseable_date_is_none_not_garbage(self):
        assert m._clean("sometime in July", "date") is None

    def test_bad_int_falls_back_to_the_raw_string(self):
        # Deliberate: a typo in a page shouldn't crash the whole reconcile pass.
        assert m._clean("not-a-number", int) == "not-a-number"
        assert m._clean("85", int) == 85


class TestReconcile:
    def test_pulls_lead_edits_back_into_jds(self, db, pages):
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-jd-id": "1",
            "lead-status": "#declined",
            "decline-reason": "Comp band was below my floor",
            "decline-category": "comp",
            "score": "82",
        })
        m.reconcile(str(db))
        row = fetch(db, "jds", 1)
        assert row["lead_status"] == "declined"
        assert row["decline_reason"] == "Comp band was below my floor"
        assert row["decline_category"] == "comp"
        assert row["score"] == 82

    def test_pulls_application_edits_back(self, db, pages):
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-application-id": "10",
            "status": "interviewing",
            "stage": "interview_1",
            "concluded": "[[2026/08/02]]",
        })
        m.reconcile(str(db))
        row = fetch(db, "applications", 10)
        assert row["status"] == "interviewing"
        assert row["stage"] == "interview_1"
        assert row["concluded_at"] == "2026-08-02"

    def test_lead_pages_reconcile_the_same_jds_fields(self, db, pages):
        write_page(pages, "Kuat___Staff___Lead.md", {
            "bff-jd-id": "1",
            "lead-status": "approved",
            "url": "https://example.test/jobs/1",
        })
        m.reconcile(str(db))
        row = fetch(db, "jds", 1)
        assert row["lead_status"] == "approved"
        assert row["url"] == "https://example.test/jobs/1"

    def test_dry_run_reports_without_writing(self, db, pages):
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-jd-id": "1", "lead-status": "declined",
        })
        changes = m.reconcile(str(db), dry_run=True)
        assert changes, "dry-run should still report the diff it would apply"
        assert fetch(db, "jds", 1)["lead_status"] == "pending"

    def test_is_idempotent(self, db, pages):
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-jd-id": "1", "lead-status": "declined",
        })
        first = m.reconcile(str(db))
        second = m.reconcile(str(db))
        assert first, "first pass should change something"
        assert second == [], "a second pass over unchanged pages must be a no-op"

    def test_date_only_page_value_does_not_truncate_a_stored_timestamp(self, db, pages):
        """applied_at holds a full timestamp; the page carries a date. Reconciling
        the same calendar day must leave the time component alone."""
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-application-id": "10", "applied": "[[2026/07/01]]",
        })
        changes = m.reconcile(str(db))
        assert changes == [], "same calendar date should not register as a change"
        assert fetch(db, "applications", 10)["applied_at"] == "2026-07-01T09:30:00"

    def test_unknown_id_is_ignored_not_inserted(self, db, pages):
        write_page(pages, "Ghost___Role___Application.md", {
            "bff-jd-id": "9999", "lead-status": "declined",
        })
        m.reconcile(str(db))
        conn = sqlite3.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0] == 1
        conn.close()

    def test_non_numeric_id_is_skipped(self, db, pages):
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-jd-id": "", "lead-status": "declined",
        })
        m.reconcile(str(db))
        assert fetch(db, "jds", 1)["lead_status"] == "pending"

    def test_only_listed_properties_are_reconciled(self, db, pages):
        """Prose and unmapped properties stay markdown-only — the module reconciles
        structured fields, not the page body."""
        write_page(pages, "Kuat___Staff___Application.md", {
            "bff-jd-id": "1", "company": "[[Someone Else]]", "role": "Totally Different",
        })
        m.reconcile(str(db))
        row = fetch(db, "jds", 1)
        assert row["company"] == "Kuat Design Systems"
        assert row["role"] == "Staff Engineer"
