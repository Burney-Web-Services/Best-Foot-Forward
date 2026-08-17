"""Tests for cover letter sign-off composition.

Regression cover for the missing signature bug: commit 903ed1d removed the code that
appended CONTACT_INFO['name'] after LETTER['closing'], on the assumption that `closing`
always carries the full sign-off. That was true only while the base letter templates
supplied the name. Once the templates were archived, any letter whose closing did not
itself include the name ended with a bare "Sincerely," and nothing else.

compose_signoff has to satisfy both conventions at once, so neither the missing-name
bug nor the original double-name bug can come back.

Uses the project's example persona (docs/example/LeiaOrgana) rather than a real name.
"""
from best_foot_forward.docx_helpers import compose_signoff

NAME = "Leia Organa"


class TestBareClosing:
    """A closing without the name: the generator supplies it."""

    def test_bare_valediction_gets_the_name(self):
        assert compose_signoff("Sincerely,", NAME) == ["Sincerely,", NAME]

    def test_other_valedictions_work_too(self):
        assert compose_signoff("Best regards,", NAME) == ["Best regards,", NAME]

    def test_surrounding_whitespace_is_trimmed(self):
        assert compose_signoff("  Sincerely,\n ", "  Leia Organa ") == ["Sincerely,", NAME]


class TestClosingAlreadyHasName:
    """The upstream convention: closing carries the full sign-off. Do not duplicate."""

    def test_name_on_second_line_is_not_duplicated(self):
        assert compose_signoff("Sincerely,\nLeia Organa", NAME) == ["Sincerely,\nLeia Organa"]

    def test_name_with_contact_details_is_not_duplicated(self):
        closing = "Leia Organa\nleia@example.com"
        assert compose_signoff(closing, NAME) == [closing]

    def test_detection_is_case_insensitive(self):
        assert compose_signoff("Sincerely,\nLEIA ORGANA", NAME) == ["Sincerely,\nLEIA ORGANA"]

    def test_detection_tolerates_extra_internal_whitespace(self):
        assert compose_signoff("Sincerely,\nLeia   Organa", NAME) == ["Sincerely,\nLeia   Organa"]


class TestEdgeCases:
    """Missing or empty inputs must not crash the generator."""

    def test_none_closing_yields_just_the_name(self):
        assert compose_signoff(None, NAME) == [NAME]

    def test_empty_closing_yields_just_the_name(self):
        assert compose_signoff("   ", NAME) == [NAME]

    def test_missing_name_returns_closing_unchanged(self):
        assert compose_signoff("Sincerely,", None) == ["Sincerely,"]

    def test_both_missing_yields_nothing(self):
        assert compose_signoff(None, None) == []
