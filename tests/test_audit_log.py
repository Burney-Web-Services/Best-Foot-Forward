"""
Verify the shared JSONL audit trail (utils/audit_log.py) writes one line
per event, appends rather than overwrites, and creates its file/directory
on first use.
"""
import json
from pathlib import Path

import pytest


@pytest.fixture
def audit_log(tmp_path, monkeypatch):
    import best_foot_forward.utils.audit_log as mod
    log_path = tmp_path / "nested" / "audit_log.jsonl"
    monkeypatch.setattr(mod, "LOG_PATH", str(log_path))
    yield mod


def test_creates_file_and_parent_dir_if_missing(audit_log):
    assert not Path(audit_log.LOG_PATH).exists()
    audit_log.log_event("test_actor", "test_action")
    assert Path(audit_log.LOG_PATH).exists()


def test_writes_one_json_line_with_core_fields(audit_log):
    audit_log.log_event("auto_ghost", "ghost", application_id=42, company="Acme")
    lines = Path(audit_log.LOG_PATH).read_text().strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["actor"] == "auto_ghost"
    assert record["action"] == "ghost"
    assert record["application_id"] == 42
    assert record["company"] == "Acme"
    assert "ts" in record


def test_appends_across_multiple_calls(audit_log):
    audit_log.log_event("actor_a", "action_a")
    audit_log.log_event("actor_b", "action_b")
    lines = Path(audit_log.LOG_PATH).read_text().strip().splitlines()
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert records[0]["actor"] == "actor_a"
    assert records[1]["actor"] == "actor_b"
