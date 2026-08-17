"""generate_star_prep.expand_ops: expands a company's operating-principle
abbreviations ("TB" -> "Think Big") in the STAR prep doc.

Importing this module is itself the awkward part, and worth stating plainly:
all three prep generators do `from star_data import ...` at module scope, so
they cannot be imported at all without a session scratch file present — and
data/session/ is gitignored, so a fresh clone and CI both lack it. That import
shape is why these modules had no tests. Stubbing the session module is the
cheap way in; making the generators importable without one is the real fix,
and is a bigger change than this test.
"""
import sys
import types

import pytest


@pytest.fixture(scope="module")
def star_prep():
    """Import generate_star_prep with a stubbed session data module."""
    stub = types.ModuleType("star_data")
    stub.COMPANY = "Kuat Design Systems"
    stub.ROLE = "Staff Engineer"
    stub.OUTPUT_DIR = "/tmp"
    stub.INTERVIEWER = "A. Interviewer"
    stub.DATE = "2026-08-16"
    stub.OPS_KEY = [
        ("TB", "Think Big"),
        ("DD", "Dive Deep"),
        ("CO", "Customer Obsession"),
    ]
    stub.STARS = []
    stub.OPS_CROSSREF = {}

    saved = sys.modules.get("star_data")
    sys.modules["star_data"] = stub
    try:
        from best_foot_forward.utils import generate_star_prep
        yield generate_star_prep
    finally:
        if saved is None:
            sys.modules.pop("star_data", None)
        else:
            sys.modules["star_data"] = saved


class TestExpandOps:
    def test_expands_a_bare_abbreviation(self, star_prep):
        assert star_prep.expand_ops("TB") == "Think Big"

    def test_keeps_the_trailing_description(self, star_prep):
        assert star_prep.expand_ops("TB (rearchitected the platform)") == \
            "Think Big (rearchitected the platform)"

    def test_expands_every_item_in_a_pipe_separated_list(self, star_prep):
        assert star_prep.expand_ops("TB | DD (root caused it) | CO") == \
            "Think Big | Dive Deep (root caused it) | Customer Obsession"

    def test_unknown_abbreviations_pass_through_untouched(self, star_prep):
        """A company whose principles aren't in OPS_KEY must not have its text
        mangled — the prep doc is still useful with the raw label."""
        assert star_prep.expand_ops("XX (something)") == "XX (something)"
        assert star_prep.expand_ops("TB | XX") == "Think Big | XX"

    def test_expansion_is_anchored_to_the_first_word(self, star_prep):
        """Only the leading token is an abbreviation; a match later in the
        description must not be substituted."""
        assert star_prep.expand_ops("DD (we had to TB about it)") == \
            "Dive Deep (we had to TB about it)"

    def test_empty_string_round_trips(self, star_prep):
        assert star_prep.expand_ops("") == ""

    def test_already_expanded_names_are_left_alone(self, star_prep):
        assert star_prep.expand_ops("Think Big | Dive Deep") == "Think Big | Dive Deep"
