"""delete_lead.py: the single write path for removing a jds row, added so a
deleted lead's JD file also gets removed from disk -- otherwise scan_jds.py
later rediscovers the orphaned file and silently re-registers it as a
duplicate row (see test_scan_jds.py's canonical-match tests for the other
half of that fix, and TODO.md's 'scan_jds re-registers orphaned JD files'
item for the incident this closes)."""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils import delete_lead as m

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "bff.db"
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_PATH.read_text())
    c.close()
    return path


@pytest.fixture
def conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


@pytest.fixture
def jd_file(tmp_path):
    d = tmp_path / "assets" / "GhostCo" / "Engineer"
    d.mkdir(parents=True)
    f = d / "GhostCo_EngineerJobDesc.md"
    f.write_text("A posting nobody wants tracked anymore.")
    return f


def _insert_jd(conn, file_path=None, **cols):
    cols = {"company": "GhostCo", "role": "Engineer", "file_path": str(file_path) if file_path else None, **cols}
    keys = ", ".join(cols)
    cur = conn.execute(
        f"INSERT INTO jds ({keys}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values())
    )
    conn.commit()
    return cur.lastrowid


class TestDeleteLead:
    def test_deletes_row_and_removes_jd_file(self, conn, jd_file):
        jd_id = _insert_jd(conn, file_path=jd_file)

        result = m.delete_lead(conn, jd_id)

        assert result["files_removed"] == [str(jd_file)]
        assert not jd_file.exists()
        assert conn.execute("SELECT COUNT(*) FROM jds WHERE id=?", (jd_id,)).fetchone()[0] == 0

    def test_dry_run_deletes_nothing(self, conn, jd_file):
        jd_id = _insert_jd(conn, file_path=jd_file)

        result = m.delete_lead(conn, jd_id, dry_run=True)

        assert result["files_removed"] == [str(jd_file)]
        assert jd_file.exists(), "dry-run must not touch the filesystem"
        assert conn.execute("SELECT COUNT(*) FROM jds WHERE id=?", (jd_id,)).fetchone()[0] == 1

    def test_removes_sibling_jd_files_in_the_same_directory(self, conn, jd_file, tmp_path):
        """An .odt/.txt pair left over from a format change would otherwise
        still be rediscovered by a later scan_jds.py pass."""
        sibling = jd_file.parent / "GhostCo_EngineerJobDesc.odt"
        sibling.write_bytes(b"fake odt bytes")
        noise = jd_file.parent / "ClaudeNotes.md"
        noise.write_text("not a JD file, must survive")

        jd_id = _insert_jd(conn, file_path=jd_file)
        result = m.delete_lead(conn, jd_id)

        assert set(result["files_removed"]) == {str(jd_file), str(sibling)}
        assert not jd_file.exists()
        assert not sibling.exists()
        assert noise.exists(), "non-JD files in the same directory must be left alone"

    def test_refuses_to_delete_a_lead_with_an_application(self, conn, jd_file):
        jd_id = _insert_jd(conn, file_path=jd_file)
        conn.execute(
            "INSERT INTO applications (jd_id, created_at, resume_summary, status) "
            "VALUES (?, datetime('now'), '', 'applied')",
            (jd_id,),
        )
        conn.commit()

        with pytest.raises(ValueError, match="application"):
            m.delete_lead(conn, jd_id)

        assert jd_file.exists()
        assert conn.execute("SELECT COUNT(*) FROM jds WHERE id=?", (jd_id,)).fetchone()[0] == 1

    def test_refuses_to_delete_a_lead_with_a_contact(self, conn, jd_file):
        jd_id = _insert_jd(conn, file_path=jd_file)
        conn.execute("INSERT INTO contacts (jd_id, name) VALUES (?, 'Recruiter Name')", (jd_id,))
        conn.commit()

        with pytest.raises(ValueError, match="contact"):
            m.delete_lead(conn, jd_id)

        assert conn.execute("SELECT COUNT(*) FROM jds WHERE id=?", (jd_id,)).fetchone()[0] == 1

    def test_unknown_jd_id_raises_lookup_error(self, conn):
        with pytest.raises(LookupError):
            m.delete_lead(conn, 9999)

    def test_missing_on_disk_file_does_not_block_deletion(self, conn, tmp_path):
        """A row whose file was already removed by hand must still be
        deletable -- the point is not leaving a dangling row either way."""
        jd_id = _insert_jd(conn, file_path=tmp_path / "already-gone.md")

        result = m.delete_lead(conn, jd_id)

        assert result["files_removed"] == []
        assert conn.execute("SELECT COUNT(*) FROM jds WHERE id=?", (jd_id,)).fetchone()[0] == 0

    def test_deletes_file_registry_row_instead_of_leaving_it_dangling(self, conn, jd_file):
        jd_id = _insert_jd(conn, file_path=jd_file)
        conn.execute(
            "INSERT INTO file_registry (file_path, file_type, jd_id) VALUES (?, 'jd', ?)",
            (str(jd_file), jd_id),
        )
        conn.commit()

        m.delete_lead(conn, jd_id)

        assert conn.execute(
            "SELECT COUNT(*) FROM file_registry WHERE jd_id=?", (jd_id,)
        ).fetchone()[0] == 0
