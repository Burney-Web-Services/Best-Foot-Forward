"""
Tests for track_bullets.record_bullet_selections.

Uses an in-memory SQLite DB so no data/ directory is required.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "src" / "best_foot_forward" / "schema.sql"
sys.path.insert(0, str(ROOT / "src" / "best_foot_forward" / "utils"))

from track_bullets import record_bullet_selections


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_db(conn):
    """Insert minimal rows needed to satisfy FK constraints."""
    conn.execute(
        "INSERT INTO employers (id, name, location, start_date, sort_order) VALUES (1, 'Acme', 'Boston, MA', '01/2020', 1)"
    )
    conn.execute(
        "INSERT INTO bullets (id, employer_id, role, text) VALUES ('bullet-a', 1, 'Engineer', 'Canonical text A')"
    )
    conn.execute(
        "INSERT INTO bullets (id, employer_id, role, text) VALUES ('bullet-b', 1, 'Engineer', 'Canonical text B')"
    )
    conn.execute(
        "INSERT INTO skills (id, label, content) VALUES ('skill-x', 'Languages', 'Python, PHP')"
    )
    conn.execute(
        "INSERT INTO jds (id, company, role) VALUES (1, 'Acme', 'Engineer')"
    )
    conn.execute(
        "INSERT INTO applications (id, jd_id, created_at, resume_summary) VALUES (1, 1, '2026-01-01T00:00:00', 'summary')"
    )
    conn.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_bullets_inserted_with_correct_position():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [{
            'employer': 'Acme',
            'roles': [{
                'title': 'Engineer',
                'bullets': [
                    {'id': 'bullet-a', 'text': 'Canonical text A'},
                    {'id': 'bullet-b', 'text': 'Canonical text B'},
                ],
            }],
        }],
        'skills': [],
    }
    record_bullet_selections(conn, 1, resume)
    rows = conn.execute(
        "SELECT bullet_id, position FROM application_bullets WHERE application_id=1 ORDER BY position"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]['bullet_id'] == 'bullet-a' and rows[0]['position'] == 1
    assert rows[1]['bullet_id'] == 'bullet-b' and rows[1]['position'] == 2


def test_text_override_null_when_text_matches_canonical():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [{
            'employer': 'Acme',
            'roles': [{'title': 'Engineer', 'bullets': [{'id': 'bullet-a', 'text': 'Canonical text A'}]}],
        }],
        'skills': [],
    }
    record_bullet_selections(conn, 1, resume)
    row = conn.execute("SELECT text_override FROM application_bullets WHERE bullet_id='bullet-a'").fetchone()
    assert row['text_override'] is None


def test_text_override_populated_when_text_differs():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [{
            'employer': 'Acme',
            'roles': [{'title': 'Engineer', 'bullets': [{'id': 'bullet-a', 'text': 'Modified text for this role'}]}],
        }],
        'skills': [],
    }
    record_bullet_selections(conn, 1, resume)
    row = conn.execute("SELECT text_override FROM application_bullets WHERE bullet_id='bullet-a'").fetchone()
    assert row['text_override'] == 'Modified text for this role'


def test_plain_string_bullets_skipped():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [{
            'employer': 'Acme',
            'roles': [{'title': 'Engineer', 'bullets': ['Plain string bullet — no id']}],
        }],
        'skills': [],
    }
    record_bullet_selections(conn, 1, resume)
    count = conn.execute("SELECT COUNT(*) FROM application_bullets WHERE application_id=1").fetchone()[0]
    assert count == 0


def test_skills_inserted():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [],
        'skills': [{'id': 'skill-x', 'label': 'Languages', 'content': 'Python, PHP'}],
    }
    record_bullet_selections(conn, 1, resume)
    row = conn.execute("SELECT skill_id, position, content_override FROM application_skills WHERE application_id=1").fetchone()
    assert row['skill_id'] == 'skill-x'
    assert row['position'] == 1
    assert row['content_override'] is None


def test_skill_content_override_when_adjusted():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [],
        'skills': [{'id': 'skill-x', 'label': 'Languages', 'content': 'Python, PHP, Ruby (refreshing)'}],
    }
    record_bullet_selections(conn, 1, resume)
    row = conn.execute("SELECT content_override FROM application_skills WHERE skill_id='skill-x'").fetchone()
    assert row['content_override'] == 'Python, PHP, Ruby (refreshing)'


def test_skills_without_id_skipped():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [],
        'skills': [{'label': 'Languages', 'content': 'Python, PHP'}],  # no 'id' key
    }
    record_bullet_selections(conn, 1, resume)
    count = conn.execute("SELECT COUNT(*) FROM application_skills WHERE application_id=1").fetchone()[0]
    assert count == 0


def test_idempotent_on_rerun():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [{
            'employer': 'Acme',
            'roles': [{'title': 'Engineer', 'bullets': [{'id': 'bullet-a', 'text': 'Canonical text A'}]}],
        }],
        'skills': [{'id': 'skill-x', 'label': 'Languages', 'content': 'Python, PHP'}],
    }
    record_bullet_selections(conn, 1, resume)
    record_bullet_selections(conn, 1, resume)  # second run — should not duplicate
    bullet_count = conn.execute("SELECT COUNT(*) FROM application_bullets WHERE application_id=1").fetchone()[0]
    skill_count = conn.execute("SELECT COUNT(*) FROM application_skills WHERE application_id=1").fetchone()[0]
    assert bullet_count == 1
    assert skill_count == 1


def test_additional_experience_bullets_tracked():
    conn = make_db()
    seed_db(conn)
    resume = {
        'experience': [],
        'additional_experience': [{
            'employer': 'Acme',
            'roles': [{'title': 'Engineer', 'bullets': [{'id': 'bullet-b', 'text': 'Canonical text B'}]}],
        }],
        'skills': [],
    }
    record_bullet_selections(conn, 1, resume)
    row = conn.execute("SELECT bullet_id FROM application_bullets WHERE application_id=1").fetchone()
    assert row['bullet_id'] == 'bullet-b'
