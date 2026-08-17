"""Tier 1 assertions for the UAT harness (see run_uat.sh's docstring and
~/.claude/plans/i-put-an-example-groovy-zephyr.md). Does NOT drive any
`claude -p` calls itself and costs nothing to run -- it only inspects
whatever run_uat.sh already left behind at $BFF_DATA_DIR.

Usage:
    BFF_DATA_DIR=/tmp/uat-... tests/uat/run_uat.sh
    BFF_DATA_DIR=/tmp/uat-... .venv/bin/python3 -m pytest tests/uat/test_uat_pipeline.py -v

Every test skips (not fails) if BFF_DATA_DIR isn't set or its DB isn't
there yet -- this file participates in `pytest tests/` without demanding a
live run every time the rest of the suite runs.
"""
import glob
import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

import sys  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "src"))
from best_foot_forward.utils.save_lead_jd import jd_paths  # noqa: E402

_DATA_DIR = os.environ.get("BFF_DATA_DIR")
_DB_PATH = Path(_DATA_DIR) / "best_foot_forward.db" if _DATA_DIR else None

pytestmark = pytest.mark.skipif(
    not _DATA_DIR or not _DB_PATH.exists(),
    reason="BFF_DATA_DIR not set or its DB doesn't exist yet -- run tests/uat/run_uat.sh first",
)

# Only the persona's own synthetic contact details are allowed to appear --
# anything else email/phone-shaped is real PII that leaked into a fictional
# run, which CLAUDE.md's BFF_UAT section calls a bug worth stopping for.
ALLOWED_EMAIL = "leia.organa@example.com"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
ALLOWED_PHONE = "(555) 555-1212"


@pytest.fixture
def conn():
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_real_repo_data_and_memory_untouched():
    assert Path(_DATA_DIR).resolve() != (REPO_ROOT / "data").resolve()


def test_leia_fixture_loaded(conn):
    companies = {r[0] for r in conn.execute("SELECT DISTINCT company FROM jds")}
    # The 6 original companies from examples/leia-organa/applications/. Not
    # Coruscant Systems Group (the 7th, added 2026-08-16) -- its score gets
    # live-overwritten by this same run_uat.sh pass's /evaluate-job call, so
    # it's asserted separately by test_gap_posting_scored below rather than
    # pinned here alongside the six whose scores must stay fixed.
    assert {
        "Chandrila Data Collective", "Kuat Design Systems",
        "Nar Shaddaa Exchange Group", "Obroa-skai Analytics",
        "Scarif Identity Systems", "Theed Agent Systems",
    } <= companies


def test_gap_posting_scored(conn):
    row = conn.execute(
        "SELECT id, score, role FROM jds WHERE company = 'Coruscant Systems Group'"
    ).fetchone()
    assert row is not None, "gap_posting.txt was never evaluated into the DB"
    assert row["score"] is not None


def test_gap_posting_names_the_real_gaps(conn):
    """The direct Bug-1-class regression check at the live /evaluate-job
    level (test_load_example_data.py covers the loader path separately):
    GCP/ArgoCD/Snowflake are named in gap_posting.txt and genuinely absent
    from Leia's skills -- if evaluate-job's vocabulary were circular again,
    these would silently fail to get indexed."""
    jd = conn.execute(
        "SELECT id FROM jds WHERE company = 'Coruscant Systems Group'"
    ).fetchone()
    assert jd is not None
    canonicals = {
        r[0] for r in conn.execute(
            "SELECT canonical_label FROM jd_required_skills WHERE jd_id = ? "
            "AND canonical_label IS NOT NULL",
            (jd["id"],),
        )
    }
    missing = {"GCP", "ArgoCD", "Snowflake"} - canonicals
    assert not missing, f"expected gap terms not indexed: {missing} (indexed: {canonicals})"


def test_no_orphaned_jd_required_skills_rows(conn):
    orphans = conn.execute(
        "SELECT COUNT(*) FROM jd_required_skills s "
        "LEFT JOIN jds j ON j.id = s.jd_id WHERE j.id IS NULL"
    ).fetchone()[0]
    assert orphans == 0


def _iter_text_blobs():
    reply_path = Path(_DATA_DIR) / "evaluate_job_reply.json"
    if reply_path.exists():
        with open(reply_path, encoding="utf-8") as f:
            payload = json.load(f)
        # .get(..., "") only covers a missing key -- an aborted/errored call
        # still has the "result" key present with value null.
        yield "evaluate_job_reply.json", payload.get("result") or ""

    conn_ = sqlite3.connect(_DB_PATH)
    conn_.row_factory = sqlite3.Row
    for row in conn_.execute("SELECT company, role, summary FROM jds"):
        yield f"jds({row['company']}/{row['role']})", row["summary"] or ""
    conn_.close()


def test_no_unexpected_pii():
    for source, text in _iter_text_blobs():
        for match in EMAIL_RE.findall(text):
            assert match == ALLOWED_EMAIL, f"unexpected email {match!r} in {source}"
        for match in PHONE_RE.findall(text):
            assert match in ALLOWED_PHONE, f"unexpected phone {match!r} in {source}"


def test_no_fixed_track_enum_leakage(conn):
    """Bug 4's regression check: track labels should be freeform (per
    ADR-0009), not silently constrained back to the stale
    engineer|manager|executive enum onboard.md used to hardcode."""
    tracks = {r[0] for r in conn.execute("SELECT DISTINCT track FROM bullet_tracks")}
    assert tracks, "no tracks indexed at all -- fixture load likely failed upstream"


# --- The 6 real Leia postings (examples/leia-organa/applications/) ---
#
# These load for free during run_uat.sh's seeding step (load_example_data.py
# replays each jd_eval.json through save_lead_jd.py -- no live claude -p call
# involved), but until now nothing beyond company-name presence
# (test_leia_fixture_loaded) actually checked what landed. The scores below
# are the real /evaluate-job output from examples/leia-organa/README.md's
# provenance table -- pinning them here means a future load_example_data.py
# or save_lead_jd.py regression that silently drops or reorders a score
# shows up as a UAT failure instead of nothing.
LEIA_KNOWN_SCORES = {
    "Obroa-skai Analytics": 82,
    "Scarif Identity Systems": 81,
    "Nar Shaddaa Exchange Group": 76,
    "Kuat Design Systems": 65,
    "Chandrila Data Collective": 59,
    "Theed Agent Systems": 58,
}

# The two companies whose fixture directories carry resume_data.py/letter_data.py
# (the only two of the six actually tailored, per README.md's outcomes table).
LEIA_TAILORED = {
    "Obroa-skai Analytics": "Staff Platform Engineer, Cloud Developer Experience",
    "Scarif Identity Systems": "Senior / Staff Site Reliability, Platform Engineering",
}


def test_leia_fixture_scores_match_known_values(conn):
    for company, expected_score in LEIA_KNOWN_SCORES.items():
        row = conn.execute(
            "SELECT score FROM jds WHERE company = ?", (company,)
        ).fetchone()
        assert row is not None, f"{company} missing from jds entirely"
        assert row["score"] == expected_score, (
            f"{company}: expected score {expected_score}, got {row['score']!r} "
            "-- either the fixture's jd_eval.json changed or load_example_data.py "
            "regressed"
        )


def test_no_duplicate_jds_rows_for_leia_companies(conn):
    """Regression check for the exact bug fixed 2026-08-15 (see
    examples/leia-organa/README.md's 'Known gaps' section): a tailored
    fixture used to land as two jds rows (one from the loader's own insert,
    one orphaned by generate_resume.py reading JD_FILE_PATH back out under a
    differently-formatted path). Each of the six companies must land as
    exactly one row."""
    for company in LEIA_KNOWN_SCORES:
        count = conn.execute(
            "SELECT COUNT(*) FROM jds WHERE company = ?", (company,)
        ).fetchone()[0]
        assert count == 1, f"{company}: expected exactly 1 jds row, found {count}"


def test_leia_fixture_required_skills_indexed(conn):
    """Each real posting's jd_eval.json ships a required_skills list, passed
    through save_lead_jd.py --skills-json during load. If this comes back
    empty for any of the six, the loader's skills-indexing leg silently
    broke (the same failure class Bug 1's circular-vocabulary fix exists to
    prevent -- see test_load_example_data.py and test_jd_skills.py for the
    non-UAT-gated regression coverage of that bug specifically)."""
    for company in LEIA_KNOWN_SCORES:
        jd = conn.execute(
            "SELECT id FROM jds WHERE company = ?", (company,)
        ).fetchone()
        assert jd is not None
        n = conn.execute(
            "SELECT COUNT(*) FROM jd_required_skills WHERE jd_id = ?", (jd["id"],)
        ).fetchone()[0]
        assert n > 0, f"{company}: no jd_required_skills rows indexed"


def test_leia_tailored_applications_generated(conn):
    """Obroa-skai and Scarif are the two postings in the fixture that carry
    resume_data.py/letter_data.py -- load_example_data.py should have driven
    them all the way through generate_resume.py/generate_letter.py/
    track_application.py, landing an applications row and real .docx files
    on disk, not just a scored jds row."""
    for company, role in LEIA_TAILORED.items():
        app = conn.execute(
            "SELECT a.id, a.status FROM applications a "
            "JOIN jds j ON j.id = a.jd_id WHERE j.company = ?",
            (company,),
        ).fetchone()
        assert app is not None, f"{company}: no applications row (tailoring didn't run?)"
        assert app["status"] == "applied"

        asset_dir, _ = jd_paths(company, role)
        docx_files = glob.glob(os.path.join(asset_dir, "*.docx"))
        assert docx_files, f"{company}: no .docx files generated under {asset_dir}"


def test_leia_nar_shaddaa_declined(conn):
    """Regression check for the 2026-08-16 loader extension (see
    examples/leia-organa/README.md's 'Known gaps' section): Nar Shaddaa's
    real decline outcome must replay through triage_lead.set_lead_status(),
    not sit unread in jd_eval.json's _not_yet_loadable key."""
    row = conn.execute(
        "SELECT lead_status, decline_category, decline_reason, lead_decided_at "
        "FROM jds WHERE company = 'Nar Shaddaa Exchange Group'"
    ).fetchone()
    assert row is not None
    assert row["lead_status"] == "declined"
    assert row["decline_category"] == "domain"
    assert row["decline_reason"], "decline_reason should carry her actual words"
    assert row["lead_decided_at"] == "2026-08-14"


def test_leia_obroaskai_screen_stage_and_contact(conn):
    """Same loader extension: Obroa-skai's real screening state (stage +
    scheduled-interview contact) must replay, not default to stage='application'
    with no contact row."""
    app = conn.execute(
        "SELECT a.stage FROM applications a JOIN jds j ON j.id = a.jd_id "
        "WHERE j.company = 'Obroa-skai Analytics'"
    ).fetchone()
    assert app is not None
    assert app["stage"] == "screen"

    contact = conn.execute(
        "SELECT c.name, c.interview_date, c.interview_stage FROM contacts c "
        "JOIN jds j ON j.id = c.jd_id WHERE j.company = 'Obroa-skai Analytics'"
    ).fetchone()
    assert contact is not None
    assert contact["name"] == "Toman Feyn"
    assert contact["interview_date"] == "2026-08-21"


def test_leia_stories_loaded(conn):
    """stories.json ships one real /star-story capture (the Corellian
    reliability story) -- confirms _load_stories() actually ran and its
    theme/bullet-link join tables populated, not just the top-level row."""
    story = conn.execute("SELECT id FROM stories LIMIT 1").fetchone()
    assert story is not None, "no stories loaded -- stories.json fixture likely didn't run"
    themes = conn.execute(
        "SELECT COUNT(*) FROM story_themes WHERE story_id = ?", (story["id"],)
    ).fetchone()[0]
    assert themes > 0, "story loaded but no story_themes rows -- theme join likely broke"
