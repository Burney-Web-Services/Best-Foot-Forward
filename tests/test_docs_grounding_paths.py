"""Permanent guard against doc/code drift of the shape that caused a real bug:
CLAUDE.md told evaluate-job to read `data/_bullets_manager.json`, a per-track
file export_cache.py stopped producing when ADR-0009 removed the per-track
split. The doc sweep that landed ADR-0009 updated docs/reference.md and
docs/architecture.md but missed CLAUDE.md, AGENTS.md, and .antigravity.md.

This scans every doc/command markdown file for backtick-quoted
`data/_*.json` paths and asserts each one is a file export_cache.py actually
produces. Catches the next doc-drift bug of this exact shape automatically,
without needing a human to notice a stale filename in prose.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The complete, exact set of data/_*.json files export_cache.py produces —
# kept in sync by hand; a change here should be paired with a change there.
EXPORT_CACHE_PRODUCES = {
    "_bullets.json",
    "_bullets_conditional.json",
    "_skills.json",
    "_employers.json",
    "_contact.json",
    "_education.json",
}

DOC_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / ".antigravity.md",
    *sorted((REPO_ROOT / ".claude" / "commands").glob("*.md")),
]

# `data/_*.json` inside backticks, e.g. `data/_bullets.json` or `` `data/_skills.json` ``
JSON_PATH_RE = re.compile(r"`data/(_[a-zA-Z0-9_]+\.json)`")


def find_referenced_json_paths(text: str) -> set[str]:
    return set(JSON_PATH_RE.findall(text))


class TestDocsReferenceRealCacheFiles:
    def test_no_doc_references_a_nonexistent_per_track_file(self):
        """Regression test for the exact bug: any data/_bullets_<track>.json or
        data/_skills_<track>.json reference is stale — export_cache.py has
        never produced per-track files since ADR-0009."""
        offenders = []
        for path in DOC_FILES:
            if not path.exists():
                continue
            referenced = find_referenced_json_paths(path.read_text())
            unknown = referenced - EXPORT_CACHE_PRODUCES
            if unknown:
                offenders.append((path.relative_to(REPO_ROOT), unknown))

        assert not offenders, (
            "Doc file(s) reference data/_*.json paths export_cache.py doesn't "
            "produce (stale per-track reference, or a typo):\n" +
            "\n".join(f"  {p}: {sorted(u)}" for p, u in offenders)
        )

    def test_export_cache_produces_every_file_this_test_expects(self):
        """Keeps EXPORT_CACHE_PRODUCES itself honest — if export_cache.py adds
        or removes an output file without this set being updated to match,
        the other test above would silently stop meaning anything."""
        source = (REPO_ROOT / "src" / "best_foot_forward" / "utils" / "export_cache.py").read_text()
        actual = set(re.findall(r'"(_[a-zA-Z0-9_]+\.json)"', source))
        assert actual == EXPORT_CACHE_PRODUCES, (
            f"export_cache.py's actual output files {actual} no longer match "
            f"EXPORT_CACHE_PRODUCES {EXPORT_CACHE_PRODUCES} in this test — update the set."
        )
