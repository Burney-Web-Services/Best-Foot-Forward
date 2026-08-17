"""The bug this file exists for: JD skill extraction once built its entire
vocabulary from the user's own skills table (plus a small hardcoded list), so
a gap report could only ever surface skills the user already had. This is a
pure-function regression test — no DB fixture beyond schema, no LLM, no
sandbox roleplay required to catch it.
"""
import sqlite3
from pathlib import Path

import pytest

from best_foot_forward.utils.jd_skills import canonicalize, extract_terms

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "best_foot_forward" / "schema.sql"


def make_db(skills=()):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    for sid, label, content in skills:
        conn.execute("INSERT INTO skills (id, label, content) VALUES (?, ?, ?)", (sid, label, content))
    conn.commit()
    return conn


class TestExtractionIsNotBoundedByTheProfile:
    def test_extraction_is_not_bounded_by_the_profile(self):
        """The headline regression: a profile with none of these skills must
        still surface them from a JD that names them explicitly."""
        conn = make_db(skills=[("py", "Python", "Python, Django, PostgreSQL")])
        text = ("Requires production experience with ArgoCD, Istio, Terragrunt, "
                "Crossplane, and GitLab CI for our platform team.")

        terms = extract_terms(text, conn)
        canonicals = {t.canonical for t in terms}

        assert {"ArgoCD", "Istio", "Terragrunt", "Crossplane", "GitLab CI"} <= canonicals

    def test_profile_skills_are_still_matched(self):
        """Backward compatibility: terms the user actually has must still be
        indexed, same as before this fix — extraction is additive, not a
        replacement of the profile-derived path."""
        conn = make_db(skills=[("py", "Python", "Python, Django")])
        terms = extract_terms("Requires strong Python and Django experience.", conn)
        canonicals = {t.canonical for t in terms}
        assert "Python" in canonicals

    def test_matched_profile_term_gets_its_skill_id(self):
        conn = make_db(skills=[("py", "Python", "Python")])
        terms = extract_terms("Python required.", conn)
        python_term = next(t for t in terms if t.label == "python")
        assert python_term.skill_id == "py"

    def test_lexicon_term_not_in_profile_has_no_skill_id(self):
        conn = make_db(skills=[("py", "Python", "Python")])
        terms = extract_terms("Requires ArgoCD.", conn)
        argocd = next(t for t in terms if t.canonical == "ArgoCD")
        assert argocd.skill_id is None
        assert argocd.source == "lexicon"

    def test_no_false_positive_on_substring(self):
        """java must not match inside javascript, kafka must not match inside
        some unrelated compound word -- \\b word boundaries, same discipline
        the original extractor had."""
        conn = make_db()
        terms = extract_terms("Requires strong JavaScript experience.", conn)
        labels = {t.label for t in terms}
        assert "javascript" in labels
        assert "java" not in labels


class TestLlmTier:
    def test_llm_labels_are_canonicalized_and_included(self):
        conn = make_db()
        terms = extract_terms(
            "Some JD text with nothing extractable by lexicon alone.",
            conn,
            llm_labels=["columnar data formats (Apache Arrow, Parquet)"],
        )
        # canonicalize() strips the parenthetical qualifier; the cleaned
        # phrase becomes the canonical label since it isn't itself a lexicon hit
        assert any(t.source == "llm" for t in terms)

    def test_llm_label_matching_lexicon_gets_canonical_form(self):
        conn = make_db()
        terms = extract_terms("no lexicon hits here", conn, llm_labels=["k8s"])
        llm_term = next(t for t in terms if t.source == "llm")
        assert llm_term.canonical == "Kubernetes"

    def test_llm_label_already_found_by_lexicon_is_not_duplicated(self):
        conn = make_db()
        terms = extract_terms("Requires ArgoCD experience.", conn, llm_labels=["ArgoCD"])
        argocd_terms = [t for t in terms if t.canonical == "ArgoCD"]
        assert len(argocd_terms) == 1


class TestCanonicalize:
    def test_strips_parenthetical_qualifier(self):
        assert canonicalize("Python (Django strongly preferred)") == "Python"

    def test_strips_trailing_qualifier_phrase(self):
        assert canonicalize("Go preferred") == "Go"

    def test_maps_alias_to_canonical(self):
        assert canonicalize("k8s") == "Kubernetes"
        assert canonicalize("gh actions") == "GitHub Actions"

    def test_rejects_sentence_fragments(self):
        assert canonicalize("Experience with a wide variety of backend systems.") is None
        assert canonicalize("ability to build AI evaluation harnesses rather than just use off-the-shelf tools") is None

    def test_rejects_empty_after_stripping(self):
        assert canonicalize("   ") is None

    def test_title_cases_a_clean_lowercase_phrase_not_in_lexicon(self):
        assert canonicalize("distributed tracing") == "Distributed Tracing"


class TestCanonicalizationCollapsesQualifiers:
    def test_qualifier_variants_collapse_to_the_same_canonical_label(self):
        """This is the half of the fix that actually makes the gaps report
        aggregate correctly: without it, 'python (django strongly preferred)'
        and 'python' never collide, so HAVING demand >= 2 filters both out."""
        variants = ["Python (Django strongly preferred)", "python", "Python required"]
        canonicals = {canonicalize(v) for v in variants}
        assert canonicals == {"Python"}


class TestCompoundProfileEntries:
    """A skills group stores "JavaScript/TypeScript" as one comma token. The
    profile term index yielded that literal string, which can never word-match
    "javascript" in a JD — so a skill explicitly claimed in the profile read as
    "not in your skills" everywhere skill_id is consulted. On a real database
    that was JavaScript across 20 JDs.
    """

    def test_slash_joined_entry_links_both_halves(self):
        conn = make_db([("s-lang", "Languages", "PHP, JavaScript/TypeScript, SQL")])
        terms = {t.canonical: t for t in extract_terms("We use JavaScript heavily.", conn)}
        assert "JavaScript" in terms
        assert terms["JavaScript"].skill_id == "s-lang", (
            "a claimed skill stored as half a slash pair must still link to its group"
        )

    def test_both_halves_link_independently(self):
        conn = make_db([("s-lang", "Languages", "JavaScript/TypeScript")])
        for jd, expected in [("TypeScript required.", "TypeScript"),
                             ("JavaScript required.", "JavaScript")]:
            terms = {t.canonical: t for t in extract_terms(jd, conn)}
            assert terms[expected].skill_id == "s-lang"

    def test_a_split_part_is_never_introduced_as_a_new_skill(self):
        """The reason this pass is attach-only. Splitting "Agile/SAFe" yields
        "safe" — a real framework (Scaled Agile Framework) whose lowercased form
        collides with an ordinary English word, so introducing it would tag every
        JD mentioning "a safe environment" as demanding SAFe. Matching SAFe for
        real needs case-sensitive comparison, which the extractor does not do."""
        conn = make_db([("s-lead", "Leadership", "Agile/SAFe, Mentoring")])
        canonicals = {t.canonical for t in
                      extract_terms("A safe workplace in a psychologically safe team.", conn)}
        assert "Safe" not in canonicals
        assert "SAFe" not in canonicals

    def test_multiword_halves_are_left_alone(self):
        """Splitting "CI/CD Test Integration" would produce "CD Test
        Integration", which is not a term."""
        conn = make_db([("s-qe", "Testing", "CI/CD Test Integration, PHPUnit")])
        canonicals = {t.canonical for t in
                      extract_terms("Own the CD Test Integration pipeline.", conn)}
        assert "Cd Test Integration" not in canonicals

    def test_does_not_overwrite_a_skill_id_another_pass_already_set(self):
        conn = make_db([
            ("s-frontend", "Frontend", "TypeScript, React"),
            ("s-lang", "Languages", "JavaScript/TypeScript"),
        ])
        terms = {t.canonical: t for t in extract_terms("TypeScript required.", conn)}
        assert terms["TypeScript"].skill_id == "s-frontend", (
            "the direct, non-compound match should win"
        )
