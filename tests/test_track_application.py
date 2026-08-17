"""track_application.py: auto-tracks a tailored application, reading
COMPANY/ROLE/JD_FILE_PATH from resume_data.py. Subprocess-based (not an
import-time monkeypatch) since the script executes top-level code on import
and resolves its DB path from BFF_DATA_DIR at that time -- the whole point
of these tests is exercising that resolution and the resulting DB writes,
not bypassing them.

Covers the fail-loud behavior added for TODO.md's "track_application
JD-lookup mismatch" item: a lookup miss (no jds row matches by file_path or
by company+role) used to silently insert a fresh, scoreless duplicate jds
row -- the exact failure class that recurred three times before path
canonicalization was added (see CLAUDE.md's JD-file-conventions section).
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "src" / "best_foot_forward" / "schema.sql"
SCRIPT = REPO_ROOT / "src" / "best_foot_forward" / "utils" / "track_application.py"


def make_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.close()


def write_resume_data(session_dir: Path, company: str, role: str, jd_file_path: str) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "resume_data.py").write_text(
        f"COMPANY = {company!r}\nROLE = {role!r}\nJD_FILE_PATH = {jd_file_path!r}\n"
        "RESUME = {}\n"
    )


def run_track_application(data_dir: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "BFF_DATA_DIR": str(data_dir)}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=30,
    )


class TestTrackApplication:
    def test_found_jd_tracks_normally(self, tmp_path):
        data_dir = tmp_path / "uat-data"
        data_dir.mkdir()
        db_path = data_dir / "best_foot_forward.db"
        make_db(db_path)

        jd_file = str(data_dir / "BestFootForward" / "assets" / "Acme" / "Engineer" / "Acme_EngineerJobDesc.md")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO jds (company, role, file_path, score) VALUES (?, ?, ?, ?)",
            ("Acme", "Engineer", jd_file, 80),
        )
        conn.commit()
        conn.close()

        write_resume_data(data_dir / "session", "Acme", "Engineer", jd_file)

        result = run_track_application(data_dir)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Tracked: Acme" in result.stdout

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        jds = conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0]
        apps = conn.execute("SELECT status FROM applications").fetchall()
        conn.close()
        assert jds == 1, "found path must not create a second jds row"
        assert len(apps) == 1
        assert apps[0]["status"] == "applied"

    def test_adopted_jd_backfills_file_path(self, tmp_path):
        """company+role matches an existing row whose file_path differs (or is
        NULL, e.g. a pasted-JD lead stub) -- adopted, not duplicated."""
        data_dir = tmp_path / "uat-data"
        data_dir.mkdir()
        db_path = data_dir / "best_foot_forward.db"
        make_db(db_path)

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO jds (company, role, file_path, score) VALUES (?, ?, NULL, ?)",
            ("Acme", "Engineer", 80),
        )
        conn.commit()
        conn.close()

        jd_file = str(data_dir / "BestFootForward" / "assets" / "Acme" / "Engineer" / "Acme_EngineerJobDesc.md")
        write_resume_data(data_dir / "session", "Acme", "Engineer", jd_file)

        result = run_track_application(data_dir)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Linked existing jds row" in result.stdout

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        jds = conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0]
        row = conn.execute("SELECT file_path FROM jds").fetchone()
        conn.close()
        assert jds == 1
        assert row["file_path"] == os.path.normpath(jd_file)

    def test_lookup_miss_fails_loudly_and_creates_no_duplicate_row(self, tmp_path):
        """No jds row matches by file_path or by company+role -- this must
        now fail loudly (nonzero exit, explanatory stderr) instead of
        silently inserting a fresh scoreless duplicate."""
        data_dir = tmp_path / "uat-data"
        data_dir.mkdir()
        db_path = data_dir / "best_foot_forward.db"
        make_db(db_path)
        # Deliberately no jds row at all.

        jd_file = str(data_dir / "BestFootForward" / "assets" / "Ghost Co" / "Engineer" / "GhostCo_EngineerJobDesc.md")
        write_resume_data(data_dir / "session", "Ghost Co", "Engineer", jd_file)

        result = run_track_application(data_dir)
        assert result.returncode != 0
        assert "Refusing to insert a fresh duplicate stub" in result.stderr

        conn = sqlite3.connect(db_path)
        jds = conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0]
        apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        conn.close()
        assert jds == 0, "a failed lookup must not leave a stub jds row behind"
        assert apps == 0

    def test_already_tracked_application_is_idempotent(self, tmp_path):
        data_dir = tmp_path / "uat-data"
        data_dir.mkdir()
        db_path = data_dir / "best_foot_forward.db"
        make_db(db_path)

        jd_file = str(data_dir / "BestFootForward" / "assets" / "Acme" / "Engineer" / "Acme_EngineerJobDesc.md")
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "INSERT INTO jds (company, role, file_path, score) VALUES (?, ?, ?, ?)",
            ("Acme", "Engineer", jd_file, 80),
        )
        jd_id = cur.lastrowid
        conn.execute(
            "INSERT INTO applications (jd_id, created_at, resume_summary, status) "
            "VALUES (?, datetime('now'), '', 'applied')",
            (jd_id,),
        )
        conn.commit()
        conn.close()

        write_resume_data(data_dir / "session", "Acme", "Engineer", jd_file)

        result = run_track_application(data_dir)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "already exists" in result.stdout

        conn = sqlite3.connect(db_path)
        apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        conn.close()
        assert apps == 1, "must not insert a second application row"
