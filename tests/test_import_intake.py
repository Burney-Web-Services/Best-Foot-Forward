"""
Tests for import_intake.py — the utility that populates SQLite from
data/session/intake_data.py during the /onboard workflow.

Strategy: monkeypatch get_conn/init_db in import_intake to use a temp SQLite
file, inject a synthetic intake_data module, call run(), then reopen the file
to assert the results. Using a real file (not :memory:) because run() calls
conn.close() before we can assert.
"""

import sys
import sqlite3
import types
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_db_file(path: Path) -> Path:
    """Create a schema-initialized SQLite file and return its path."""
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA_PATH.read_text())
    conn.close()
    return path


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def make_intake_module(**overrides) -> types.ModuleType:
    m = types.ModuleType("intake_data")
    m.CONTACT = overrides.get("CONTACT", {
        "name": "Jane Doe",
        "phone": "555-0100",
        "email": "jane@example.com",
        "location": "Boston, MA",
    })
    m.EDUCATION = overrides.get("EDUCATION", [
        {"institution": "MIT", "location": "Cambridge, MA",
         "degree": "BS Computer Science", "sort_order": 0},
    ])
    m.EMPLOYERS = overrides.get("EMPLOYERS", [
        {"name": "Acme Corp", "location": "Boston, MA",
         "start_date": "01/2020", "end_date": None, "sort_order": 0, "notes": ""},
    ])
    m.BULLETS = overrides.get("BULLETS", [
        {"id": None, "employer": "Acme Corp", "role": "Engineer",
         "text": "Built the core API.", "tracks": ["engineer"], "themes": ["backend"]},
    ])
    m.SKILLS = overrides.get("SKILLS", [
        {"id": None, "label": "Backend:", "content": "Python, SQL",
         "tracks": ["engineer"], "themes": ["backend"]},
    ])
    return m


@pytest.fixture(autouse=True)
def cleanup_intake_module():
    """Remove intake_data from sys.modules before and after every test."""
    sys.modules.pop("intake_data", None)
    yield
    sys.modules.pop("intake_data", None)


@pytest.fixture
def db_path(tmp_path):
    return make_db_file(tmp_path / "test_bff.db")


@pytest.fixture
def import_intake(monkeypatch, db_path, tmp_path):
    """Import the module and wire get_conn/init_db to the temp DB.

    Also redirects the audit log (import_intake.py logs one line per run())
    to a temp file. The bare `from utils.audit_log import log_event` import
    resolves to a SEPARATE module object from `best_foot_forward.utils.audit_log`
    under pytest's dotted import — patch LOG_PATH on log_event's actual
    __globals__ rather than the dotted module, which would silently no-op.
    """
    import best_foot_forward.utils.import_intake as ii

    def fake_get_conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(ii, "get_conn", fake_get_conn)
    monkeypatch.setattr(ii, "init_db", lambda: None)
    ii.log_event.__globals__["LOG_PATH"] = str(tmp_path / "audit_log.jsonl")
    return ii


def run(import_intake, **overrides):
    """Inject intake_data and call import_intake.run()."""
    sys.modules["intake_data"] = make_intake_module(**overrides)
    import_intake.run()


# ── Helper tests ──────────────────────────────────────────────────────────────

class TestSlugify:
    def test_first_word_lowercased(self, import_intake):
        assert import_intake.slugify("Acme Corp") == "acme"

    def test_truncated_to_eight_chars(self, import_intake):
        assert import_intake.slugify("Abcdefghijklmnop LLC") == "abcdefgh"

    def test_non_alphanumeric_stripped(self, import_intake):
        # "Burney-Web" → strip hyphen → "BurneyWeb" (9 chars) → truncate → "burneywe"
        assert import_intake.slugify("Burney-Web Services") == "burneywe"

    def test_single_word(self, import_intake):
        assert import_intake.slugify("Google") == "google"


class TestSkillIdFromLabel:
    def test_simple_label(self, import_intake):
        assert import_intake.skill_id_from_label("Backend:") == "skills-backend"

    def test_ampersand_and_spaces(self, import_intake):
        assert import_intake.skill_id_from_label("AI & Product Engineering:") == "skills-ai-product-engineering"

    def test_no_trailing_colon(self, import_intake):
        assert import_intake.skill_id_from_label("Leadership") == "skills-leadership"


# ── Contact ───────────────────────────────────────────────────────────────────

class TestContact:
    def test_contact_written(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        row = conn.execute("SELECT * FROM contact WHERE id = 1").fetchone()
        assert row["name"] == "Jane Doe"
        assert row["email"] == "jane@example.com"
        assert row["location"] == "Boston, MA"
        conn.close()

    def test_contact_overwritten_on_rerun(self, import_intake, db_path):
        run(import_intake)
        updated = {"name": "Updated Name", "phone": "555-9999",
                   "email": "new@example.com", "location": "Cambridge, MA"}
        run(import_intake, CONTACT=updated)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM contact WHERE id = 1").fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "Updated Name"
        conn.close()


# ── Education ─────────────────────────────────────────────────────────────────

class TestEducation:
    def test_education_inserted(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM education").fetchall()
        assert len(rows) == 1
        assert rows[0]["institution"] == "MIT"
        conn.close()

    def test_no_duplicate_on_rerun(self, import_intake, db_path):
        run(import_intake)
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM education").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_multiple_education_records(self, import_intake, db_path):
        education = [
            {"institution": "MIT", "location": "Cambridge, MA", "degree": "BS CS", "sort_order": 0},
            {"institution": "Harvard", "location": "Cambridge, MA", "degree": "MBA", "sort_order": 1},
        ]
        run(import_intake, EDUCATION=education)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM education ORDER BY sort_order").fetchall()
        assert len(rows) == 2
        assert rows[1]["institution"] == "Harvard"
        conn.close()


# ── Employers ─────────────────────────────────────────────────────────────────

class TestEmployers:
    def test_employer_inserted(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM employers").fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "Acme Corp"
        conn.close()

    def test_no_duplicate_on_rerun(self, import_intake, db_path):
        run(import_intake)
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM employers").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_null_end_date_for_current_employer(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        row = conn.execute("SELECT end_date FROM employers WHERE name='Acme Corp'").fetchone()
        assert row["end_date"] is None
        conn.close()

    def test_employer_notes_stored(self, import_intake, db_path):
        employers = [{"name": "Acme Corp", "location": "Boston, MA",
                      "start_date": "01/2020", "end_date": None,
                      "sort_order": 0, "notes": "SaaS startup, 50 engineers"}]
        run(import_intake, EMPLOYERS=employers)
        conn = open_db(db_path)
        row = conn.execute("SELECT notes FROM employers WHERE name='Acme Corp'").fetchone()
        assert row["notes"] == "SaaS startup, 50 engineers"
        conn.close()


# ── Bullets ───────────────────────────────────────────────────────────────────

class TestBullets:
    def test_bullet_inserted(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM bullets").fetchall()
        assert len(rows) == 1
        assert rows[0]["text"] == "Built the core API."
        conn.close()

    def test_auto_id_generated(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        row = conn.execute("SELECT id FROM bullets").fetchone()
        assert row["id"] == "acme-001"
        conn.close()

    def test_sequence_increments_per_employer(self, import_intake, db_path):
        bullets = [
            {"id": None, "employer": "Acme Corp", "role": "Engineer",
             "text": "First.", "tracks": ["engineer"], "themes": []},
            {"id": None, "employer": "Acme Corp", "role": "Engineer",
             "text": "Second.", "tracks": ["engineer"], "themes": []},
        ]
        run(import_intake, BULLETS=bullets)
        conn = open_db(db_path)
        ids = {r["id"] for r in conn.execute("SELECT id FROM bullets").fetchall()}
        assert "acme-001" in ids
        assert "acme-002" in ids
        conn.close()

    def test_sequence_picks_up_from_existing(self, import_intake, db_path):
        """Second run continues from where the first left off."""
        first = [{"id": None, "employer": "Acme Corp", "role": "Engineer",
                  "text": "First.", "tracks": ["engineer"], "themes": []}]
        second = [{"id": None, "employer": "Acme Corp", "role": "Engineer",
                   "text": "Second.", "tracks": ["engineer"], "themes": []}]
        run(import_intake, BULLETS=first)
        run(import_intake, BULLETS=second)
        conn = open_db(db_path)
        ids = {r["id"] for r in conn.execute("SELECT id FROM bullets").fetchall()}
        assert "acme-001" in ids
        assert "acme-002" in ids
        conn.close()

    def test_explicit_id_preserved(self, import_intake, db_path):
        bullets = [{"id": "custom-xyz-007", "employer": "Acme Corp", "role": "Engineer",
                    "text": "Custom.", "tracks": ["general"], "themes": []}]
        run(import_intake, BULLETS=bullets)
        conn = open_db(db_path)
        row = conn.execute("SELECT id FROM bullets WHERE id='custom-xyz-007'").fetchone()
        assert row is not None
        conn.close()

    def test_bullet_tracks_written(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM bullet_tracks").fetchall()
        assert any(r["track"] == "engineer" for r in rows)
        conn.close()

    def test_bullet_themes_written(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM bullet_themes").fetchall()
        assert any(r["theme"] == "backend" for r in rows)
        conn.close()

    def test_multiple_tracks_per_bullet(self, import_intake, db_path):
        bullets = [{"id": None, "employer": "Acme Corp", "role": "Manager",
                    "text": "Led team.", "tracks": ["engineer", "manager"], "themes": []}]
        run(import_intake, BULLETS=bullets)
        conn = open_db(db_path)
        rows = conn.execute("SELECT track FROM bullet_tracks").fetchall()
        tracks = {r["track"] for r in rows}
        assert "engineer" in tracks
        assert "manager" in tracks
        conn.close()

    def test_unknown_employer_skips_bullet(self, import_intake, db_path, capsys):
        bullets = [{"id": None, "employer": "No Such Corp", "role": "Engineer",
                    "text": "Should be skipped.", "tracks": ["engineer"], "themes": []}]
        run(import_intake, BULLETS=bullets)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM bullets").fetchall()
        assert len(rows) == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        conn.close()

    def test_duplicate_bullet_skipped_on_rerun(self, import_intake, db_path):
        run(import_intake)
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM bullets").fetchall()
        assert len(rows) == 1
        conn.close()


# ── Skills ────────────────────────────────────────────────────────────────────

class TestSkills:
    def test_skill_inserted(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM skills").fetchall()
        assert len(rows) == 1
        assert rows[0]["label"] == "Backend:"
        conn.close()

    def test_auto_id_generated(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        row = conn.execute("SELECT id FROM skills").fetchone()
        assert row["id"] == "skills-backend"
        conn.close()

    def test_explicit_id_preserved(self, import_intake, db_path):
        skills = [{"id": "skills-custom", "label": "Custom:", "content": "Stuff",
                   "tracks": ["general"], "themes": []}]
        run(import_intake, SKILLS=skills)
        conn = open_db(db_path)
        row = conn.execute("SELECT id FROM skills WHERE id='skills-custom'").fetchone()
        assert row is not None
        conn.close()

    def test_skill_tracks_written(self, import_intake, db_path):
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT track FROM skill_tracks").fetchall()
        assert any(r["track"] == "engineer" for r in rows)
        conn.close()

    def test_no_duplicate_on_rerun(self, import_intake, db_path):
        run(import_intake)
        run(import_intake)
        conn = open_db(db_path)
        rows = conn.execute("SELECT * FROM skills").fetchall()
        assert len(rows) == 1
        conn.close()


# ── Full round-trip ───────────────────────────────────────────────────────────

class TestRoundTrip:
    def test_full_intake_populates_all_tables(self, import_intake, db_path):
        employers = [
            {"name": "StartupA", "location": "SF, CA", "start_date": "03/2022",
             "end_date": None, "sort_order": 0, "notes": ""},
            {"name": "BigCo", "location": "NYC, NY", "start_date": "01/2018",
             "end_date": "02/2022", "sort_order": 1, "notes": "Fortune 500"},
        ]
        bullets = [
            {"id": None, "employer": "StartupA", "role": "Senior Engineer",
             "text": "Reduced p99 latency from 800ms to 120ms by rewriting the cache layer.",
             "tracks": ["engineer"], "themes": ["backend", "scale"]},
            {"id": None, "employer": "BigCo", "role": "Engineering Manager",
             "text": "Grew team from 3 to 11 engineers over 18 months.",
             "tracks": ["manager"], "themes": ["leadership"]},
        ]
        skills = [
            {"id": None, "label": "Backend:", "content": "Python, Go, Redis",
             "tracks": ["engineer"], "themes": ["backend"]},
            {"id": None, "label": "Leadership:", "content": "Hiring, Coaching, Roadmapping",
             "tracks": ["manager"], "themes": ["leadership"]},
        ]
        run(import_intake, EMPLOYERS=employers, BULLETS=bullets, SKILLS=skills)

        conn = open_db(db_path)
        assert len(conn.execute("SELECT * FROM employers").fetchall()) == 2
        assert len(conn.execute("SELECT * FROM bullets").fetchall()) == 2
        assert len(conn.execute("SELECT * FROM skills").fetchall()) == 2

        # Bullets get employer-specific slug IDs ("StartupA" → "startupa")
        ids = {r["id"] for r in conn.execute("SELECT id FROM bullets").fetchall()}
        assert "startupa-001" in ids
        assert "bigco-001" in ids

        # Cross-table: bullet themes
        themes = {r["theme"] for r in conn.execute("SELECT theme FROM bullet_themes").fetchall()}
        assert "scale" in themes
        assert "leadership" in themes
        conn.close()
