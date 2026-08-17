"""
Tests for pure functions in transcribe.py — no ML models needed.
The conftest.py stubs out faster-whisper, pyannote, and torch at import time.
"""
from best_foot_forward.utils.transcribe import (
    _fmt_ts,
    assign_speakers,
    format_transcript,
)


# ── _fmt_ts ──────────────────────────────────────────────────────────────────

def test_fmt_ts_under_one_hour():
    assert _fmt_ts(90) == "01:30"


def test_fmt_ts_zero():
    assert _fmt_ts(0) == "00:00"


def test_fmt_ts_exact_minute():
    assert _fmt_ts(60) == "01:00"


def test_fmt_ts_long_flag_pads_hours():
    assert _fmt_ts(90, long=True) == "00:01:30"


def test_fmt_ts_over_one_hour_shows_hours():
    assert _fmt_ts(3661) == "01:01:01"


# ── assign_speakers ───────────────────────────────────────────────────────────

def test_assign_speakers_exact_overlap():
    segs = [{"start": 0.0, "end": 5.0, "text": "Hello"}]
    diarization = [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}]
    result = assign_speakers(segs, diarization)
    assert result[0]["speaker"] == "SPEAKER_00"


def test_assign_speakers_picks_best_overlap():
    segs = [{"start": 2.0, "end": 8.0, "text": "Some text"}]
    diarization = [
        {"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"},  # 1s overlap
        {"start": 3.0, "end": 9.0, "speaker": "SPEAKER_01"},  # 5s overlap
    ]
    result = assign_speakers(segs, diarization)
    assert result[0]["speaker"] == "SPEAKER_01"


def test_assign_speakers_no_overlap_returns_unknown():
    segs = [{"start": 10.0, "end": 15.0, "text": "No speaker"}]
    diarization = [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}]
    result = assign_speakers(segs, diarization)
    assert result[0]["speaker"] == "UNKNOWN"


def test_assign_speakers_preserves_text():
    segs = [{"start": 0.0, "end": 2.0, "text": "Preserved text"}]
    diarization = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}]
    result = assign_speakers(segs, diarization)
    assert result[0]["text"] == "Preserved text"


# ── format_transcript ─────────────────────────────────────────────────────────

def test_format_transcript_header():
    segs = [{"start": 0.0, "end": 3.0, "text": "Hi", "speaker": "SPEAKER_00"}]
    content = format_transcript(segs, "/tmp/interview.m4a", 180.0, "base.en")
    assert content.startswith("# Transcript: interview.m4a")


def test_format_transcript_contains_speaker():
    segs = [{"start": 0.0, "end": 3.0, "text": "Hi there", "speaker": "SPEAKER_01"}]
    content = format_transcript(segs, "/tmp/test.m4a", 60.0, "small.en")
    assert "SPEAKER_01" in content
    assert "Hi there" in content


def test_format_transcript_contains_model():
    segs = []
    content = format_transcript(segs, "/tmp/test.m4a", 60.0, "tiny.en")
    assert "tiny.en" in content
