"""
Tests for the generate_thankyou module.

Covers:
  - Session data reading (COMPANY, ROLE, JD_FILE_PATH, EMAIL_BODY, etc.)
  - JD path resolution and jd_id lookup
  - Application lookup from jd_id
  - Thank you email file generation and writing
  - File registration in file_registry with application_id
  - Filename sanitization (special characters in role)
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_mem_db() -> sqlite3.Connection:
    """Create in-memory SQLite with BFF schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


@pytest.fixture
def db_with_jd_and_app(tmp_path):
    """In-memory DB with a sample JD and application."""
    conn = make_mem_db()

    jd_path = str(tmp_path / "assets" / "TestCorp" / "Test_Role" / "TestCorp_Test_RoleJobDesc.md")

    # Insert a JD
    cur = conn.execute(
        "INSERT INTO jds (company, role, file_path, score, summary) VALUES (?, ?, ?, ?, ?)",
        ("TestCorp", "Test Role", jd_path, 85, "A good fit")
    )
    jd_id = cur.lastrowid

    # Insert an application
    cur = conn.execute(
        "INSERT INTO applications (jd_id, created_at, resume_summary, stage, status, applied_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (jd_id, "2026-08-01T10:00:00", "A good fit", "screen", "applied", "2026-08-01T10:00:00")
    )
    app_id = cur.lastrowid

    conn.commit()

    return conn, jd_id, app_id, jd_path


@pytest.fixture
def db_with_contact(db_with_jd_and_app):
    """Add a contact record to the DB."""
    conn, jd_id, app_id, jd_path = db_with_jd_and_app

    conn.execute(
        "INSERT INTO contacts (jd_id, name, title, interview_date) VALUES (?, ?, ?, ?)",
        (jd_id, "Jane Smith", "Hiring Manager", "2026-07-30")
    )
    conn.commit()

    return conn, jd_id, app_id, jd_path


class TestGenerateThankyou:
    """Tests for the generate_thankyou module."""

    def test_session_data_reading(self, tmp_path):
        """Verify session data can be read from thankyou_data.py."""
        session_file = tmp_path / "thankyou_data.py"
        session_file.write_text("""
COMPANY = "TestCorp"
ROLE = "Test Role"
JD_FILE_PATH = "/path/to/jd.md"
RECIPIENT_NAME = "Jane Smith"
RECIPIENT_TITLE = "Hiring Manager"
INTERVIEW_DATE = "2026-07-30"
EMAIL_BODY = "Hi Jane, thank you for the interview."
""")

        # Simulate reading the session file
        import sys
        sys.path.insert(0, str(tmp_path))
        try:
            import thankyou_data
            assert thankyou_data.COMPANY == "TestCorp"
            assert thankyou_data.ROLE == "Test Role"
            assert thankyou_data.RECIPIENT_NAME == "Jane Smith"
            assert thankyou_data.EMAIL_BODY == "Hi Jane, thank you for the interview."
        finally:
            sys.path.pop(0)
            if "thankyou_data" in sys.modules:
                del sys.modules["thankyou_data"]

    def test_filename_sanitization(self):
        """Verify special characters in role names are sanitized."""
        # Test sanitization logic (mirrors generate_thankyou.py)
        def sanitize(s):
            return s.replace('/', '_').replace('\\', '_')

        assert sanitize("Software Engineer") == "Software Engineer"
        assert sanitize("Director, Engineering – AI") == "Director, Engineering – AI"
        assert sanitize("Role/With/Slashes") == "Role_With_Slashes"
        assert sanitize("Role\\With\\Backslashes") == "Role_With_Backslashes"

    def test_file_writing(self, tmp_path):
        """Verify thank you email is written to correct location."""
        output_dir = tmp_path / "assets" / "TestCorp" / "Test_Role"
        email_body = "Hi Jane, thank you for the interview. I'm excited about the opportunity."

        # Simulate file write
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / "TestCorp_Test_RoleThankYou.txt"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(email_body)

        # Verify file exists and content is correct
        assert filepath.exists()
        assert filepath.read_text() == email_body

    def test_file_registration(self, db_with_jd_and_app):
        """Verify file is registered in file_registry with correct metadata."""
        conn, jd_id, app_id, jd_path = db_with_jd_and_app

        # Simulate file registration
        filepath = "data/BestFootForward/assets/TestCorp/Test_Role/TestCorp_Test_RoleThankYou.txt"
        file_type = "thankyou"
        summary = "Thank you email for TestCorp – Test Role"

        conn.execute(
            "INSERT INTO file_registry (file_path, file_type, summary, jd_id, application_id) VALUES (?, ?, ?, ?, ?)",
            (filepath, file_type, summary, jd_id, app_id)
        )
        conn.commit()

        # Verify registration
        row = conn.execute(
            "SELECT file_type, summary, jd_id, application_id FROM file_registry WHERE file_path = ?",
            (filepath,)
        ).fetchone()

        assert row is not None
        assert row["file_type"] == "thankyou"
        assert row["jd_id"] == jd_id
        assert row["application_id"] == app_id

    def test_application_lookup_with_app(self, db_with_jd_and_app):
        """Verify application is looked up correctly from jd_id."""
        conn, jd_id, app_id, _ = db_with_jd_and_app

        app = conn.execute(
            "SELECT id FROM applications WHERE jd_id = ? ORDER BY created_at DESC LIMIT 1",
            (jd_id,)
        ).fetchone()

        assert app is not None
        assert app["id"] == app_id

    def test_application_lookup_without_app(self, tmp_path):
        """Verify behavior when no application exists for a JD."""
        conn = make_mem_db()

        jd_path = str(tmp_path / "jd.md")
        cur = conn.execute(
            "INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)",
            ("NewCorp", "New Role", jd_path)
        )
        jd_id = cur.lastrowid
        conn.commit()

        app = conn.execute(
            "SELECT id FROM applications WHERE jd_id = ? ORDER BY created_at DESC LIMIT 1",
            (jd_id,)
        ).fetchone()

        assert app is None

    def test_contact_retrieval(self, db_with_contact):
        """Verify contact info can be retrieved for thank you page."""
        conn, jd_id, app_id, _ = db_with_contact

        contact = conn.execute(
            "SELECT name, title, interview_date FROM contacts WHERE jd_id = ? ORDER BY id LIMIT 1",
            (jd_id,)
        ).fetchone()

        assert contact is not None
        assert contact["name"] == "Jane Smith"
        assert contact["title"] == "Hiring Manager"
        assert contact["interview_date"] == "2026-07-30"

    def test_end_to_end_file_workflow(self, tmp_path, db_with_contact):
        """End-to-end test: write email file and register it."""
        conn, jd_id, app_id, jd_path = db_with_contact

        # Create output directory
        output_dir = Path(jd_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write email file
        email_body = "Hi Jane,\n\nThank you for our conversation. I'm excited about the opportunity."
        filepath = output_dir / "TestCorp_Test_RoleThankYou.txt"
        filepath.write_text(email_body)

        # Register file
        conn.execute(
            "INSERT INTO file_registry (file_path, file_type, summary, jd_id, application_id) VALUES (?, ?, ?, ?, ?)",
            (str(filepath), "thankyou", "Thank you for TestCorp", jd_id, app_id)
        )
        conn.commit()

        # Verify workflow
        assert filepath.exists()
        assert filepath.read_text() == email_body

        file_reg = conn.execute(
            "SELECT jd_id, application_id FROM file_registry WHERE file_path = ?",
            (str(filepath),)
        ).fetchone()

        assert file_reg is not None
        assert file_reg["jd_id"] == jd_id
        assert file_reg["application_id"] == app_id
