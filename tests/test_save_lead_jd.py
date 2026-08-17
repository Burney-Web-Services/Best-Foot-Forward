"""Eval-time JD capture: writes the file once, indexes salary + skills, and leaves
the scoring columns alone.
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils import save_lead_jd as m

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"

JD_TEXT = """Senior Test Engineer

We need strong Selenium and Java experience, plus Jenkins for CI.
Compensation: $120,000 - $150,000 depending on location.
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_PATH.read_text())
    # A tiny skills taxonomy so extract_skills has terms to match.
    for sid, label in [("sel", "Selenium"), ("java", "Java"), ("jen", "Jenkins")]:
        c.execute("INSERT INTO skills (id, label, content) VALUES (?,?,?)", (sid, label, label))
    c.commit()
    return c


@pytest.fixture(autouse=True)
def asset_base(tmp_path, monkeypatch):
    """Redirect writes into tmp_path so tests never touch the real graph."""
    base = tmp_path / "assets"
    monkeypatch.setattr(m, "ASSET_BASE", str(base))
    monkeypatch.setattr(m, "resolve_jd_path", lambda p: p)
    monkeypatch.setattr(m, "register_file", lambda *a, **k: 1)
    return base


def test_writes_the_jd_file_with_a_property_block(conn, asset_base):
    r = m.save_lead_jd(conn, "Affirm", "Software Engineer II", JD_TEXT, url="https://x.test/1")

    body = Path(r["file_path"]).read_text()
    assert body.startswith("type:: #JobDescription")
    assert "company:: [[Affirm]]" in body
    assert "role:: Software Engineer II" in body
    assert "url:: https://x.test/1" in body
    assert "Selenium" in body  # posting text preserved verbatim
    assert r["wrote_file"] is True


def test_filename_and_directory_carry_the_role_slug(conn):
    """Two roles at one company must not share a bare {Company}JobDesc.md: Logseq
    indexes every .md by filename alone and treats the collision as a duplicate page."""
    _, a = m.jd_paths("Mercury", "Test Engineer II")
    _, b = m.jd_paths("Mercury", "Staff Test Engineer")
    assert a != b
    assert a.endswith("Mercury_Test_Engineer_IIJobDesc.md")
    assert "Test_Engineer_II" in a


def test_role_slug_is_computed_not_hand_derived(conn):
    """slugify collapses a spaced hyphen and keeps an internal one; a hand
    derivation gets this wrong, and a one-character difference silently duplicates
    the jds row."""
    _, p = m.jd_paths("SitusAMC", "Quality Assurance - Playwright")
    assert "Quality_Assurance_Playwright" in p


def test_salary_and_skills_are_indexed(conn):
    r = m.save_lead_jd(conn, "Acme", "Senior Test Engineer", JD_TEXT)

    assert (r["salary_min"], r["salary_max"]) == (120000, 150000)
    row = conn.execute("SELECT salary_min, salary_max FROM jds WHERE id=?", (r["jd_id"],)).fetchone()
    assert (row["salary_min"], row["salary_max"]) == (120000, 150000)

    # Labels are stored lowercased, matching every existing jd_required_skills row.
    labels = {x["skill_label"] for x in conn.execute(
        "SELECT skill_label FROM jd_required_skills WHERE jd_id=?", (r["jd_id"],))}
    assert {"selenium", "java", "jenkins"} <= labels


def test_open_vocabulary_extracts_beyond_the_profile(conn):
    """The Bug 1 regression, at the save_lead_jd integration level: a JD
    naming a skill nowhere in the user's profile must still get indexed, via
    the shipped lexicon."""
    r = m.save_lead_jd(conn, "Acme", "Platform Engineer",
                       "Requires production ArgoCD and Istio experience.")
    canonicals = {x["canonical_label"] for x in conn.execute(
        "SELECT canonical_label FROM jd_required_skills WHERE jd_id=?", (r["jd_id"],))}
    assert {"ArgoCD", "Istio"} <= canonicals


def test_skills_json_llm_labels_are_unioned_in(conn):
    r = m.save_lead_jd(conn, "Acme", "Platform Engineer",
                       "Some JD text a lexicon match alone wouldn't fully cover.",
                       llm_labels=["Terragrunt", "Crossplane"])
    canonicals = {x["canonical_label"] for x in conn.execute(
        "SELECT canonical_label, source FROM jd_required_skills WHERE jd_id=?", (r["jd_id"],))}
    assert {"Terragrunt", "Crossplane"} <= canonicals
    sources = {x["source"] for x in conn.execute(
        "SELECT source FROM jd_required_skills WHERE jd_id=? AND canonical_label='Terragrunt'", (r["jd_id"],))}
    assert sources == {"llm"}


def test_scoring_columns_are_never_touched(conn):
    """evaluate-job owns score/summary/evaluated_at. This is the trap that ruled
    out calling scan_jds --rescan, which restamps evaluated_at with the scan time."""
    conn.execute(
        "INSERT INTO jds (company, role, file_path, score, summary, evaluated_at) "
        "VALUES ('Acme','Senior Test Engineer',NULL,72,'the fit analysis','2026-08-01T09:00:00')")
    conn.commit()

    m.save_lead_jd(conn, "Acme", "Senior Test Engineer", JD_TEXT)

    row = conn.execute("SELECT score, summary, evaluated_at FROM jds").fetchone()
    assert row["score"] == 72
    assert row["summary"] == "the fit analysis"
    assert row["evaluated_at"] == "2026-08-01T09:00:00"


def test_adopts_the_evaluate_job_stub_rather_than_duplicating_it(conn):
    conn.execute("INSERT INTO jds (company, role, lead_status) VALUES ('Acme','Senior Test Engineer','pending')")
    conn.commit()

    r = m.save_lead_jd(conn, "Acme", "Senior Test Engineer", JD_TEXT)

    assert r["action"] == "adopted"
    assert conn.execute("SELECT COUNT(*) FROM jds").fetchone()[0] == 1


def test_a_new_lead_lands_pending_not_approved(conn):
    """The schema DEFAULT is still 'approved', so a row created here would skip the
    triage inbox and count as a lead the seeker had already said yes to."""
    r = m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT)

    assert r["action"] == "created"
    assert conn.execute("SELECT lead_status FROM jds WHERE id=?", (r["jd_id"],)).fetchone()[0] == "pending"


@pytest.mark.parametrize("existing", ["approved", "declined", "applied"])
def test_an_already_triaged_lead_keeps_its_status(conn, existing):
    """Re-saving the JD for a lead that was already decided must not drag it back
    to the inbox — the same rule the score UPDATE follows."""
    conn.execute("INSERT INTO jds (company, role, lead_status) VALUES ('Acme','QA Engineer',?)", (existing,))
    conn.commit()

    r = m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT)

    assert r["action"] == "adopted"
    assert conn.execute("SELECT lead_status FROM jds WHERE id=?", (r["jd_id"],)).fetchone()[0] == existing


def test_a_hand_set_salary_is_not_clobbered(conn):
    """The Inductive Automation case: the range lived in a sidebar widget, not the
    body, and was set by hand. A later parse that finds nothing must not blank it."""
    r = m.save_lead_jd(conn, "Acme", "QA Engineer", "No pay information here at all.")
    conn.execute("UPDATE jds SET salary_min=125000, salary_max=143000 WHERE id=?", (r["jd_id"],))
    conn.commit()

    m.save_lead_jd(conn, "Acme", "QA Engineer", "Still no pay information.", overwrite=True)

    row = conn.execute("SELECT salary_min, salary_max FROM jds WHERE id=?", (r["jd_id"],)).fetchone()
    assert (row["salary_min"], row["salary_max"]) == (125000, 143000)


def test_an_existing_file_is_kept_and_indexed_not_overwritten(conn, asset_base):
    m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT)
    r = m.save_lead_jd(conn, "Acme", "QA Engineer", "totally different text")

    assert r["wrote_file"] is False
    assert r["file_existed"] is True
    assert "Selenium" in Path(r["file_path"]).read_text()


def test_overwrite_replaces_the_file(conn):
    m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT)
    r = m.save_lead_jd(conn, "Acme", "QA Engineer", "fresh posting text", overwrite=True)

    assert r["wrote_file"] is True
    assert "fresh posting text" in Path(r["file_path"]).read_text()


def test_reindexing_does_not_accumulate_duplicate_skill_rows(conn):
    r = m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT)
    first = conn.execute("SELECT COUNT(*) FROM jd_required_skills WHERE jd_id=?", (r["jd_id"],)).fetchone()[0]
    m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT, overwrite=True)
    again = conn.execute("SELECT COUNT(*) FROM jd_required_skills WHERE jd_id=?", (r["jd_id"],)).fetchone()[0]

    assert first == again


def test_url_is_recorded_but_never_replaced(conn):
    r = m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT, url="https://x.test/first")
    m.save_lead_jd(conn, "Acme", "QA Engineer", JD_TEXT, url="https://x.test/second")

    url = conn.execute("SELECT url FROM jds WHERE id=?", (r["jd_id"],)).fetchone()["url"]
    assert url == "https://x.test/first"
