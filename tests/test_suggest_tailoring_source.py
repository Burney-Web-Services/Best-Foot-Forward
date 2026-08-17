"""
Tests for suggest_tailoring_source.py — deterministic prior-application lookup.
"""

import json
import os
import tempfile
from unittest.mock import patch

from best_foot_forward.utils import suggest_tailoring_source as sts
from best_foot_forward.utils.suggest_tailoring_source import (
    suggest_tailoring_source,
    _parse_tailoring_notes,
    _similarity_score,
    main,
)


# ────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ────────────────────────────────────────────────────────────────────────────

MOCK_SUMMARIES = {
    "applications": [
        {
            "app_id": 1,
            "jd_id": 101,
            "company": "Anthropic",
            "role": "Applied AI Architect, Enterprise Tech",
            "status": "applied",
            "score": 74,
            "tailoring_notes": "Track: manager (SA/advisory framing)\nKey angle: Solutions architect framing",
        },
        {
            "app_id": 2,
            "jd_id": 102,
            "company": "Anthropic",
            "role": "Research Scientist",
            "status": "applied",
            "score": 68,
            "tailoring_notes": "Track: engineer\nKey angle: Deep learning systems",
        },
        {
            "app_id": 3,
            "jd_id": 103,
            "company": "Google",
            "role": "Forward Deployed Engineer III",
            "status": "applied",
            "score": 67,
            "tailoring_notes": "Track: engineer\nKey angle: FDE production AI proof",
        },
        {
            "app_id": 4,
            "jd_id": 104,
            "company": "Brightwheel",
            "role": "Principal AI Product Engineer",
            "status": "rejected",  # Should be ignored
            "score": 70,
            "tailoring_notes": "Track: engineer\nKey angle: AI product leadership",
        },
    ]
}


# ────────────────────────────────────────────────────────────────────────────
# Tests — parsing helpers
# ────────────────────────────────────────────────────────────────────────────

def test_parse_track_and_key_angle():
    """Extract Track: and Key angle: from tailoring_notes."""
    notes = "Track: manager (SA/advisory)\nKey angle: Solutions architect framing"
    track, angle = _parse_tailoring_notes(notes)
    assert track == "manager (SA/advisory)"
    assert angle == "Solutions architect framing"


def test_parse_multiline_key_angle():
    """Key angle: can span multiple lines."""
    notes = """Track: engineer
Key angle: Deep learning systems,
  state-of-the-art architectures,
  and distributed training."""
    track, angle = _parse_tailoring_notes(notes)
    assert track == "engineer"
    assert "Deep learning" in angle
    assert "distributed training" in angle


def test_parse_missing_track():
    """If Track: is missing, return None."""
    notes = "Key angle: Some framing"
    track, angle = _parse_tailoring_notes(notes)
    assert track is None
    assert angle == "Some framing"


def test_parse_empty_notes():
    """Empty or None notes return (None, None)."""
    assert _parse_tailoring_notes(None) == (None, None)
    assert _parse_tailoring_notes("") == (None, None)


def test_similarity_score_exact():
    """Identical strings should score high."""
    score = _similarity_score("engineer manager", "engineer manager")
    assert score == 1.0


def test_similarity_score_partial():
    """Partial overlap scores between 0 and 1."""
    score = _similarity_score("engineer ai", "ai architect")
    assert 0.3 < score < 0.7  # "ai" is shared, but not all words


def test_similarity_score_no_overlap():
    """No shared words score 0."""
    score = _similarity_score("engineer", "banana")
    assert score == 0.0


# ────────────────────────────────────────────────────────────────────────────
# Tests — suggest_tailoring_source with mocked summaries
# ────────────────────────────────────────────────────────────────────────────

@patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR')
def test_exact_company_match_highest_score(mock_data_dir):
    """When company matches exactly, return the highest-score application."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_data_dir = tmpdir
        summaries_path = os.path.join(tmpdir, 'application_summaries.json')
        with open(summaries_path, 'w') as f:
            json.dump(MOCK_SUMMARIES, f)

        # Mock the DATA_DIR
        with patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Anthropic', 'Some Role')

        assert result is not None
        assert result['company'] == 'Anthropic'
        assert result['app_id'] == 1  # Score 74, higher than app 2's 68
        assert result['match_type'] == 'exact_company'
        assert result['track'] == 'manager (SA/advisory framing)'


@patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR')
def test_fuzzy_domain_match(mock_data_dir):
    """When company doesn't match exactly, fuzzy-match on domain overlap."""
    with tempfile.TemporaryDirectory() as tmpdir:
        summaries_path = os.path.join(tmpdir, 'application_summaries.json')
        with open(summaries_path, 'w') as f:
            json.dump(MOCK_SUMMARIES, f)

        with patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Unknown Company', 'Forward Deployed Engineer')

        # Should match "Forward Deployed Engineer III" at Google (app 3) via word overlap
        assert result is not None
        assert result['company'] == 'Google'
        assert result['match_type'] == 'fuzzy_domain'


@patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR')
def test_rejected_applications_ignored(mock_data_dir):
    """Rejected applications should not be suggested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        summaries_path = os.path.join(tmpdir, 'application_summaries.json')
        with open(summaries_path, 'w') as f:
            json.dump(MOCK_SUMMARIES, f)

        with patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Brightwheel', 'Principal AI Product Engineer')

        # Brightwheel application is rejected, so no exact match
        # Will fuzzy-match to Google (ai, engineer keywords overlap)
        assert result is None or result['company'] != 'Brightwheel'


@patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR')
def test_no_match_returns_none(mock_data_dir):
    """If no suitable prior application, return None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        summaries_path = os.path.join(tmpdir, 'application_summaries.json')
        with open(summaries_path, 'w') as f:
            json.dump({"applications": []}, f)

        with patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Unknown', 'Unknown Role')

        assert result is None


@patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR')
def test_extracts_track_and_angle(mock_data_dir):
    """Result includes parsed track and key_angle from tailoring_notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        summaries_path = os.path.join(tmpdir, 'application_summaries.json')
        with open(summaries_path, 'w') as f:
            json.dump(MOCK_SUMMARIES, f)

        with patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Anthropic', 'anything')

        assert result['track'] is not None
        assert result['key_angle'] is not None
        assert 'Solutions architect' in result['key_angle']


@patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR')
def test_result_includes_app_metadata(mock_data_dir):
    """Result includes app_id, jd_id, company, role, score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        summaries_path = os.path.join(tmpdir, 'application_summaries.json')
        with open(summaries_path, 'w') as f:
            json.dump(MOCK_SUMMARIES, f)

        with patch('best_foot_forward.utils.suggest_tailoring_source.DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Anthropic', 'anything')

        assert result['app_id'] == 1
        assert result['jd_id'] == 101
        assert result['score'] == 74


# ────────────────────────────────────────────────────────────────────────────
# Tests — NULL score handling (an unevaluated application: score IS NULL → None)
# ────────────────────────────────────────────────────────────────────────────

# score:None is exactly what json.load produces for a SQLite NULL score. This
# mirrors the real tvScientific row that crashed suggest_tailoring_source before
# the `.get('score') or 0` fix.
MOCK_SUMMARIES_NULL_SCORE = {
    "applications": [
        {
            "app_id": 10,
            "jd_id": 200,
            "company": "tvScientific",
            "role": "SDET II",
            "status": "applied",
            "score": None,
            "tailoring_notes": "Track: engineer\nKey angle: Test infrastructure",
        },
        {
            "app_id": 11,
            "jd_id": 201,
            "company": "Google",
            "role": "Forward Deployed Engineer III",
            "status": "applied",
            "score": 67,
            "tailoring_notes": "Track: engineer\nKey angle: FDE production AI proof",
        },
    ]
}


def _write_summaries(tmpdir, payload):
    path = os.path.join(tmpdir, 'application_summaries.json')
    with open(path, 'w') as f:
        json.dump(payload, f)
    return path


def test_fuzzy_does_not_crash_on_null_score():
    """A NULL-score application in the pool must not crash the fuzzy pass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summaries(tmpdir, MOCK_SUMMARIES_NULL_SCORE)
        with patch.object(sts, 'DATA_DIR', tmpdir):
            # Company with no exact match forces the fuzzy path across all applied,
            # including the NULL-score tvScientific row.
            result = suggest_tailoring_source('Netflix', 'Software Engineer')
        # No crash; either a fuzzy hit or None, but never a TypeError.
        assert result is None or 'company' in result


def test_null_score_exact_match_normalized_to_zero():
    """Exact company match on a NULL-score app returns score 0, not None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summaries(tmpdir, MOCK_SUMMARIES_NULL_SCORE)
        with patch.object(sts, 'DATA_DIR', tmpdir):
            result = suggest_tailoring_source('tvScientific', 'SDET II')
        assert result is not None
        assert result['company'] == 'tvScientific'
        assert result['score'] == 0  # NULL ranked/reported as 0, satisfies score: int
        assert result['match_type'] == 'exact_company'


def test_null_score_ranks_below_scored_sibling():
    """With two same-company apps, a scored one outranks a NULL-score one."""
    payload = {
        "applications": [
            {
                "app_id": 20, "jd_id": 300, "company": "Acme", "role": "A",
                "status": "applied", "score": None, "tailoring_notes": "",
            },
            {
                "app_id": 21, "jd_id": 301, "company": "Acme", "role": "B",
                "status": "applied", "score": 55, "tailoring_notes": "",
            },
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summaries(tmpdir, payload)
        with patch.object(sts, 'DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Acme', 'anything')
        assert result['app_id'] == 21  # scored 55 beats NULL-ranked-0
        assert result['score'] == 55


def test_null_score_fuzzy_still_eligible():
    """A NULL-score app still wins on fuzzy overlap when it's the only match."""
    payload = {
        "applications": [
            {
                "app_id": 30, "jd_id": 400, "company": "tvScientific",
                "role": "Forward Deployed Engineer", "status": "applied",
                "score": None, "tailoring_notes": "Track: engineer\nKey angle: FDE",
            },
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summaries(tmpdir, payload)
        with patch.object(sts, 'DATA_DIR', tmpdir):
            result = suggest_tailoring_source('Unknown Co', 'Forward Deployed Engineer')
        assert result is not None
        assert result['app_id'] == 30
        assert result['match_type'] == 'fuzzy_domain'
        assert result['score'] == 0


# ────────────────────────────────────────────────────────────────────────────
# Tests — CLI entry point (argparse, replacing the old hardcoded scratch test)
# ────────────────────────────────────────────────────────────────────────────

def test_main_uses_cli_args(capsys):
    """main() reads company/role from argv rather than hardcoded values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summaries(tmpdir, MOCK_SUMMARIES_NULL_SCORE)
        argv = ['suggest_tailoring_source', 'tvScientific', 'SDET II']
        with patch.object(sts, 'DATA_DIR', tmpdir), patch('sys.argv', argv):
            main()
        out = capsys.readouterr().out
        assert 'tvScientific' in out
        assert 'exact_company' in out


def test_main_no_match_reports_none(capsys):
    """main() prints the no-suggestion line when nothing matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summaries(tmpdir, {"applications": []})
        argv = ['suggest_tailoring_source', 'Nobody', 'Nothing']
        with patch.object(sts, 'DATA_DIR', tmpdir), patch('sys.argv', argv):
            main()
        assert 'No suggestion found' in capsys.readouterr().out
