"""
Verify that schema.sql initialises correctly against an in-memory SQLite DB.
These tests are the canary for schema regressions — no data/ directory needed.
"""
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"

EXPECTED_TABLES = [
    "contact", "education", "employers", "bullets", "bullet_tracks", "bullet_themes",
    "skills", "skill_tracks", "skill_themes", "jds", "jd_required_skills",
    "applications", "contacts", "stories", "story_themes", "story_bullets",
    "story_interview_use", "assessments", "file_registry",
]


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def test_schema_file_exists():
    assert SCHEMA_PATH.exists(), f"schema.sql not found at {SCHEMA_PATH}"


def test_all_tables_created():
    conn = make_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in EXPECTED_TABLES:
        assert t in tables, f"Missing table: {t}"


def test_foreign_keys_enforced():
    conn = make_db()
    conn.execute("INSERT INTO employers (name, location, start_date, sort_order) VALUES (?, ?, ?, ?)",
                 ("Acme", "Boston, MA", "01/2020", 1))
    conn.commit()
    employer_id = conn.execute("SELECT id FROM employers WHERE name='Acme'").fetchone()[0]
    conn.execute("INSERT INTO bullets (employer_id, role, text) VALUES (?, ?, ?)",
                 (employer_id, "Engineer", "Built things"))
    conn.commit()
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO bullets (employer_id, role, text) VALUES (?, ?, ?)",
                     (9999, "Engineer", "Orphaned bullet"))
        conn.commit()


def test_applications_status_check_constraint():
    conn = make_db()
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO jds (company, role) VALUES ('Acme', 'Engineer')")
        conn.commit()
        jd_id = conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute("INSERT INTO applications (jd_id, status) VALUES (?, 'invalid_status')", (jd_id,))
        conn.commit()


def test_applications_has_offer_columns():
    """Canary for the offer-acceptance schema addition — columns on `applications`,
    not a separate `offers` table (see schema.sql's "Offer terms" comment block)."""
    conn = make_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(applications)")}
    for col in ("offer_received_at", "offer_salary", "offer_total_comp", "offer_currency",
                "offer_title", "offer_start_date", "offer_deadline", "offer_notes"):
        assert col in cols, f"Missing offer column: {col}"


def test_contact_insert_and_retrieve():
    conn = make_db()
    conn.execute("INSERT INTO contact (name, email, phone, location) VALUES (?, ?, ?, ?)",
                 ("Jane Doe", "jane@example.com", "555-0100", "Boston, MA"))
    conn.commit()
    row = conn.execute("SELECT * FROM contact LIMIT 1").fetchone()
    assert row["name"] == "Jane Doe"
    assert row["email"] == "jane@example.com"


def test_file_registry_unique_file_path():
    conn = make_db()
    conn.execute(
        "INSERT INTO file_registry (file_path, file_type) VALUES (?, ?)",
        ("data/applications/Acme/Engineer/resume.docx", "resume"),
    )
    conn.commit()
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO file_registry (file_path, file_type) VALUES (?, ?)",
            ("data/applications/Acme/Engineer/resume.docx", "resume"),
        )
        conn.commit()


def test_file_registry_jd_fk_set_null_on_delete():
    conn = make_db()
    conn.execute("INSERT INTO jds (company, role) VALUES ('Acme', 'Engineer')")
    conn.commit()
    jd_id = conn.execute("SELECT id FROM jds LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO file_registry (file_path, file_type, jd_id) VALUES (?, ?, ?)",
        ("data/applications/Acme/Engineer/resume.docx", "resume", jd_id),
    )
    conn.commit()
    conn.execute("DELETE FROM jds WHERE id = ?", (jd_id,))
    conn.commit()
    row = conn.execute("SELECT jd_id FROM file_registry").fetchone()
    assert row["jd_id"] is None
