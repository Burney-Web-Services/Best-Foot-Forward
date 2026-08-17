"""Aggregation over the declined pile: category tallies, the signal/choice split,
and score banding.
"""
import sqlite3
from pathlib import Path

from best_foot_forward.reports.applications import (
    SCORE_BANDS,
    _band,
    _midpoint,
    decline_patterns,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def add_jd(conn, company="Acme", role="QA Engineer", lead_status="declined",
           score=70, category=None, salary_min=None, salary_max=None):
    conn.execute(
        "INSERT INTO jds (company, role, lead_status, score, decline_category, "
        "salary_min, salary_max) VALUES (?,?,?,?,?,?,?)",
        (company, role, lead_status, score, category, salary_min, salary_max),
    )
    conn.commit()
    return conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()["id"]


def add_application(conn, jd_id):
    conn.execute(
        "INSERT INTO applications (jd_id, created_at, resume_summary) VALUES (?,?,?)",
        (jd_id, "2026-07-01T09:00:00", "summary"),
    )
    conn.commit()


def test_empty_pile_reports_zero():
    d = decline_patterns(make_db())
    assert d["total"] == 0
    assert d["by_category"] == {}


def test_categories_are_counted_and_averaged():
    conn = make_db()
    add_jd(conn, "A", score=60, category="stack", salary_min=100_000, salary_max=200_000)
    add_jd(conn, "B", score=80, category="stack", salary_min=100_000, salary_max=100_000)
    add_jd(conn, "C", score=50, category="domain")

    d = decline_patterns(conn)
    assert d["total"] == 3
    assert d["by_category"]["stack"]["count"] == 2
    assert sum(d["by_category"]["stack"]["scores"]) / 2 == 70
    # Midpoints: 150K and 100K.
    assert sum(d["by_category"]["stack"]["salaries"]) / 2 == 125_000
    # A lead with no salary contributes a count but no salary datapoint, rather
    # than dragging the average toward zero.
    assert d["by_category"]["domain"]["salaries"] == []


def test_strategy_declines_are_excluded_from_market_signal():
    """The whole point of keeping 'strategy' separate from 'other': a decline that
    was a pipeline choice says nothing about the roles on offer."""
    conn = make_db()
    add_jd(conn, "A", category="stack")
    add_jd(conn, "B", category="domain")
    add_jd(conn, "C", category="strategy")
    add_jd(conn, "D", category="strategy")

    d = decline_patterns(conn)
    assert d["total"] == 4
    assert d["signal"] == 2
    assert d["strategy"] == 2


def test_uncategorized_counted_but_not_as_signal():
    conn = make_db()
    add_jd(conn, "A", category="stack")
    add_jd(conn, "B", category=None)

    d = decline_patterns(conn)
    assert d["total"] == 2
    assert d["uncategorized"] == 1
    assert d["signal"] == 1  # the uncategorized one is unknown, not signal


def test_repeat_companies_are_tallied():
    conn = make_db()
    add_jd(conn, "Mercury", role="Test Engineer II", category="level")
    add_jd(conn, "Mercury", role="Staff Test Engineer", category="strategy")
    add_jd(conn, "Affirm", category="stack")

    d = decline_patterns(conn)
    assert d["by_company"] == {"Mercury": 2, "Affirm": 1}


def test_bands_split_declined_from_applied():
    conn = make_db()
    add_jd(conn, "Declined80", score=85, category="stack")
    add_jd(conn, "Declined60", score=65, category="stack")
    applied = add_jd(conn, "Applied", lead_status="applied", score=88)
    add_application(conn, applied)

    d = decline_patterns(conn)
    assert d["declined_bands"] == {"80+": 1, "60–69": 1}
    assert d["applied_bands"] == {"80+": 1}


def test_applied_band_keys_off_the_application_not_lead_status():
    """A lead can sit at 'approved' with a real application row (the tvScientific
    case), so 'what did I actually pursue' has to come from the application."""
    conn = make_db()
    jd = add_jd(conn, "tvSci", lead_status="approved", score=85)
    add_application(conn, jd)

    assert decline_patterns(conn)["applied_bands"] == {"80+": 1}


def test_unscored_leads_are_left_out_of_bands():
    conn = make_db()
    add_jd(conn, "NoScore", score=None, category="stack")

    d = decline_patterns(conn)
    assert d["total"] == 1          # still counted as a decline
    assert d["declined_bands"] == {}  # but unbandable


def test_band_boundaries_are_contiguous_and_exclusive():
    assert _band(80) == "80+"
    assert _band(79) == "70–79"
    assert _band(70) == "70–79"
    assert _band(59) == "<60"
    assert _band(100) == "80+"
    assert _band(None) is None
    # Every score 0-100 lands in exactly one band.
    assert all(_band(s) is not None for s in range(0, 101))


def test_midpoint_handles_a_one_sided_range():
    assert _midpoint(100_000, 200_000) == 150_000
    assert _midpoint(100_000, None) == 100_000
    assert _midpoint(None, 200_000) == 200_000
    assert _midpoint(None, None) is None


def test_score_bands_cover_the_full_range_without_gaps():
    lows = [lo for _, lo, _ in SCORE_BANDS]
    his = [hi for _, _, hi in SCORE_BANDS]
    assert min(lows) == 0
    assert max(his) == 101
