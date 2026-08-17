"""resolve_or_create_jd is the single definition of "find the jds row for this job,
creating it if the job was never evaluated".

It replaced three hand-maintained copies that drifted apart twice, each time producing
a data bug: an application row with jd_id NULL, orphaned from every report that joins
through jds, and matchable by `WHERE jd_id IS ?` against an unrelated company's orphan.
"""
import sqlite3
from pathlib import Path

from best_foot_forward.db import resolve_or_create_jd

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def add_jd(conn, company="Acme", role="QA Engineer", file_path="/jd/acme.md"):
    conn.execute("INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)",
                 (company, role, file_path))
    conn.commit()
    return conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()["id"]


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0]


def test_found_by_file_path():
    conn = make_db()
    jd_id = add_jd(conn)
    assert resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md") == (jd_id, "found")
    assert count(conn) == 1


def test_adopts_row_whose_file_path_differs():
    """A lead stub written by evaluate-job carries the *expected* path; tailoring may
    arrive with a different one. Adopt the row rather than duplicating the job."""
    conn = make_db()
    jd_id = add_jd(conn, file_path="/jd/expected/acme.md")

    got_id, action = resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/actual/acme.md")

    assert (got_id, action) == (jd_id, "adopted")
    assert count(conn) == 1
    assert conn.execute("SELECT file_path FROM jds WHERE id=?", (jd_id,)).fetchone()[0] \
        == "/jd/actual/acme.md"


def test_adopts_row_with_no_file_path():
    """Collaborator-sourced leads import with file_path NULL."""
    conn = make_db()
    jd_id = add_jd(conn, file_path=None)

    got_id, action = resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md")

    assert (got_id, action) == (jd_id, "adopted")
    assert count(conn) == 1


def test_creates_when_job_was_never_evaluated():
    conn = make_db()
    jd_id, action = resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md")

    assert action == "created"
    assert jd_id is not None            # a NULL jd_id is what orphans the application
    row = conn.execute("SELECT company, role, file_path FROM jds WHERE id=?", (jd_id,)).fetchone()
    assert tuple(row) == ("Acme", "QA Engineer", "/jd/acme.md")


def test_same_role_at_different_companies_stays_separate():
    conn = make_db()
    a, _ = resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md")
    b, action = resolve_or_create_jd(conn, "Beta", "QA Engineer", "/jd/beta.md")

    assert action == "created"
    assert a != b and count(conn) == 2


def test_is_idempotent():
    conn = make_db()
    first, _ = resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md")
    second, action = resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md")

    assert (second, action) == (first, "found")
    assert count(conn) == 1


def test_does_not_commit():
    """The caller owns the transaction — track_application commits eagerly because it
    can exit early, generate_resume commits once at the end."""
    conn = make_db()
    resolve_or_create_jd(conn, "Acme", "QA Engineer", "/jd/acme.md")
    assert count(conn) == 1
    conn.rollback()
    assert count(conn) == 0
