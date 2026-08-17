"""export_application_summaries.py: writes data/application_summaries.json (the
low-context cache resume-tailor reads) and refreshes the "Applications complete: N"
line that the session greeting is built from.

Both outputs are consumed by something that never re-derives them, so a silent
failure here shows up as a stale greeting or a tailoring suggestion built on old
data rather than as an error.

Every test pins DATA_DIR and get_conn at a temp directory. Nothing here may touch
the developer's real database or real project_status.md.
"""
import json
import sqlite3
import types
from pathlib import Path

import pytest

from best_foot_forward.utils import export_application_summaries as m

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    db_path = d / "best_foot_forward.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()

    def get_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(m, "DATA_DIR", str(d))
    monkeypatch.setattr(m, "get_conn", get_conn)
    return types.SimpleNamespace(path=d, get_conn=get_conn)


def add_application(data_dir, *, company="Kuat Design Systems", role="Staff Engineer",
                    status="applied", applied_at="2026-07-01", concluded_at=None,
                    score=80, tailoring_notes=None, jd_id=1, app_id=1):
    conn = data_dir.get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO jds (id, company, role, file_path, score, output_dir) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (jd_id, company, role, f"/tmp/jd{jd_id}.md", score, f"/tmp/out{jd_id}"),
    )
    conn.execute(
        "INSERT INTO applications (id, jd_id, status, applied_at, concluded_at, "
        "created_at, resume_summary, tailoring_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (app_id, jd_id, status, applied_at, concluded_at, "2026-07-01", "s", tailoring_notes),
    )
    conn.commit()
    conn.close()


def read_output(data_dir):
    return json.loads((data_dir.path / "application_summaries.json").read_text())


class TestExportApplications:
    def test_writes_the_cache_file_even_when_empty(self, data_dir):
        m.export_applications()
        out = read_output(data_dir)
        assert out["applications"] == []
        assert "Edit via SQLite" in out["_notes"], "the file must warn it is generated"

    def test_exports_core_fields(self, data_dir):
        add_application(data_dir)
        m.export_applications()
        (app,) = read_output(data_dir)["applications"]
        assert app["company"] == "Kuat Design Systems"
        assert app["role"] == "Staff Engineer"
        assert app["status"] == "applied"
        assert app["score"] == 80
        assert app["file_path"] == "/tmp/out1", "file_path is the materials directory"

    def test_computes_days_to_rejection(self, data_dir):
        add_application(data_dir, status="rejected",
                        applied_at="2026-07-01", concluded_at="2026-07-22")
        m.export_applications()
        (app,) = read_output(data_dir)["applications"]
        assert app["rejected_at"] == "2026-07-22"
        assert app["days_to_rejection"] == 21

    def test_unparseable_dates_do_not_raise(self, data_dir):
        add_application(data_dir, status="rejected",
                        applied_at="whenever", concluded_at="2026-07-22")
        m.export_applications()
        (app,) = read_output(data_dir)["applications"]
        assert "days_to_rejection" not in app

    def test_rejected_without_conclusion_has_no_rejection_fields(self, data_dir):
        add_application(data_dir, status="rejected", concluded_at=None)
        m.export_applications()
        (app,) = read_output(data_dir)["applications"]
        assert "rejected_at" not in app

    def test_tailoring_notes_included_only_when_present(self, data_dir):
        add_application(data_dir, app_id=1, jd_id=1, tailoring_notes=None)
        add_application(data_dir, app_id=2, jd_id=2, company="Chandrila Data Collective",
                        tailoring_notes="Led with platform reliability")
        m.export_applications()
        apps = {a["app_id"]: a for a in read_output(data_dir)["applications"]}
        assert "tailoring_notes" not in apps[1]
        assert apps[2]["tailoring_notes"] == "Led with platform reliability"

    def test_leads_without_an_application_are_excluded(self, data_dir):
        """The export joins applications to jds — an evaluated-but-unapplied lead
        is not an application and must not appear."""
        conn = data_dir.get_conn()
        conn.execute("INSERT INTO jds (id, company, role, file_path) "
                     "VALUES (99, 'Nar Shaddaa Exchange Group', 'Engineer', '/tmp/x.md')")
        conn.commit()
        conn.close()
        m.export_applications()
        assert read_output(data_dir)["applications"] == []


class TestRefreshStatusGreeting:
    def test_missing_memory_file_is_reported_not_fatal(self, data_dir, capsys):
        m.refresh_status_greeting()
        assert "skipping greeting refresh" in capsys.readouterr().out

    def test_updates_the_count_line_in_the_local_fallback(self, data_dir, capsys):
        # The project-relative memory/ fallback: dirname(DATA_DIR)/memory/.
        mem = data_dir.path.parent / "memory"
        mem.mkdir()
        status = mem / "project_status.md"
        status.write_text("# Status\n\nApplications complete: 3\n\nLast: Somewhere\n")

        add_application(data_dir, app_id=1, jd_id=1)
        add_application(data_dir, app_id=2, jd_id=2, company="Chandrila Data Collective")
        m.refresh_status_greeting()

        assert "Applications complete: 2" in status.read_text()
        assert "Last: Somewhere" in status.read_text(), "only the count line may change"

    def test_applications_never_submitted_are_not_counted(self, data_dir):
        mem = data_dir.path.parent / "memory"
        mem.mkdir()
        status = mem / "project_status.md"
        status.write_text("Applications complete: 9\n")

        add_application(data_dir, app_id=1, jd_id=1, applied_at=None)
        m.refresh_status_greeting()
        assert "Applications complete: 0" in status.read_text()

    def test_no_count_line_is_left_alone(self, data_dir):
        mem = data_dir.path.parent / "memory"
        mem.mkdir()
        status = mem / "project_status.md"
        status.write_text("# Status\n\nnothing to substitute here\n")
        m.refresh_status_greeting()
        assert status.read_text() == "# Status\n\nnothing to substitute here\n"
