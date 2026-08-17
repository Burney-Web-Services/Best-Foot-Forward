"""
Verify the log_action.py CLI wrapper (Pattern B: command-markdown-driven
workflows with no single Python entry point, e.g. evaluate-job,
interview-debrief, star-story) correctly parses args and appends one line
via the shared audit_log.log_event.
"""
import json
from pathlib import Path

import pytest


@pytest.fixture
def log_action(tmp_path, monkeypatch):
    import best_foot_forward.utils.audit_log as audit_log_mod
    import best_foot_forward.utils.log_action as mod
    log_path = tmp_path / "audit_log.jsonl"
    monkeypatch.setattr(audit_log_mod, "LOG_PATH", str(log_path))
    yield mod, log_path


def run_main(mod, monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["log_action.py"] + argv)
    mod.main()


class TestLogAction:
    def test_required_args_only(self, log_action, monkeypatch):
        mod, log_path = log_action
        run_main(mod, monkeypatch, ["--actor", "evaluate-job", "--action", "score"])

        record = json.loads(log_path.read_text().strip())
        assert record["actor"] == "evaluate-job"
        assert record["action"] == "score"

    def test_entity_type_and_id(self, log_action, monkeypatch):
        mod, log_path = log_action
        run_main(mod, monkeypatch, [
            "--actor", "evaluate-job", "--action", "score",
            "--entity-type", "jd", "--entity-id", "42",
        ])

        record = json.loads(log_path.read_text().strip())
        assert record["entity_type"] == "jd"
        assert record["entity_id"] == 42

    def test_details_json_merged_in(self, log_action, monkeypatch):
        mod, log_path = log_action
        run_main(mod, monkeypatch, [
            "--actor", "evaluate-job", "--action", "score",
            "--details", '{"company": "Acme", "score": 85}',
        ])

        record = json.loads(log_path.read_text().strip())
        assert record["company"] == "Acme"
        assert record["score"] == 85

    def test_details_plus_entity_fields_together(self, log_action, monkeypatch):
        mod, log_path = log_action
        run_main(mod, monkeypatch, [
            "--actor", "star-story", "--action", "capture",
            "--entity-type", "story", "--entity-id", "7",
            "--details", '{"title": "Kuat rewrite"}',
        ])

        record = json.loads(log_path.read_text().strip())
        assert record["entity_type"] == "story"
        assert record["entity_id"] == 7
        assert record["title"] == "Kuat rewrite"

    def test_slug_entity_id_for_non_row_entities(self, log_action, monkeypatch):
        """/capture-voice logs a memory file, which has no integer primary key —
        --entity-id must accept a string slug, not just numeric row ids."""
        mod, log_path = log_action
        run_main(mod, monkeypatch, [
            "--actor", "capture-voice", "--action", "write",
            "--entity-type", "memory-file", "--entity-id", "voice_guide",
        ])

        record = json.loads(log_path.read_text().strip())
        assert record["entity_id"] == "voice_guide"

    def test_missing_required_arg_raises(self, log_action, monkeypatch):
        mod, _ = log_action
        with pytest.raises(SystemExit):
            run_main(mod, monkeypatch, ["--actor", "evaluate-job"])  # missing --action
