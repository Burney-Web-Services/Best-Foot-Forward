"""
Suggest a prior application as the tailoring source for a new JD.

Given a company and role, returns the best prior application to use as a
tailoring foundation:
1. Exact: same company, any prior role
2. Fuzzy: highest-score application with overlapping domain/role level

Parses Track: and Key angle: from tailoring_notes for human context.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional, TypedDict

# Find the data directory (same logic as in db.py)
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.normpath(os.path.join(_here, '../../..'))
DATA_DIR = os.path.join(_project_root, 'data')


class TailoringSource(TypedDict):
    """Structured suggestion for a tailoring source."""
    app_id: int
    jd_id: int
    company: str
    role: str
    score: int
    track: Optional[str]
    key_angle: Optional[str]
    match_type: str  # "exact_company" | "fuzzy_domain"


def _parse_tailoring_notes(notes: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Extract Track: and Key angle: from tailoring_notes.

    Returns (track_label, key_angle) or (None, None) if not found.
    """
    if not notes:
        return None, None

    track = None
    key_angle = None

    # Parse Track: line (case-insensitive, capture to end of line or next keyword)
    match = re.search(r'^Track:\s*(.+?)(?=\n|$)', notes, re.MULTILINE | re.IGNORECASE)
    if match:
        track = match.group(1).strip()

    # Parse Key angle: block (capture until next double-newline or end)
    match = re.search(
        r'^Key\s+angle[:\s]+(.+?)(?=\n\n|\nGaps|\Z)',
        notes,
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    if match:
        # Preserve newlines within the key angle, but clean up excessive whitespace
        raw = match.group(1).strip()
        key_angle = ' '.join(raw.split())  # collapse multi-line into single line

    return track, key_angle


def _similarity_score(domain_a: str, domain_b: str) -> float:
    """
    Simple fuzzy domain overlap: count shared words (case-insensitive).
    Returns a score 0.0–1.0.
    """
    words_a = set(domain_a.lower().split())
    words_b = set(domain_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def suggest_tailoring_source(company: str, role: str) -> Optional[TailoringSource]:
    """
    Suggest a prior application as the tailoring source for a new JD.

    Args:
        company: Company name (will be matched against applications.company)
        role: Role name (used for fuzzy domain matching if exact company not found)

    Returns:
        A TailoringSource dict with app_id, track, key_angle, etc., or None
        if no suitable prior application exists.
    """
    summaries_path = os.path.join(DATA_DIR, 'application_summaries.json')
    if not os.path.exists(summaries_path):
        return None

    with open(summaries_path, 'r', encoding='utf-8') as f:
        summaries = json.load(f)

    applications = summaries.get('applications', [])

    # Filter to applied applications only (ignore pending/rejected for now)
    applied = [a for a in applications if a.get('status') == 'applied']
    if not applied:
        return None

    # Strategy 1: exact company match — return the highest-score application for that company.
    # An unscored application (score IS NULL in the DB → None here) still counts as a valid
    # tailoring source; we rank it as 0 so it sorts below any scored sibling but stays eligible.
    same_company = [a for a in applied if a.get('company', '').lower() == company.lower()]
    if same_company:
        best = max(same_company, key=lambda a: a.get('score') or 0)
        track, key_angle = _parse_tailoring_notes(best.get('tailoring_notes'))
        return TailoringSource(
            app_id=best['app_id'],
            jd_id=best['jd_id'],
            company=best['company'],
            role=best['role'],
            score=best.get('score') or 0,
            track=track,
            key_angle=key_angle,
            match_type='exact_company',
        )

    # Strategy 2: fuzzy domain match — find the highest-score application with word overlap
    # in company name and/or role
    combined_target = f"{company} {role}".lower()

    best_fuzzy = None
    best_fuzzy_score = 0.0

    for app in applied:
        app_company = app.get('company', '')
        app_role = app.get('role', '')
        combined_app = f"{app_company} {app_role}".lower()

        sim = _similarity_score(combined_target, combined_app)
        # NULL score (unevaluated application) ranks as 0: it stays eligible on fuzzy
        # overlap alone, just without a score-based boost. `.get('score', 0)` is not
        # enough — the key exists holding None, so the default never fires.
        app_score = app.get('score') or 0

        # Weight by both fuzzy match AND application score
        weighted = sim * (1 + app_score / 100.0)

        if weighted > best_fuzzy_score:
            best_fuzzy_score = weighted
            best_fuzzy = app

    if best_fuzzy and best_fuzzy_score > 0.1:  # threshold: at least 10% word overlap
        track, key_angle = _parse_tailoring_notes(best_fuzzy.get('tailoring_notes'))
        return TailoringSource(
            app_id=best_fuzzy['app_id'],
            jd_id=best_fuzzy['jd_id'],
            company=best_fuzzy['company'],
            role=best_fuzzy['role'],
            score=best_fuzzy.get('score') or 0,
            track=track,
            key_angle=key_angle,
            match_type='fuzzy_domain',
        )

    return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description='Suggest a prior application to use as a tailoring source for a new JD.'
    )
    parser.add_argument('company', help='Company name for the new JD')
    parser.add_argument('role', help='Role name for the new JD')
    args = parser.parse_args()

    result = suggest_tailoring_source(args.company, args.role)
    if result:
        print(f"Found: {result['company']} — {result['role']} (score {result['score']}, {result['match_type']})")
        print(f"Track: {result['track']}")
        print(f"Key angle: {result['key_angle']}")
    else:
        print("No suggestion found")


if __name__ == '__main__':
    main()
