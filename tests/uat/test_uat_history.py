"""Tier 0 (free, no live call) tests for tests/uat/uat_history.py's
record/report round-trip. Always uses a temp DB path -- never touches the
real tracked tests/uat/uat_history.db."""
import json
import sqlite3
from pathlib import Path

import pytest

from tests.uat import uat_history


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "uat_history_test.db"


def test_record_creates_schema_and_row(db_path):
    row_id = uat_history.record_run(
        db_path,
        harness="run_uat",
        fixture="Coruscant Systems Group",
        outer_model="sonnet",
        score=61,
        cost_usd=1.62,
        duration_ms=143000,
        num_turns=9,
        gaps_expected=["GCP", "ArgoCD", "Snowflake"],
        gaps_named=["GCP", "ArgoCD"],
        git_sha="abc1234",
    )
    assert row_id == 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (row_id,)).fetchone()
    conn.close()

    assert row["fixture"] == "Coruscant Systems Group"
    assert row["score"] == 61
    assert row["is_error"] == 0
    assert json.loads(row["gaps_expected"]) == ["GCP", "ArgoCD", "Snowflake"]
    assert json.loads(row["gaps_named"]) == ["GCP", "ArgoCD"]
    assert row["git_sha"] == "abc1234"


def test_record_error_run(db_path):
    row_id = uat_history.record_run(
        db_path, harness="compare_eval_models", fixture="X", eval_model="haiku",
        is_error=True, git_sha="deadbee",
    )
    rows = uat_history.report_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["is_error"] == 1
    assert rows[0]["id"] == row_id


def test_report_filters_by_fixture(db_path):
    uat_history.record_run(db_path, harness="run_uat", fixture="A", score=50, git_sha="x")
    uat_history.record_run(db_path, harness="run_uat", fixture="B", score=70, git_sha="x")
    rows = uat_history.report_rows(db_path, fixture="A")
    assert len(rows) == 1
    assert rows[0]["fixture"] == "A"


def test_report_respects_limit_and_recency_order(db_path):
    for i in range(5):
        uat_history.record_run(db_path, harness="run_uat", fixture="A", score=i, git_sha="x")
    rows = uat_history.report_rows(db_path, limit=2)
    assert len(rows) == 2


def test_csv_helper_ignores_blank_and_whitespace():
    assert uat_history._csv_to_list("") == []
    assert uat_history._csv_to_list(None) == []
    assert uat_history._csv_to_list("GCP, ArgoCD ,  Snowflake") == ["GCP", "ArgoCD", "Snowflake"]
