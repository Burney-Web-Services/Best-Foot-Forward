"""
Tests for the conditional-bullet filtering logic in
export_cache.py export_bullets_conditional().

These verify the rules independently so the cache generator can be refactored
with confidence.
"""

# ---------------------------------------------------------------------------
# Fixtures — synthetic bullet list representing every meaningful case
# ---------------------------------------------------------------------------

BULLETS = [
    {"id": "main-1",      "tracks": ["engineer"],  "text": "main bullet 1"},
    {"id": "main-2",      "tracks": ["manager"],   "text": "main bullet 2"},
    {"id": "general",     "tracks": ["general"],   "text": "general bullet"},
    # conditional bullets — have use_when, must be separated into conditional file
    {"id": "cond-react",  "tracks": ["engineer"],  "text": "React-specific bullet", "use_when": "When React required"},
    {"id": "cond-hist",   "tracks": ["general"],   "text": "Historical experience only", "use_when": "Pre-2011 role"},
]


def _split_conditional(bullets):
    """Mirrors the filtering logic in export_cache.py export_bullets_conditional()."""
    main        = [b for b in bullets if "use_when" not in b]
    conditional = [b for b in bullets if "use_when" in b]
    return main, conditional


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_conditional_file_contains_only_use_when_bullets():
    _, conditional = _split_conditional(BULLETS)
    ids = {b["id"] for b in conditional}
    assert ids == {"cond-react", "cond-hist"}


def test_conditional_file_excludes_main_bullets():
    _, conditional = _split_conditional(BULLETS)
    ids = {b["id"] for b in conditional}
    for main_id in ("main-1", "main-2", "general"):
        assert main_id not in ids, f"main bullet {main_id} leaked into conditional file"


def test_main_file_contains_only_non_use_when_bullets():
    main, _ = _split_conditional(BULLETS)
    ids = {b["id"] for b in main}
    assert ids == {"main-1", "main-2", "general"}


def test_main_file_excludes_conditional_bullets():
    main, _ = _split_conditional(BULLETS)
    ids = {b["id"] for b in main}
    for cond_id in ("cond-react", "cond-hist"):
        assert cond_id not in ids, f"conditional bullet {cond_id} leaked into main file"
