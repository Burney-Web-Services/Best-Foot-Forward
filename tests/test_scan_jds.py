"""Rescan is an indexing pass, not a scoring pass: it refreshes required skills and
fills gaps, but never restamps a lead's score time.
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils import scan_jds as m

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"

JD_TEXT = """Senior Test Engineer

We need strong Selenium and Java experience, plus Jenkins for CI.
Compensation: $120,000 - $150,000 depending on location.
"""


@pytest.fixture
def db_path(tmp_path):
    """A real file DB, because scan() closes its connection when it finishes."""
    path = tmp_path / "bff.db"
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_PATH.read_text())
    for sid, label in [("sel", "Selenium"), ("java", "Java"), ("jen", "Jenkins")]:
        c.execute("INSERT INTO skills (id, label, content) VALUES (?,?,?)", (sid, label, label))
    c.commit()
    c.close()
    return path


@pytest.fixture
def conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture
def jd_dir(tmp_path):
    """An asset tree shaped the way scan() expects: {Company}/{Role_Slug}/{...}JobDesc.md."""
    d = tmp_path / "assets" / "Alderaan_Systems" / "Senior_Test_Engineer"
    d.mkdir(parents=True)
    (d / "Alderaan_Systems_Senior_Test_EngineerJobDesc.md").write_text(JD_TEXT)
    return d


@pytest.fixture(autouse=True)
def isolate(db_path, monkeypatch):
    """Point scan() at the temp DB and keep it out of the real audit log."""
    def _get_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(m, "get_conn", _get_conn)
    monkeypatch.setattr(m, "init_db", lambda: None)
    monkeypatch.setattr(m, "resolve_jd_path", lambda p: p)
    monkeypatch.setattr(m, "log_event", lambda *a, **k: None)


def _insert_jd(conn, jd_dir, **cols):
    path = str(jd_dir / "Alderaan_Systems_Senior_Test_EngineerJobDesc.md")
    cols = {"company": "Alderaan Systems", "role": "Senior Test Engineer", "file_path": path, **cols}
    keys = ", ".join(cols)
    cur = conn.execute(
        f"INSERT INTO jds ({keys}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values())
    )
    conn.commit()
    return cur.lastrowid


def test_rescan_does_not_overwrite_a_real_score_time(conn, jd_dir):
    """evaluate-job owns evaluated_at: it means when the lead was *scored*. A scanner
    restamping it makes the column mean "scored or scanned, whichever was last",
    which destroys the interval between scoring and applying."""
    jd_id = _insert_jd(conn, jd_dir, score=72, evaluated_at="2026-08-01T09:00:00")

    m.scan(str(jd_dir), rescan=True)

    row = conn.execute("SELECT score, evaluated_at FROM jds WHERE id=?", (jd_id,)).fetchone()
    assert row["evaluated_at"] == "2026-08-01T09:00:00"
    assert row["score"] == 72


def test_rescan_stamps_a_row_that_was_never_scored(conn, jd_dir):
    """Filling a NULL is the one case where a scan may write the column."""
    jd_id = _insert_jd(conn, jd_dir)

    m.scan(str(jd_dir), rescan=True)

    assert conn.execute("SELECT evaluated_at FROM jds WHERE id=?", (jd_id,)).fetchone()[0] is not None


def test_rescan_still_refreshes_required_skills(conn, jd_dir):
    """Guard the behaviour the fix sits next to: indexing is the point of a rescan."""
    jd_id = _insert_jd(conn, jd_dir, evaluated_at="2026-08-01T09:00:00")
    conn.execute("INSERT INTO jd_required_skills (jd_id, skill_label) VALUES (?, 'cobol')", (jd_id,))
    conn.commit()

    m.scan(str(jd_dir), rescan=True)

    labels = {r["skill_label"] for r in conn.execute(
        "SELECT skill_label FROM jd_required_skills WHERE jd_id=?", (jd_id,))}
    assert {"selenium", "java", "jenkins"} <= labels
    assert "cobol" not in labels  # stale rows are cleared, not accumulated


def test_rescan_fills_salary_but_never_clobbers_a_hand_set_range(conn, jd_dir):
    """A range set by hand off a posting's sidebar must survive a parse that finds
    nothing in the body text."""
    jd_id = _insert_jd(conn, jd_dir, salary_min=125000, salary_max=143000)
    (jd_dir / "Alderaan_Systems_Senior_Test_EngineerJobDesc.md").write_text("No pay information here at all.")

    m.scan(str(jd_dir), rescan=True)

    row = conn.execute("SELECT salary_min, salary_max FROM jds WHERE id=?", (jd_id,)).fetchone()
    assert (row["salary_min"], row["salary_max"]) == (125000, 143000)


def test_rescan_adds_a_salary_the_row_was_missing(conn, jd_dir):
    jd_id = _insert_jd(conn, jd_dir)

    m.scan(str(jd_dir), rescan=True)

    row = conn.execute("SELECT salary_min, salary_max FROM jds WHERE id=?", (jd_id,)).fetchone()
    assert (row["salary_min"], row["salary_max"]) == (120000, 150000)


def test_rescan_never_touches_a_hand_corrected_role(conn, jd_dir):
    """infer_company_role() only reads the folder slug, which has lost the title's
    punctuation. Overwriting would orphan the Logseq page, since export_graph.py
    computes filenames fresh from the role text with no rename tracking."""
    jd_id = _insert_jd(conn, jd_dir, role="Senior Test Engineer, Platform (Core)")

    m.scan(str(jd_dir), rescan=True)

    assert conn.execute("SELECT role FROM jds WHERE id=?", (jd_id,)).fetchone()[0] == \
        "Senior Test Engineer, Platform (Core)"


def test_without_rescan_an_existing_row_is_skipped_entirely(conn, jd_dir):
    jd_id = _insert_jd(conn, jd_dir)

    m.scan(str(jd_dir))

    row = conn.execute("SELECT evaluated_at, salary_min FROM jds WHERE id=?", (jd_id,)).fetchone()
    assert row["evaluated_at"] is None
    assert row["salary_min"] is None


def test_a_new_row_is_inserted_for_an_unseen_jd_file(conn, jd_dir):
    m.scan(str(jd_dir))

    row = conn.execute("SELECT company, role, salary_min FROM jds").fetchone()
    assert row["company"] == "Alderaan Systems"
    assert row["role"] == "Senior Test Engineer"
    assert row["salary_min"] == 120000


def test_orphaned_file_already_covered_by_canonical_match_is_skipped(conn, jd_dir):
    """Regression test for the bug TODO.md flagged (surfaced with Commerce,
    2026-07-16): a jds row deleted without also removing its JD file left an
    orphan on disk. A later scan found no file_path match and silently
    inserted a fresh, scoreless duplicate row for the same real company/role
    an existing row already covers. Now: canonical company+role matching
    finds the surviving row and skips the file instead of duplicating it."""
    jd_id = _insert_jd(
        conn, jd_dir,
        file_path=str(jd_dir / "a-different-file-this-row-actually-points-at.md"),
        score=72,
    )

    m.scan(str(jd_dir))

    rows = conn.execute("SELECT id FROM jds").fetchall()
    assert len(rows) == 1, "orphaned file must not create a second jds row"
    assert rows[0]["id"] == jd_id
    # The surviving row's own data (score, file_path) must be untouched --
    # this is a skip, not an adopt/backfill.
    row = conn.execute("SELECT score, file_path FROM jds WHERE id=?", (jd_id,)).fetchone()
    assert row["score"] == 72
    assert row["file_path"] != str(jd_dir / "Alderaan_Systems_Senior_Test_EngineerJobDesc.md")


def test_canonical_match_ignores_case_and_punctuation(conn, jd_dir):
    """alnum_key() normalization must catch a role that differs only in case
    or punctuation from the folder-slug-derived guess, not just an exact
    string match."""
    jd_id = _insert_jd(
        conn, jd_dir,
        role="senior test engineer",  # lowercase; folder infers "Senior Test Engineer"
        file_path=str(jd_dir / "some-other-path.md"),
    )

    m.scan(str(jd_dir))

    assert conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0] == 1
    assert conn.execute("SELECT id FROM jds").fetchone()["id"] == jd_id


def test_canonical_match_does_not_block_a_genuinely_different_company(conn, jd_dir):
    """A row for an unrelated company/role must not suppress a real new
    registration -- the fix should only skip genuine re-discoveries."""
    _insert_jd(
        conn, jd_dir,
        company="Unrelated Corp", role="Totally Different Role",
        file_path=str(jd_dir / "unrelated.md"),
    )

    m.scan(str(jd_dir))

    rows = conn.execute("SELECT company FROM jds ORDER BY id").fetchall()
    assert [r["company"] for r in rows] == ["Unrelated Corp", "Alderaan Systems"]
