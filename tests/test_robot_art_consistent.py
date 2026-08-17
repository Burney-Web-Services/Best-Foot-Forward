"""The ASCII robot appears in more than one place and must be the same drawing
everywhere.

It drifted once: commit 3c4939c ("Updated the little bot icon") replaced the
robot in CLAUDE.md's session-startup block but missed the copy in
.claude/commands/web.md, so `/web` kept printing the previous design while the
session greeting printed the new one — visible to the user as the bot randomly
reverting.

There is no shared constant to point both at (they are instructions to an agent,
not code), so a test is the only thing that keeps them together.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / ".claude" / "commands" / "web.md",
]

# The line every version of the robot has kept — its little heart-arm.
ROBOT_MARKER = re.compile(r"^\s*-*\[ ?<3 ?\]--", re.M)


def _is_art(line: str) -> bool:
    """Art lines are non-blank and contain no letters or fence markers — the
    robot is drawn entirely from punctuation and underscores."""
    stripped = line.strip()
    if not stripped or stripped.startswith("```"):
        return False
    return not any(c.isalpha() for c in stripped)


def extract_robot(path: Path) -> list[str]:
    """Find the robot by its marker line and expand outward over adjacent art
    lines. Fence-pair parsing is unreliable here — these files contain other
    code blocks, and one stray fence shifts every pair after it."""
    lines = [ln.rstrip() for ln in path.read_text().splitlines()]
    hits = [i for i, ln in enumerate(lines) if ROBOT_MARKER.search(ln)]
    if not hits:
        return []
    i = hits[0]
    start, end = i, i
    while start > 0 and _is_art(lines[start - 1]):
        start -= 1
    while end + 1 < len(lines) and _is_art(lines[end + 1]):
        end += 1
    return lines[start:end + 1]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_each_source_actually_contains_a_robot(path):
    assert extract_robot(path), f"no fenced robot block found in {path}"


def test_all_copies_are_identical():
    drawings = {str(p.relative_to(REPO_ROOT)): extract_robot(p) for p in SOURCES}
    reference_name, reference = next(iter(drawings.items()))
    for name, drawing in drawings.items():
        assert drawing == reference, (
            f"robot in {name} differs from {reference_name}\n"
            f"{name}:\n" + "\n".join(drawing) + "\n\n"
            f"{reference_name}:\n" + "\n".join(reference)
        )


def test_the_old_design_is_gone():
    """Guard against the specific stale drawing that caused this."""
    old_markers = ["[__]__", "|*  *|", "_|/_"]
    for path in SOURCES:
        text = path.read_text()
        for marker in old_markers:
            assert marker not in text, f"{path} still contains the retired robot ({marker!r})"
