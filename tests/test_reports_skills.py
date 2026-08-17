"""reports/skills.py: canonical-label grouping (so equivalent JD mentions
aggregate instead of each staying a singleton), the vocabulary_health() check
(the only thing distinguishing "no gaps" from "gaps filtered out before the
query ran"), and the seen-once tail for sub-threshold gaps.
"""
import sqlite3
from pathlib import Path

from best_foot_forward.reports.skills import (
    _GROUP_KEY,
    view_frequency,
    view_gaps,
    vocabulary_health,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def add_jd(conn, company="Acme", role="Engineer", file_path="/tmp/jd.md"):
    cur = conn.execute("INSERT INTO jds (company, role, file_path) VALUES (?, ?, ?)", (company, role, file_path))
    conn.commit()
    return cur.lastrowid


def add_required_skill(conn, jd_id, skill_label, canonical_label=None, source="lexicon", skill_id=None):
    conn.execute(
        "INSERT INTO jd_required_skills (jd_id, skill_label, canonical_label, source, skill_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (jd_id, skill_label, canonical_label, source, skill_id),
    )
    conn.commit()


class TestVocabularyHealth:
    def test_empty_db_reports_zero_total(self):
        conn = make_db()
        health = vocabulary_health(conn)
        assert health["total"] == 0
        assert health["outside_fraction"] is None

    def test_all_terms_in_profile_is_a_closed_vocabulary(self):
        """The exact shape of the bug: every indexed term already in the profile."""
        conn = make_db()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('py', 'Python', 'Python, Django')")
        conn.commit()
        jd_id = add_jd(conn)
        add_required_skill(conn, jd_id, "python", canonical_label="Python")

        health = vocabulary_health(conn)
        assert health["total"] == 1
        assert health["outside"] == 0
        assert health["outside_fraction"] == 0.0

    def test_terms_outside_profile_raise_the_outside_fraction(self):
        conn = make_db()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('py', 'Python', 'Python')")
        conn.commit()
        jd_id = add_jd(conn)
        add_required_skill(conn, jd_id, "python", canonical_label="Python")
        add_required_skill(conn, jd_id, "argocd", canonical_label="ArgoCD")

        health = vocabulary_health(conn)
        assert health["total"] == 2
        assert health["outside"] == 1
        assert health["outside_fraction"] == 0.5


class TestViewGapsGrouping:
    def test_canonical_label_collapses_equivalent_mentions(self, capsys):
        """Two JDs mentioning 'k8s' and 'kubernetes' respectively must
        aggregate into one demand count of 2, not stay two singletons a
        demand>=2 filter would throw away."""
        conn = make_db()
        jd1 = add_jd(conn, company="A", file_path="/tmp/a.md")
        jd2 = add_jd(conn, company="B", file_path="/tmp/b.md")
        add_required_skill(conn, jd1, "k8s", canonical_label="Kubernetes")
        add_required_skill(conn, jd2, "kubernetes", canonical_label="Kubernetes")

        view_gaps(conn)
        out = capsys.readouterr().out
        assert "Kubernetes" in out
        assert "2 JDs" in out

    def test_seen_once_tail_is_not_silently_dropped(self, capsys):
        """A requirement seen in exactly one JD is still a real gap -- must
        show up in the 'seen once' section, not vanish entirely."""
        conn = make_db()
        jd_id = add_jd(conn)
        add_required_skill(conn, jd_id, "terragrunt", canonical_label="Terragrunt")

        view_gaps(conn)
        out = capsys.readouterr().out
        assert "Terragrunt" in out
        assert "Seen once" in out

    def test_no_gaps_message_when_nothing_indexed(self, capsys):
        conn = make_db()
        view_gaps(conn)
        out = capsys.readouterr().out
        assert "No significant gaps found." in out

    def test_health_warning_shown_for_closed_vocabulary(self, capsys):
        conn = make_db()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('py', 'Python', 'Python')")
        conn.commit()
        jd_id = add_jd(conn)
        add_required_skill(conn, jd_id, "python", canonical_label="Python")

        view_gaps(conn)
        out = capsys.readouterr().out
        assert "looks closed" in out


class TestViewFrequencyGrouping:
    def test_groups_by_canonical_label(self, capsys):
        conn = make_db()
        jd1 = add_jd(conn, company="A", file_path="/tmp/a.md")
        jd2 = add_jd(conn, company="B", file_path="/tmp/b.md")
        add_required_skill(conn, jd1, "k8s", canonical_label="Kubernetes")
        add_required_skill(conn, jd2, "kubernetes", canonical_label="Kubernetes")

        view_frequency(conn)
        out = capsys.readouterr().out
        assert out.count("Kubernetes") == 1
        assert "2 JDs" in out

    def test_taxonomy_check_is_true_when_any_row_in_the_group_matched(self, capsys):
        """A skill matched to the user's library in one JD but not another must
        still read as "in your skills". The report groups rows, so this only
        holds if the query aggregates skill_id with MAX() rather than letting
        SQLite pick a bare column from an arbitrary row in the group."""
        conn = make_db()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('py', 'Python', 'Python')")
        conn.commit()
        jd1 = add_jd(conn, company="A", file_path="/tmp/a.md")
        jd2 = add_jd(conn, company="B", file_path="/tmp/b.md")
        # Same canonical group, only one row carries the taxonomy match.
        add_required_skill(conn, jd1, "python", canonical_label="Python", skill_id=None)
        add_required_skill(conn, jd2, "python3", canonical_label="Python", skill_id="py")

        view_frequency(conn)
        out = capsys.readouterr().out
        python_line = next(ln for ln in out.splitlines() if "Python" in ln and "JDs" in ln)
        assert "[✓]" in python_line, f"expected a taxonomy match, got: {python_line!r}"

    def test_legend_explains_what_the_checkmark_means(self, capsys):
        conn = make_db()
        view_frequency(conn)
        out = capsys.readouterr().out
        assert "your own skills library" in out


class TestWebReportParity:
    """The /web "Top Demanded Skills" view is meant to be the same report as the
    CLI's. It shipped with its own hand-written copy of the query that had drifted:
    it grouped on the raw label (undoing alias canonicalization, which split AWS
    across 5 rows and Python across 8 on a real database) and selected a bare
    skill_id (an arbitrary row's value, so the taxonomy checkmark was a coin flip
    for any skill matched in some JDs but not others).

    Rather than assert on prose, this runs the JS file's actual SQL against the
    same fixture as the Python report and requires identical results.
    """

    PLUGIN = Path(__file__).resolve().parents[1] / "web" / "mystery" / "plugins" / "bff-reports" / "index.js"

    def _extract_sql(self):
        import re
        src = self.PLUGIN.read_text()
        route = src.split("router.get('/skill-frequency'", 1)
        assert len(route) == 2, "skill-frequency route not found in the plugin"
        m = re.search(r"`(\s*SELECT.*?FROM jd_required_skills.*?)`", route[1], re.S)
        assert m, "no SQL template literal found in the skill-frequency route"
        return m.group(1)

    def _fixture(self):
        conn = make_db()
        conn.execute("INSERT INTO skills (id, label, content) VALUES ('py', 'Python', 'Python')")
        conn.commit()
        jd1 = add_jd(conn, company="A", file_path="/tmp/a.md")
        jd2 = add_jd(conn, company="B", file_path="/tmp/b.md")
        jd3 = add_jd(conn, company="C", file_path="/tmp/c.md")
        # Alias split + a group where only one row carries the taxonomy match.
        add_required_skill(conn, jd1, "python", canonical_label="Python", skill_id=None)
        add_required_skill(conn, jd2, "python3", canonical_label="Python", skill_id="py")
        add_required_skill(conn, jd3, "terraform", canonical_label="Terraform", skill_id=None)
        return conn

    def test_web_sql_groups_aliases_and_aggregates_the_taxonomy_flag(self):
        conn = self._fixture()
        rows = conn.execute(self._extract_sql().replace("LIMIT 30", "LIMIT 30")).fetchall()
        by_group = {r["grp"]: r for r in rows}

        assert "Python" in by_group, f"aliases did not aggregate: {list(by_group)}"
        assert by_group["Python"]["demand"] == 2
        assert by_group["Python"]["skill_id"] == "py", (
            "taxonomy flag must be non-NULL when any row in the group matched"
        )
        assert by_group["Terraform"]["skill_id"] is None

    def test_web_sql_matches_the_python_report_row_for_row(self, capsys):
        conn = self._fixture()
        web = [
            (r["grp"], r["demand"], r["skill_id"] is not None)
            for r in conn.execute(self._extract_sql()).fetchall()
        ]
        cli = [
            (r["grp"], r["demand"], r["skill_id"] is not None)
            for r in conn.execute(f"""
                SELECT MAX(skill_label) as skill_label, {_GROUP_KEY} as grp,
                       COUNT(*) as demand, MAX(skill_id) as skill_id
                FROM jd_required_skills
                GROUP BY grp
                ORDER BY demand DESC, grp
                LIMIT 30
            """).fetchall()
        ]
        assert web == cli, f"web report drifted from the CLI\n  web: {web}\n  cli: {cli}"
