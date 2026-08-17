#!/usr/bin/env python3
"""Track applications after Codex runs the resume generator.

Codex sends hook payloads as JSON on stdin. The hook schema may add fields over
time, so this deliberately searches the payload values rather than coupling the
application-tracking behavior to one payload layout.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator


GENERATOR = "src/best_foot_forward/utils/generate_resume.py"


def strings(value: Any) -> Iterator[str]:
    """Yield all textual values in a JSON-compatible object."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    if not any(GENERATOR in value for value in strings(payload)):
        return 0

    workspace_root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "src/best_foot_forward/utils/track_application.py"],
        cwd=workspace_root,
        check=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
