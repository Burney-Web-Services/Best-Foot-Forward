"""Thin CLI wrapper around utils.audit_log.log_event, for command-markdown-
driven workflows (evaluate-job, interview-debrief, star-story capture) that
have no single Python entry point to call log_event from directly — they
persist via direct SQL from the command's own instructions instead.

Usage:
    python3 -m best_foot_forward.utils.log_action --actor evaluate-job --action score \
        --entity-type jd --entity-id 42 --details '{"score": 85, "company": "Acme"}'

    python3 -m best_foot_forward.utils.log_action --actor capture-voice --action write \
        --entity-type memory-file --entity-id voice_guide --details '{"sample_count": 3}'
"""
from __future__ import annotations

import argparse
import json

from best_foot_forward.utils.audit_log import log_event


def main():
    parser = argparse.ArgumentParser(description="Append one line to the shared audit log.")
    parser.add_argument("--actor", required=True, help="Which command/workflow logged this, e.g. 'evaluate-job'")
    parser.add_argument("--action", required=True, help="What happened, e.g. 'score'")
    parser.add_argument("--entity-type", help="e.g. 'jd', 'application', 'story'")
    parser.add_argument(
        "--entity-id",
        help="Id of the affected entity. Deliberately untyped: most entities are SQLite "
             "rows with integer ids ('42'), but some aren't rows at all — /capture-voice "
             "logs 'voice_guide', a memory file with no primary key. A purely numeric "
             "value is coerced to int below so existing audit-log entries keep their type.",
    )
    parser.add_argument("--details", help="Extra fields as a JSON object, merged into the log line")
    args = parser.parse_args()

    fields = json.loads(args.details) if args.details else {}
    if args.entity_type is not None:
        fields["entity_type"] = args.entity_type
    if args.entity_id is not None:
        # Numeric ids stay ints so this doesn't retype every historical log line;
        # slug ids ('voice_guide') pass through as strings.
        fields["entity_id"] = int(args.entity_id) if args.entity_id.isdigit() else args.entity_id

    log_event(args.actor, args.action, **fields)


if __name__ == "__main__":
    main()
