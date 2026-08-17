"""import_secondary.insert_leads: the ingest path for leads pushed from a
secondary sourcer, used by both the `sync_leads` MCP tool and `/push-leads`.

This is the one write path where rows arrive from *another machine* (or another
person), so its dedupe and UPSERT behaviour is what keeps a re-push from either
duplicating a lead or blanking fields that the re-push happened not to carry.
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils import import_secondary as m

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


@pytest.fixture
def conn_factory(tmp_path, monkeypatch):
    """Point insert_leads at a throwaway DB, and neutralize register_file
    (which opens its own connection against the real DATA_DIR)."""
    path = tmp_path / "test.db"
    setup = sqlite3.connect(path)
    setup.executescript(SCHEMA_PATH.read_text())
    setup.commit()
    setup.close()

    def get_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c

    registered = []
    monkeypatch.setattr(m, "get_conn", get_conn)
    monkeypatch.setattr(m, "register_file", lambda **kw: registered.append(kw))
    get_conn.registered = registered
    return get_conn


def rows(conn_factory):
    conn = conn_factory()
    out = conn.execute("SELECT * FROM jds ORDER BY id").fetchall()
    conn.close()
    return out


class TestFirstUrl:
    def test_prefers_explicit_url(self):
        assert m._first_url({"url": "https://a.test", "source_urls": ["https://b.test"]}) \
            == "https://a.test"

    def test_falls_back_to_first_source_url(self):
        assert m._first_url({"source_urls": ["https://b.test", "https://c.test"]}) \
            == "https://b.test"

    def test_none_when_no_urls(self):
        assert m._first_url({}) is None
        assert m._first_url({"source_urls": []}) is None
        assert m._first_url({"url": ""}) is None


class TestInsertLeads:
    def test_inserts_a_new_lead_as_pending(self, conn_factory):
        imported, updated, skipped = m.insert_leads(
            [{"company": "Kuat Design Systems", "role": "Staff Engineer", "score": 80}],
            source="alex",
        )
        assert (imported, updated, skipped) == (1, 0, 0)
        (row,) = rows(conn_factory)
        assert row["company"] == "Kuat Design Systems"
        assert row["lead_status"] == "pending", "pushed leads must land untriaged"
        assert row["source"] == "alex", "the row records who pushed it"
        assert row["score"] == 80

    def test_skips_rows_missing_company_or_role(self, conn_factory):
        imported, updated, skipped = m.insert_leads([
            {"company": "", "role": "Engineer"},
            {"company": "Kuat", "role": "   "},
            {"role": "Engineer"},
        ])
        assert (imported, updated, skipped) == (0, 0, 3)
        assert rows(conn_factory) == []

    def test_repush_updates_instead_of_duplicating(self, conn_factory):
        lead = {"company": "Kuat", "role": "Staff Engineer", "score": 70}
        m.insert_leads([lead])
        imported, updated, skipped = m.insert_leads([{**lead, "score": 88}])

        assert (imported, updated, skipped) == (0, 1, 0)
        assert len(rows(conn_factory)) == 1, "dedupe key is (company, role)"
        assert rows(conn_factory)[0]["score"] == 88

    def test_partial_repush_does_not_null_out_prior_fields(self, conn_factory):
        """The COALESCE in the UPDATE is the point: a re-push carrying only a new
        score must not wipe the url and summary an earlier push supplied."""
        m.insert_leads([{
            "company": "Kuat", "role": "Staff Engineer",
            "url": "https://example.test/jobs/1", "summary": "Platform team",
            "salary_min": 180000,
        }])
        m.insert_leads([{"company": "Kuat", "role": "Staff Engineer", "score": 91}])

        row = rows(conn_factory)[0]
        assert row["score"] == 91
        assert row["url"] == "https://example.test/jobs/1"
        assert row["summary"] == "Platform team"
        assert row["salary_min"] == 180000

    def test_source_urls_used_when_no_explicit_url(self, conn_factory):
        m.insert_leads([{
            "company": "Kuat", "role": "Staff Engineer",
            "source_urls": ["https://board.test/1"],
        }])
        assert rows(conn_factory)[0]["url"] == "https://board.test/1"

    def test_required_skills_are_attached(self, conn_factory):
        m.insert_leads([{
            "company": "Kuat", "role": "Staff Engineer",
            "required_skills": ["python", "kubernetes"],
        }])
        conn = conn_factory()
        labels = [r["skill_label"] for r in
                  conn.execute("SELECT skill_label FROM jd_required_skills ORDER BY skill_label")]
        conn.close()
        assert labels == ["kubernetes", "python"]

    def test_file_path_registers_the_jd_file(self, conn_factory):
        m.insert_leads([{
            "company": "Kuat", "role": "Staff Engineer",
            "file_path": "/tmp/kuat.md", "source_urls": ["https://board.test/1"],
        }])
        (call,) = conn_factory.registered
        assert call["file_path"] == "/tmp/kuat.md"
        assert call["file_type"] == "jd"
        assert call["source"] == "sync"

    def test_no_file_registration_without_a_file_path(self, conn_factory):
        m.insert_leads([{"company": "Kuat", "role": "Staff Engineer"}])
        assert conn_factory.registered == []

    def test_empty_batch_is_a_no_op(self, conn_factory):
        assert m.insert_leads([]) == (0, 0, 0)
