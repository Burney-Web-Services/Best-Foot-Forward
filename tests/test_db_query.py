"""db_query.py: the raw-SQL CLI escape hatch used throughout .claude/commands/*.md
for persistence. Covers the --params-json flag added to make apostrophe/newline-
bearing prose (an evaluate-job summary, a decline reason in the seeker's own
words) safe to write without hand-escaping into the SQL string."""
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest

from best_foot_forward.utils import db_query

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE jds (id INTEGER PRIMARY KEY, company TEXT, summary TEXT)")
    conn.execute("INSERT INTO jds (id, company, summary) VALUES (1, 'Acme', NULL)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db_query, "DB_PATH", str(db_path))
    return db_path


class TestDbQuery:
    def test_select_prints_rows(self, temp_db, capsys):
        db_query.main(["SELECT company FROM jds WHERE id = 1"])
        out = capsys.readouterr().out
        assert "Acme" in out

    def test_select_no_rows(self, temp_db, capsys):
        db_query.main(["SELECT company FROM jds WHERE id = 999"])
        out = capsys.readouterr().out
        assert "(no rows)" in out

    def test_update_without_params(self, temp_db):
        db_query.main(["UPDATE jds SET company = 'NewCo' WHERE id = 1"])
        conn = sqlite3.connect(temp_db)
        assert conn.execute("SELECT company FROM jds WHERE id = 1").fetchone()[0] == "NewCo"

    def test_params_json_handles_apostrophes_and_newlines(self, temp_db):
        """The bug this flag exists for: prose with an apostrophe, hand-escaped
        into a SQL string literal, is the exact input that silently truncates or
        corrupts the write. Bound as a parameter, it must round-trip exactly."""
        summary = "Strong platform fit; team's stated priority is\nreliability work."
        db_query.main([
            "UPDATE jds SET summary = ? WHERE id = ?",
            "--params-json", f'["{summary}", 1]'.replace("\n", "\\n"),
        ])
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT summary FROM jds WHERE id = 1").fetchone()
        assert row["summary"] == summary

    def test_sql_error_exits_nonzero(self, temp_db):
        with pytest.raises(SystemExit):
            db_query.main(["SELECT * FROM nonexistent_table"])


class TestBffDataDirIsolation:
    """Regression test for a real incident: DB_PATH used to be hardcoded
    relative to this file, ignoring BFF_DATA_DIR entirely -- every other
    script here resolves through db.py's DATA_DIR (which honors the
    override), but this one didn't. A UAT run's evaluate-job score UPDATE
    (which persists via this script) landed on the real production DB
    instead of the isolated one, silently overwriting a real jds row.
    Caught only because the row happened to hold real data worth noticing;
    a subtler case would have gone unnoticed. Subprocess-based (not an
    import-time monkeypatch) because DB_PATH is computed once at import
    time from the environment -- the whole point is testing that
    resolution, not bypassing it."""

    def test_honors_bff_data_dir_override(self, tmp_path):
        uat_dir = tmp_path / "uat-data"
        uat_dir.mkdir()
        conn = sqlite3.connect(uat_dir / "best_foot_forward.db")
        conn.execute("CREATE TABLE jds (id INTEGER PRIMARY KEY, company TEXT)")
        conn.execute("INSERT INTO jds (id, company) VALUES (1, 'IsolatedCo')")
        conn.commit()
        conn.close()

        env = {**os.environ, "BFF_DATA_DIR": str(uat_dir)}
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "src/best_foot_forward/utils/db_query.py"),
             "SELECT company FROM jds WHERE id = 1"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "IsolatedCo" in result.stdout

    def test_does_not_fall_back_to_the_real_repo_db(self, tmp_path):
        """The real DB has hundreds of jds rows; an empty isolated dir has
        none. If this ever queries the real DB instead, this passes instead
        of erroring -- that's the exact silent-contamination failure mode."""
        uat_dir = tmp_path / "uat-empty"
        uat_dir.mkdir()

        env = {**os.environ, "BFF_DATA_DIR": str(uat_dir)}
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "src/best_foot_forward/utils/db_query.py"),
             "SELECT count(*) FROM jds"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0
        assert "no such table" in (result.stdout + result.stderr).lower()
