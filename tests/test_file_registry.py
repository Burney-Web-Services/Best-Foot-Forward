"""
Tests for the file registry feature.

Covers:
  - classify_file()    — filename/path pattern → file_type
  - make_summary()     — file_type + context → summary string
  - parse_company_role() — path → (company, role_slug)
  - should_skip()      — files/dirs to exclude from sync
  - lookup_jd_id()     — path → matching jds.id
  - db.register_file() — insert and upsert into file_registry
"""

import sqlite3
import time
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_mod(tmp_path, monkeypatch):
    """db module wired to a temp SQLite file with tmp_path as the project root."""
    import best_foot_forward.db as mod
    monkeypatch.setattr(mod, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(mod, "_root", str(tmp_path))
    mod.init_db()
    return mod


@pytest.fixture
def mem_conn():
    """In-memory SQLite connection with the full BFF schema."""
    return make_mem_db()


# ── classify_file ─────────────────────────────────────────────────────────────

class TestClassifyFile:
    def _c(self, name, rel=None):
        from best_foot_forward.utils.sync_files import classify_file
        path = f"data/BestFootForward/assets/Acme/Engineer/{name}"
        return classify_file(path, rel or path)

    def test_resume(self):
        assert self._c("Leia Organa Resume - Acme Engineer.docx") == "resume"

    def test_resume_case_insensitive(self):
        assert self._c("leia organa resume - acme engineer.docx") == "resume"

    def test_cover_letter_with_space(self):
        assert self._c("Leia Organa Cover Letter - Acme Engineer.docx") == "letter"

    def test_coverletter_no_space(self):
        assert self._c("AcmeCoverLetter.docx") == "letter"

    def test_screen_prep(self):
        assert self._c("AcmeScreenPrep.docx") == "screen_prep"

    def test_interview_prep(self):
        assert self._c("AcmeInterviewPrep.docx") == "interview_prep"

    def test_prep_guide(self):
        assert self._c("AcmePrepGuide.docx") == "interview_prep"

    def test_job_desc_by_name(self):
        assert self._c("AcmeJobDesc.txt") == "jd"

    def test_odt_in_applications(self):
        path = "data/BestFootForward/assets/Acme/Engineer/AcmeJobDescription.odt"
        from best_foot_forward.utils.sync_files import classify_file
        assert classify_file(path, path) == "jd"

    def test_application_questions(self):
        assert self._c("AcmeApplicationQuestions.txt") == "questions"

    def test_notes_by_name(self):
        assert self._c("AcmeCompanyNotes.md") == "notes"

    def test_thank_you(self):
        assert self._c("AcmeThankYou.txt") == "notes"

    def test_md_in_applications_is_notes(self):
        assert self._c("SomeAnalysis.md") == "notes"

    def test_recording_by_extension(self):
        from best_foot_forward.utils.sync_files import classify_file
        path = "data/media/recordings/interview.wav"
        assert classify_file(path, path) == "recording"

    def test_recording_mp3(self):
        from best_foot_forward.utils.sync_files import classify_file
        path = "data/media/recordings/call.mp3"
        assert classify_file(path, path) == "recording"

    def test_transcript_in_media_transcripts(self):
        from best_foot_forward.utils.sync_files import classify_file
        path = "data/media/transcripts/interview_20260601_120000.md"
        assert classify_file(path, path) == "transcript"

    def test_research_subdir(self):
        from best_foot_forward.utils.sync_files import classify_file
        path = "data/BestFootForward/assets/Amazon/SDM/Research-and-Prep/lp-matrix.md"
        assert classify_file(path, path) == "research"

    def test_research_by_name(self):
        assert self._c("AcmeResearch.pdf") == "research"

    def test_misc_unknown(self):
        assert self._c("portfolio.zip") == "misc"

    def test_misc_image(self):
        assert self._c("availability.png") == "misc"


# ── make_summary ──────────────────────────────────────────────────────────────

class TestMakeSummary:
    def _s(self, file_type, name="file.docx", company=None, role=None):
        from best_foot_forward.utils.sync_files import make_summary
        return make_summary(file_type, name, company, role)

    def test_resume_with_company_and_role(self):
        assert self._s("resume", company="Acme", role="Senior Engineer") == \
            "Resume tailored for Acme – Senior Engineer"

    def test_letter_with_company_and_role(self):
        assert self._s("letter", company="Acme", role="Senior Engineer") == \
            "Cover letter for Acme – Senior Engineer"

    def test_jd_with_company_and_role(self):
        assert self._s("jd", company="Acme", role="Senior Engineer") == \
            "Job description: Acme – Senior Engineer"

    def test_questions(self):
        assert self._s("questions", company="Acme", role="Engineer") == \
            "Application questions for Acme – Engineer"

    def test_screen_prep(self):
        assert self._s("screen_prep", company="Acme", role="Engineer") == \
            "Screen prep for Acme – Engineer"

    def test_interview_prep(self):
        assert self._s("interview_prep", company="Acme", role="Engineer") == \
            "Interview prep for Acme – Engineer"

    def test_notes_uses_filename(self):
        result = self._s("notes", name="HasbroThankYou.txt", company="Hasbro", role="SWE")
        assert result == "Notes: HasbroThankYou.txt"

    def test_transcript_uses_filename(self):
        result = self._s("transcript", name="interview_20260601.md")
        assert result == "Transcript: interview_20260601.md"

    def test_recording_uses_filename(self):
        result = self._s("recording", name="call.wav")
        assert result == "Recording: call.wav"

    def test_misc_uses_filename(self):
        result = self._s("misc", name="portfolio.zip")
        assert result == "File: portfolio.zip"

    def test_company_only_no_role(self):
        result = self._s("resume", company="Acme", role=None)
        assert "Acme" in result

    def test_no_company_no_role_uses_filename(self):
        result = self._s("resume", name="my_resume.docx", company=None, role=None)
        assert "my_resume.docx" in result


# ── parse_company_role ────────────────────────────────────────────────────────

class TestParseCompanyRole:
    def _p(self, rel_path):
        from best_foot_forward.utils.sync_files import parse_company_role
        return parse_company_role(rel_path)

    def test_standard_path(self):
        company, role = self._p("data/BestFootForward/assets/Acme/Senior_Engineer/resume.docx")
        assert company == "Acme"
        assert role == "Senior Engineer"

    def test_underscores_in_role_become_spaces(self):
        _, role = self._p("data/BestFootForward/assets/Acme/Engineering_Manager_AI/file.docx")
        assert role == "Engineering Manager AI"

    def test_no_applications_segment(self):
        company, role = self._p("data/media/recordings/interview.wav")
        assert company is None
        assert role is None

    def test_file_directly_in_company_dir(self):
        # File is in the company dir itself — role slot points to the file, so role is None
        company, role = self._p("data/BestFootForward/assets/Acme/resume.docx")
        assert company == "Acme"
        assert role is None

    def test_multi_segment_company_name(self):
        company, role = self._p("data/BestFootForward/assets/CVS_Health/Senior_Manager/file.docx")
        assert company == "CVS_Health"

    def test_deep_research_subdir(self):
        company, role = self._p("data/BestFootForward/assets/Amazon/SDM/Research/lp-matrix.md")
        assert company == "Amazon"
        assert role == "SDM"


# ── should_skip ───────────────────────────────────────────────────────────────

class TestShouldSkip:
    def _skip(self, name):
        from best_foot_forward.utils.sync_files import should_skip
        return should_skip(name)

    def test_lock_file(self):
        assert self._skip(".~lock.resume.docx#") is True

    def test_ds_store(self):
        assert self._skip(".DS_Store") is True

    def test_pycache(self):
        assert self._skip("__pycache__") is True

    def test_hidden_file(self):
        assert self._skip(".hidden") is True

    def test_normal_docx(self):
        assert self._skip("Leia Organa Resume - Acme Engineer.docx") is False

    def test_normal_txt(self):
        assert self._skip("AcmeJobDesc.txt") is False

    def test_normal_md(self):
        assert self._skip("notes.md") is False


# ── lookup_jd_id ──────────────────────────────────────────────────────────────

class TestLookupJdId:
    def _lookup(self, conn, rel_path):
        from best_foot_forward.utils.sync_files import lookup_jd_id
        return lookup_jd_id(conn, rel_path)

    def test_matches_by_company_role_substring(self, mem_conn):
        mem_conn.execute(
            "INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)",
            ("Acme", "Senior Engineer", "data/BestFootForward/assets/Acme/Senior_Engineer/AcmeJobDesc.txt"),
        )
        mem_conn.commit()
        jd_id = mem_conn.execute("SELECT id FROM jds LIMIT 1").fetchone()[0]
        result = self._lookup(mem_conn, "data/BestFootForward/assets/Acme/Senior_Engineer/resume.docx")
        assert result == jd_id

    def test_company_only_fallback(self, mem_conn):
        mem_conn.execute(
            "INSERT INTO jds (company, role) VALUES (?, ?)",
            ("Banyan", "Head of Technology"),
        )
        mem_conn.commit()
        jd_id = mem_conn.execute("SELECT id FROM jds LIMIT 1").fetchone()[0]
        # No file_path in jds, but company dir name matches
        result = self._lookup(mem_conn, "data/BestFootForward/assets/Banyan/Head_of_Technology/resume.docx")
        assert result == jd_id

    def test_no_match_returns_none(self, mem_conn):
        result = self._lookup(mem_conn, "data/BestFootForward/assets/NoSuchCo/Engineer/file.docx")
        assert result is None

    def test_media_path_returns_none(self, mem_conn):
        result = self._lookup(mem_conn, "data/media/transcripts/interview.md")
        assert result is None

    def test_picks_correct_jd_among_multiple(self, mem_conn):
        mem_conn.execute(
            "INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)",
            ("Acme", "Engineer", "data/BestFootForward/assets/Acme/Engineer/AcmeJobDesc.txt"),
        )
        mem_conn.execute(
            "INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)",
            ("Banyan", "CTO", "data/BestFootForward/assets/Banyan/CTO/BanyanJobDesc.txt"),
        )
        mem_conn.commit()
        banyan_id = mem_conn.execute("SELECT id FROM jds WHERE company='Banyan'").fetchone()[0]
        result = self._lookup(mem_conn, "data/BestFootForward/assets/Banyan/CTO/resume.docx")
        assert result == banyan_id


# ── register_file ─────────────────────────────────────────────────────────────

class TestRegisterFile:
    def test_inserts_record(self, db_mod, tmp_path):
        f = tmp_path / "data" / "applications" / "Acme" / "Engineer" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"fake docx content")

        row_id = db_mod.register_file(str(f), "resume", "Resume tailored for Acme – Engineer")

        assert isinstance(row_id, int)
        conn = db_mod.get_conn()
        row = conn.execute("SELECT * FROM file_registry WHERE id = ?", (row_id,)).fetchone()
        assert row["file_type"] == "resume"
        assert row["summary"] == "Resume tailored for Acme – Engineer"
        assert row["source"] == "auto"

    def test_stores_relative_path(self, db_mod, tmp_path):
        f = tmp_path / "data" / "applications" / "Acme" / "Engineer" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")

        db_mod.register_file(str(f), "resume", "Resume for Acme")

        conn = db_mod.get_conn()
        row = conn.execute("SELECT file_path FROM file_registry LIMIT 1").fetchone()
        # Should be relative to tmp_path (_root), not an absolute path
        assert not row["file_path"].startswith("/")

    def test_stores_file_size(self, db_mod, tmp_path):
        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"A" * 1234)

        db_mod.register_file(str(f), "resume", "Test resume")

        conn = db_mod.get_conn()
        row = conn.execute("SELECT file_size FROM file_registry LIMIT 1").fetchone()
        assert row["file_size"] == 1234

    def test_stores_file_mtime(self, db_mod, tmp_path):
        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"content")

        db_mod.register_file(str(f), "resume", "Test resume")

        conn = db_mod.get_conn()
        row = conn.execute("SELECT file_mtime FROM file_registry LIMIT 1").fetchone()
        assert row["file_mtime"] is not None

    def test_missing_file_stores_null_size_and_mtime(self, db_mod, tmp_path):
        db_mod.register_file(
            str(tmp_path / "data" / "nonexistent.docx"),
            "resume", "Ghost file",
        )

        conn = db_mod.get_conn()
        row = conn.execute("SELECT file_size, file_mtime FROM file_registry LIMIT 1").fetchone()
        assert row["file_size"] is None
        assert row["file_mtime"] is None

    def test_upsert_does_not_reset_registered_at(self, db_mod, tmp_path):
        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"v1")

        db_mod.register_file(str(f), "resume", "First registration")

        conn = db_mod.get_conn()
        first_ts = conn.execute("SELECT registered_at FROM file_registry LIMIT 1").fetchone()[0]

        time.sleep(1.1)  # ensure datetime('now') would differ
        f.write_bytes(b"v2 updated content")
        db_mod.register_file(str(f), "resume", "Second registration")

        second_ts = conn.execute("SELECT registered_at FROM file_registry LIMIT 1").fetchone()[0]
        assert first_ts == second_ts

    def test_upsert_updates_summary(self, db_mod, tmp_path):
        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"content")

        db_mod.register_file(str(f), "resume", "Original summary")
        db_mod.register_file(str(f), "resume", "Updated summary")

        conn = db_mod.get_conn()
        row = conn.execute("SELECT summary FROM file_registry LIMIT 1").fetchone()
        assert row["summary"] == "Updated summary"

    def test_upsert_updates_file_size(self, db_mod, tmp_path):
        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"short")

        db_mod.register_file(str(f), "resume", "Resume")

        f.write_bytes(b"much longer content now")
        db_mod.register_file(str(f), "resume", "Resume")

        conn = db_mod.get_conn()
        row = conn.execute("SELECT file_size FROM file_registry LIMIT 1").fetchone()
        assert row["file_size"] == len(b"much longer content now")

    def test_stores_jd_id(self, db_mod, tmp_path):
        conn = db_mod.get_conn()
        conn.execute("INSERT INTO jds (company, role) VALUES ('Acme', 'Engineer')")
        conn.commit()
        jd_id = conn.execute("SELECT id FROM jds LIMIT 1").fetchone()[0]

        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
        db_mod.register_file(str(f), "resume", "Resume for Acme", jd_id=jd_id)

        row = conn.execute("SELECT jd_id FROM file_registry LIMIT 1").fetchone()
        assert row["jd_id"] == jd_id

    def test_stores_application_id(self, db_mod, tmp_path):
        conn = db_mod.get_conn()
        conn.execute("INSERT INTO applications (created_at, resume_summary) VALUES ('2026-01-01', '')")
        conn.commit()
        app_id = conn.execute("SELECT id FROM applications LIMIT 1").fetchone()[0]

        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
        db_mod.register_file(str(f), "resume", "Resume", application_id=app_id)

        row = conn.execute("SELECT application_id FROM file_registry LIMIT 1").fetchone()
        assert row["application_id"] == app_id

    def test_custom_source_label(self, db_mod, tmp_path):
        f = tmp_path / "data" / "resume.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
        db_mod.register_file(str(f), "resume", "Resume", source="sync")

        conn = db_mod.get_conn()
        row = conn.execute("SELECT source FROM file_registry LIMIT 1").fetchone()
        assert row["source"] == "sync"

    def test_returns_row_id(self, db_mod, tmp_path):
        f = tmp_path / "data" / "a.docx"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
        row_id = db_mod.register_file(str(f), "resume", "A")
        assert isinstance(row_id, int)
        assert row_id > 0
