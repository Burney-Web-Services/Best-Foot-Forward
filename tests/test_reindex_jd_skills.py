"""reindex_jd_skills.py: backfill for JDs indexed before the skill-gap-
vocabulary fix. Re-extracts from source text when a file is readable;
re-canonicalizes existing labels in place for imported rows with no file.
Never touches evaluated_at/score/summary/lead_status.
"""
import sqlite3
from pathlib import Path

from best_foot_forward.utils.reindex_jd_skills import reindex_one

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def add_jd(conn, file_path=None, **cols):
    fields = {"company": "Acme", "role": "Engineer", "file_path": file_path,
              "score": 80, "evaluated_at": "2026-07-01T00:00:00", **cols}
    keys = ", ".join(fields)
    conn.execute(f"INSERT INTO jds ({keys}) VALUES ({', '.join('?' * len(fields))})", tuple(fields.values()))
    conn.commit()
    return conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()["id"]


class TestReindexWithReadableFile:
    def test_re_extracts_open_vocabulary_terms(self, tmp_path):
        jd_file = tmp_path / "jd.md"
        jd_file.write_text("Requires production ArgoCD and Istio experience.")
        conn = make_db()
        jd_id = add_jd(conn, file_path=str(jd_file))
        conn.execute("INSERT INTO jd_required_skills (jd_id, skill_label) VALUES (?, 'stale')", (jd_id,))
        conn.commit()

        result = reindex_one(conn, jd_id, str(jd_file))

        assert result["mode"] == "re-extracted"
        labels = {r["canonical_label"] for r in conn.execute(
            "SELECT canonical_label FROM jd_required_skills WHERE jd_id=?", (jd_id,))}
        assert {"ArgoCD", "Istio"} <= labels
        assert "stale" not in {r["skill_label"] for r in conn.execute(
            "SELECT skill_label FROM jd_required_skills WHERE jd_id=?", (jd_id,))}

    def test_never_touches_evaluated_at_or_score(self, tmp_path):
        jd_file = tmp_path / "jd.md"
        jd_file.write_text("Some JD text.")
        conn = make_db()
        jd_id = add_jd(conn, file_path=str(jd_file), score=80, evaluated_at="2026-07-01T00:00:00")

        reindex_one(conn, jd_id, str(jd_file))

        row = conn.execute("SELECT score, evaluated_at FROM jds WHERE id=?", (jd_id,)).fetchone()
        assert row["score"] == 80
        assert row["evaluated_at"] == "2026-07-01T00:00:00"


class TestReindexWithNoFile:
    def test_recanonicalizes_existing_labels_in_place(self):
        """Imported rows (file_path IS NULL, from a secondary's sync_leads
        payload) can't be re-extracted -- no text to read -- but their
        existing labels can still be cleaned up."""
        conn = make_db()
        jd_id = add_jd(conn, file_path=None)
        conn.execute(
            "INSERT INTO jd_required_skills (jd_id, skill_label, source) VALUES (?, ?, 'llm')",
            (jd_id, "python (django strongly preferred)"),
        )
        conn.commit()

        result = reindex_one(conn, jd_id, None)

        assert result["mode"] == "re-canonicalized in place"
        row = conn.execute(
            "SELECT canonical_label FROM jd_required_skills WHERE jd_id=?", (jd_id,)
        ).fetchone()
        assert row["canonical_label"] == "Python"

    def test_missing_file_on_disk_falls_back_to_recanonicalize(self):
        conn = make_db()
        jd_id = add_jd(conn, file_path="/nonexistent/path/jd.md")
        conn.execute("INSERT INTO jd_required_skills (jd_id, skill_label) VALUES (?, 'kubernetes')", (jd_id,))
        conn.commit()

        result = reindex_one(conn, jd_id, "/nonexistent/path/jd.md")

        assert result["mode"] == "re-canonicalized in place"


class TestDryRun:
    def test_dry_run_writes_nothing(self, tmp_path):
        jd_file = tmp_path / "jd.md"
        jd_file.write_text("Requires ArgoCD.")
        conn = make_db()
        jd_id = add_jd(conn, file_path=str(jd_file))

        result = reindex_one(conn, jd_id, str(jd_file), dry_run=True)

        assert result["written"] is False
        assert conn.execute(
            "SELECT COUNT(*) FROM jd_required_skills WHERE jd_id=?", (jd_id,)
        ).fetchone()[0] == 0


class TestFilelessRowsRelinkToTheCurrentProfile:
    """The "my skills never get updated" case. skill_id is written at index
    time, so a row indexed before a skill existed in the profile stays NULL —
    and a row with no file_path (a lead imported over sync_leads) can never be
    re-extracted to fix it. The in-place branch used to carry the stored
    skill_id forward verbatim, so those rows were permanently unclaimed. On a
    real database that was 28 Python mentions.
    """

    def _db_with_skill(self, content="Python, SQL"):
        conn = make_db()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('s-lang', 'Languages', ?)",
                     (content,))
        conn.commit()
        return conn

    def _add_unlinked_term(self, conn, jd_id, label, canonical=None):
        conn.execute(
            "INSERT INTO jd_required_skills (jd_id, skill_label, skill_id, canonical_label, source) "
            "VALUES (?, ?, NULL, ?, 'lexicon')",
            (jd_id, label, canonical or label),
        )
        conn.commit()

    def _skill_ids(self, conn, jd_id):
        return {r["canonical_label"]: r["skill_id"] for r in conn.execute(
            "SELECT canonical_label, skill_id FROM jd_required_skills WHERE jd_id = ?", (jd_id,))}

    def test_links_a_skill_added_to_the_profile_after_the_lead_arrived(self):
        conn = self._db_with_skill()
        jd_id = add_jd(conn, file_path=None)
        self._add_unlinked_term(conn, jd_id, "python", "Python")

        reindex_one(conn, jd_id, None)
        assert self._skill_ids(conn, jd_id)["Python"] == "s-lang"

    def test_links_through_a_slash_joined_profile_entry(self):
        conn = self._db_with_skill("PHP, JavaScript/TypeScript")
        jd_id = add_jd(conn, file_path=None)
        self._add_unlinked_term(conn, jd_id, "javascript", "JavaScript")

        reindex_one(conn, jd_id, None)
        assert self._skill_ids(conn, jd_id)["JavaScript"] == "s-lang"

    def test_leaves_genuinely_unclaimed_skills_unlinked(self):
        conn = self._db_with_skill()
        jd_id = add_jd(conn, file_path=None)
        self._add_unlinked_term(conn, jd_id, "kubernetes", "Kubernetes")

        reindex_one(conn, jd_id, None)
        assert self._skill_ids(conn, jd_id)["Kubernetes"] is None

    def test_does_not_overwrite_an_existing_link(self):
        conn = self._db_with_skill()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('s-other', 'Other', 'Python')")
        jd_id = add_jd(conn, file_path=None)
        conn.execute(
            "INSERT INTO jd_required_skills (jd_id, skill_label, skill_id, canonical_label, source) "
            "VALUES (?, 'python', 's-other', 'Python', 'profile')", (jd_id,))
        conn.commit()

        reindex_one(conn, jd_id, None)
        assert self._skill_ids(conn, jd_id)["Python"] == "s-other"

    def test_dry_run_writes_nothing(self):
        conn = self._db_with_skill()
        jd_id = add_jd(conn, file_path=None)
        self._add_unlinked_term(conn, jd_id, "python", "Python")

        reindex_one(conn, jd_id, None, dry_run=True)
        assert self._skill_ids(conn, jd_id)["Python"] is None
