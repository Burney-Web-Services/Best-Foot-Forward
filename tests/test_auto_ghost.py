"""
Verify the automatic age-out hook (utils/auto_ghost.py) ghosts stale
applications, leaves active ones alone, logs every change to the shared
audit trail, and is idempotent when called twice in one process lifetime
(simulating CLI start + exit).
"""
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def days_ago(n):
    """An ISO date `n` days before today.

    Staleness in these tests must always be expressed RELATIVE to now, never as
    a literal date. `applied_at="2026-07-20"` was written as a "recent"
    application against a 30-day window, stayed correct for four weeks, and then
    silently became stale on 2026-08-19 — turning two tests red on a date with
    no code change behind it. `ghost_candidates()` compares against
    `date.today()`, so the fixtures have to move with it.
    """
    return (date.today() - timedelta(days=n)).isoformat()


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def seed_application(conn, company, role, applied_at, status="applied", stage=None):
    conn.execute("INSERT INTO jds (company, role) VALUES (?, ?)", (company, role))
    jd_id = conn.execute("SELECT id FROM jds ORDER BY id DESC LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO applications (jd_id, created_at, resume_summary, status, applied_at, stage) "
        "VALUES (?, '2026-01-01', '', ?, ?, ?)",
        (jd_id, status, applied_at, stage),
    )
    conn.commit()
    return conn.execute("SELECT id FROM applications ORDER BY id DESC LIMIT 1").fetchone()[0]


@pytest.fixture
def auto_ghost(tmp_path):
    """auto_ghost wired to a temp log file for each test.

    auto_ghost.py inserts src/best_foot_forward/ onto sys.path and does a bare
    `from utils.audit_log import log_event` — under pytest's dotted import
    (best_foot_forward.utils.auto_ghost), that bare import resolves to a
    SEPARATE module object from `best_foot_forward.utils.audit_log` (two
    distinct sys.modules entries for the same file). Patching the dotted
    module's LOG_PATH would silently no-op here, so patch LOG_PATH on
    log_event's actual __globals__ instead — guaranteed to be the module
    auto_ghost really calls.
    """
    import best_foot_forward.utils.auto_ghost as mod
    log_path = tmp_path / "audit_log.jsonl"
    mod.log_event.__globals__["LOG_PATH"] = str(log_path)
    yield mod, log_path


class TestAutoGhostStaleApplications:
    def test_ghosts_stale_application(self, auto_ghost):
        mod, _ = auto_ghost
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180))  # well past any window
        mod.auto_ghost_stale_applications(conn, days=30)

        row = conn.execute("SELECT status, concluded_at FROM applications WHERE id=?", (app_id,)).fetchone()
        assert row["status"] == "ghosted"
        assert row["concluded_at"] is not None

    def test_leaves_active_stage_untouched(self, auto_ghost):
        mod, _ = auto_ghost
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180), stage="interview_1")
        mod.auto_ghost_stale_applications(conn, days=30)

        row = conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
        assert row["status"] == "applied"

    def test_leaves_recent_application_untouched(self, auto_ghost):
        mod, _ = auto_ghost
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(5))  # inside the window
        mod.auto_ghost_stale_applications(conn, days=30)

        row = conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
        assert row["status"] == "applied"

    def test_returns_ghosted_ids(self, auto_ghost):
        mod, _ = auto_ghost
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180))
        result = mod.auto_ghost_stale_applications(conn, days=30)
        assert result == [app_id]

    def test_logs_the_change(self, auto_ghost):
        mod, log_path = auto_ghost
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180))
        mod.auto_ghost_stale_applications(conn, days=30)

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["actor"] == "auto_ghost"
        assert record["action"] == "ghost"
        assert record["application_id"] == app_id
        assert record["company"] == "Acme"
        assert record["old_status"] == "applied"
        assert record["new_status"] == "ghosted"

    def test_no_log_line_when_nothing_stale(self, auto_ghost):
        mod, log_path = auto_ghost
        conn = make_db()
        seed_application(conn, "Acme", "Engineer", applied_at=days_ago(5))
        mod.auto_ghost_stale_applications(conn, days=30)
        assert not log_path.exists()

    def test_idempotent_second_call_same_process(self, auto_ghost):
        """Simulates CLI startup + shutdown in one process lifetime."""
        mod, log_path = auto_ghost
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180))

        first = mod.auto_ghost_stale_applications(conn, days=30)   # "startup"
        second = mod.auto_ghost_stale_applications(conn, days=30)  # "shutdown"

        assert first == [app_id]
        assert second == []  # already ghosted -> excluded by ghost_candidates' status='applied' filter

        log_lines = log_path.read_text().strip().splitlines()
        assert len(log_lines) == 1  # not duplicated on the second call

    def test_shares_selection_with_ghost_candidates_report(self, auto_ghost):
        """Confirms the shared-source-of-truth requirement: the same rows
        view_ghosts would display are exactly what gets auto-ghosted."""
        mod, _ = auto_ghost
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180))

        candidates_before = ghost_candidates(conn, days=30)
        assert [c["id"] for c in candidates_before] == [app_id]

        mod.auto_ghost_stale_applications(conn, days=30)

        candidates_after = ghost_candidates(conn, days=30)
        assert candidates_after == []  # ghosted row no longer a candidate


class TestGhostCandidates:
    def test_excludes_active_stage(self):
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180), stage="interview_1")
        assert ghost_candidates(conn, days=30) == []

    def test_excludes_non_applied_status(self):
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180), status="rejected")
        assert ghost_candidates(conn, days=30) == []

    def test_includes_stale_no_stage(self):
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180), stage=None)
        candidates = ghost_candidates(conn, days=30)
        assert [c["id"] for c in candidates] == [app_id]

    @pytest.mark.parametrize("stage", [
        "phone_screen", "interview_3", "onsite", "final",
        "final_interview_complete", "offer_received", "offer_accepted",
    ])
    def test_excludes_late_stage_signals(self, stage):
        """Regression: final_interview_complete (and its siblings) were missing
        from the exclusion list, so an application that reached the very end of
        a real interview loop and then went quiet while an offer was pending
        would get silently ghosted by the next auto_ghost run — the exact
        state a real accepted-but-unrecorded offer sits in."""
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        seed_application(conn, "Acme", "Engineer", applied_at=days_ago(180), stage=stage)
        assert ghost_candidates(conn, days=30) == []

    @pytest.mark.parametrize("age_days, expected_candidate", [
        (29, False),   # inside the window
        (30, True),    # exactly at the threshold — inclusive
        (31, True),    # past it
    ])
    def test_threshold_is_inclusive_and_relative_to_today(self, age_days, expected_candidate):
        """Pins the staleness boundary that the hardcoded-date bug slipped across.

        `ghost_candidates()` builds its cutoff from `date.today()`, so an
        application's candidacy depends on how long ago it was applied for, not
        on any absolute date. Before this, the "recent application" fixtures
        used a literal date that was inside the 30-day window when written and
        outside it four weeks later — the suite went red on 2026-08-19 with no
        code change behind it.

        The threshold is inclusive: `date(applied_at) <= today - days`, so
        exactly `days` old counts as stale.
        """
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(age_days))
        candidate_ids = [c["id"] for c in ghost_candidates(conn, days=30)]
        assert (app_id in candidate_ids) is expected_candidate

    def test_window_size_is_honoured(self):
        """The same application is stale or not depending only on `days`."""
        from best_foot_forward.reports.applications import ghost_candidates
        conn = make_db()
        app_id = seed_application(conn, "Acme", "Engineer", applied_at=days_ago(45))
        assert [c["id"] for c in ghost_candidates(conn, days=30)] == [app_id]
        assert ghost_candidates(conn, days=60) == []
