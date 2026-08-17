"""JD skill-term extraction and canonicalization — the fix for a real,
structural bug: extraction used to build its entire matching vocabulary from
the user's own `skills` table (plus a small hardcoded list), so
`jd_required_skills` could only ever contain skills the user already had.
The skill-gap report (`reports/skills.py::view_gaps`) subtracts the profile
from that same vocabulary, so it was mathematically incapable of surfacing a
real gap — confirmed empirically: of every skill label the old extractor ever
produced on the real DB, all but one were already in the profile or the
hardcoded list.

Two independent sources of vocabulary, unioned:

  Tier 1 — `lexicon/tech_lexicon.json`, a shipped reference file (not derived
  from any user's profile). This is what actually breaks the circularity:
  vocabulary provenance is a tracked file the project ships, not data the
  extraction is being measured against. Works fully offline — required,
  since directory sweeps (`scan_jds.py`) and backfill (`reindex_jd_skills.py`)
  have no LLM in the loop at all.

  Tier 2 (optional) — pre-extracted labels from an LLM pass over the JD.
  evaluate-job's scoring subagent already reads the whole JD to reason about
  the Gap-risk dimension; `--skills-json` lets its `required_skills` output
  feed this module directly rather than a second, separate extraction pass.

Canonicalization matters as much as the open vocabulary: a raw JD phrase like
"python (django strongly preferred)" never collides with another JD's "Python"
mention, so `reports/skills.py`'s `HAVING demand >= 2` filters singletons like
this out regardless of how open the vocabulary is. `canonicalize()` strips
qualifiers and maps aliases so equivalent mentions aggregate.

The user's own `skills` table remains in the loop, but demoted: `extract_terms`
still scans it directly (so company/user-specific terms not yet in the shared
lexicon keep getting indexed, matching the pre-fix behavior), but a term's
presence there no longer gates whether extraction can find it at all.
"""
from __future__ import annotations

import json
import os
import re
from typing import NamedTuple

_HERE = os.path.dirname(os.path.abspath(__file__))
LEXICON_PATH = os.path.normpath(os.path.join(_HERE, "..", "lexicon", "tech_lexicon.json"))

_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_TRAILING_QUALIFIERS_RE = re.compile(
    r"\b(strongly preferred|preferred|a plus|nice to have|nice-to-have|"
    r"or equivalent|experience with|required|desired)\b",
    re.IGNORECASE,
)
_MAX_CANONICAL_WORDS = 6


class Term(NamedTuple):
    label: str            # lowercase matched form — what jd_required_skills.skill_label stores (unchanged shape)
    canonical: str         # display-worthy canonical label — jd_required_skills.canonical_label
    skill_id: str | None   # matched skills.id, if the term is also in the user's own library
    source: str            # 'lexicon' | 'profile' | 'llm'


_lexicon_cache: dict[str, str] | None = None


def load_lexicon() -> dict[str, str]:
    """alias(lower) -> canonical display label. Cached — this file is read on
    every extraction call otherwise, and it doesn't change within a process."""
    global _lexicon_cache
    if _lexicon_cache is not None:
        return _lexicon_cache
    with open(LEXICON_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    alias_to_canonical: dict[str, str] = {}
    for canonical, aliases in raw.items():
        if canonical.startswith("_"):
            continue
        for alias in aliases:
            alias_to_canonical[alias.lower()] = canonical
        alias_to_canonical.setdefault(canonical.lower(), canonical)
    _lexicon_cache = alias_to_canonical
    return alias_to_canonical


def canonicalize(raw: str) -> str | None:
    """Clean a raw JD phrase into a display-worthy skill label, or None to
    reject it outright — a JD sentence fragment ("ai evaluation harnesses
    (build, not just use)") is not a skill, and letting it through is what
    lets singleton noise drown out real, aggregatable gap terms."""
    text = raw.strip()
    text = _PAREN_RE.sub("", text)
    text = _TRAILING_QUALIFIERS_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Check for sentence punctuation before the final trim strips it away —
    # a trailing "." is exactly the signal that this is a sentence fragment,
    # not a skill term, and it must be checked before it's stripped off.
    has_sentence_punctuation = bool(re.search(r"[.!?]", text))
    word_count = len(text.split())

    text = text.strip(" ,.;:-")
    if not text:
        return None

    lexicon = load_lexicon()
    hit = lexicon.get(text.lower())
    if hit:
        return hit

    if word_count > _MAX_CANONICAL_WORDS or has_sentence_punctuation:
        return None

    return text.title() if text.islower() else text


def build_term_index(conn) -> list[tuple[str, str]]:
    """(term_lower, skill_id) pairs from the user's own skills table, sorted
    longest-first. Kept for backward compatibility with existing callers, and
    for attaching a skill_id to a matched term — it no longer gates what
    extract_terms() is able to find at all."""
    index = []
    for row in conn.execute("SELECT id, content FROM skills"):
        for term in row["content"].split(","):
            term = re.sub(r"\s*\(.*", "", term).rstrip(")").strip()
            if len(term) >= 3:
                index.append((term.lower(), row["id"]))
    index.sort(key=lambda x: -len(x[0]))
    return index


def build_compound_part_index(conn) -> list[tuple[str, str]]:
    """(part_lower, skill_id) for the halves of slash-joined profile entries.

    A skills group stores "JavaScript/TypeScript" as one comma token, so
    build_term_index() yields the literal term `javascript/typescript`, which
    can never word-match "javascript" in a JD. The result: a skill explicitly
    claimed in the profile reads as "not in your skills" in every report that
    keys off skill_id.

    Only single-word parts are split. "CI/CD Test Integration" and
    "Authentication/Identity Systems" stay whole, because splitting on a part
    that contains spaces produces fragments ("CD Test Integration") that are
    not terms at all.

    These are for *attaching* a skill_id to a term some other pass already
    found — never for introducing one. Splitting "Agile/SAFe" yields "safe",
    which is a genuine skill (Scaled Agile Framework) but collides with an
    ordinary English word once the pipeline lowercases everything. Introducing
    it here would tag every JD that says "a safe environment" as demanding SAFe.
    Linking SAFe properly needs case-sensitive matching, which the extractor
    does not currently do anywhere.
    """
    parts = []
    for row in conn.execute("SELECT id, content FROM skills"):
        for term in row["content"].split(","):
            term = re.sub(r"\s*\(.*", "", term).rstrip(")").strip()
            if "/" not in term:
                continue
            halves = [h.strip() for h in term.split("/")]
            if not all(halves) or any(" " in h for h in halves):
                continue
            for half in halves:
                if len(half) >= 3:
                    parts.append((half.lower(), row["id"]))
    return parts


def extract_terms(text: str, conn, llm_labels: list[str] | None = None) -> list[Term]:
    """Extract technology/practice terms actually named in JD text — see
    module docstring for the two-tier design."""
    text_lower = text.lower()
    found: dict[str, Term] = {}

    lexicon = load_lexicon()
    for alias in sorted(lexicon, key=len, reverse=True):
        if alias in found:
            continue
        if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
            found[alias] = Term(label=alias, canonical=lexicon[alias], skill_id=None, source="lexicon")

    for term_lower, skill_id in build_term_index(conn):
        if term_lower in found:
            existing = found[term_lower]
            if existing.skill_id is None:
                found[term_lower] = existing._replace(skill_id=skill_id)
            continue
        if re.search(r"\b" + re.escape(term_lower) + r"\b", text_lower):
            canonical = canonicalize(term_lower) or term_lower.title()
            found[term_lower] = Term(label=term_lower, canonical=canonical, skill_id=skill_id, source="profile")

    if llm_labels:
        for raw_label in llm_labels:
            canonical = canonicalize(raw_label)
            if not canonical:
                continue
            key = canonical.lower()
            if key in found:
                continue
            found[key] = Term(label=key, canonical=canonical, skill_id=None, source="llm")

    # Last, because it only annotates what the passes above found: link the
    # halves of slash-joined profile entries ("JavaScript/TypeScript") to their
    # skills group. Attach-only by design — see build_compound_part_index.
    for part, skill_id in build_compound_part_index(conn):
        existing = found.get(part)
        if existing is not None and existing.skill_id is None:
            found[part] = existing._replace(skill_id=skill_id)

    return list(found.values())
