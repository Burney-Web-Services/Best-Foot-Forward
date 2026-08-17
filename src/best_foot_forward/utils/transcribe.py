"""
transcribe.py — Local audio transcription with speaker diarization.

Transcribes an audio recording locally using:
  - faster-whisper for ASR (speech-to-text)
  - pyannote.audio for speaker diarization (who spoke when)

Output is a markdown file with timestamped, speaker-labeled segments.

SETUP (one-time):
  1. Confirm ffmpeg is installed (required for audio decoding):
       which ffmpeg     # if missing: sudo apt install ffmpeg

  2. Install Python deps (CPU-only torch — much smaller download):
       uv sync --group audio    # from the project root

  3. Accept HuggingFace model terms — both of these are required:
       https://huggingface.co/pyannote/speaker-diarization-3.1
       https://huggingface.co/pyannote/speaker-diarization-community-1

  4. Generate a HuggingFace read-only token:
       https://huggingface.co/settings/tokens

  5. Export the token (add to ~/.bashrc for persistence):
       export HF_TOKEN=hf_your_token_here

USAGE:
  python3 src/best_foot_forward/utils/transcribe.py interview.m4a
  python3 src/best_foot_forward/utils/transcribe.py interview.m4a -m small.en -n 2
  python3 src/best_foot_forward/utils/transcribe.py interview.m4a -o /custom/output/dir

MODEL SPEED REFERENCE (CPU, ~40-min recording):
  tiny.en   ~3-5 min   — fast sanity check, lower accuracy
  base.en   ~8-12 min  — recommended default, solid English accuracy
  small.en  ~20-25 min — better on names, jargon, numbers
  medium.en ~45-60 min — high quality, slow on CPU
  large-v3  ~90+ min   — best quality, very slow on CPU

Speaker labels (SPEAKER_00, SPEAKER_01) can be renamed via find-replace
in any text editor after reviewing the transcript.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    from best_foot_forward.utils.slugify import slugify  # package import (tests, installed)
except ImportError:
    from slugify import slugify  # script invocation (utils/ in sys.path)

try:
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="pyannote.audio.core.io")
    warnings.filterwarnings("ignore", message="std\\(\\): degrees of freedom")
    # torch 2.12+cu130 warns when the installed driver doesn't support CUDA 13;
    # we run CPU-only on this machine so the warning is irrelevant.
    warnings.filterwarnings("ignore", message="CUDA initialization.*driver.*too old", category=UserWarning)
    from faster_whisper import WhisperModel
    from pyannote.audio import Pipeline
except ImportError as e:
    print(f"ERROR: Missing dependency — {e}", file=sys.stderr)
    print("", file=sys.stderr)
    print("From the project root, run:", file=sys.stderr)
    print("  uv sync --group audio", file=sys.stderr)
    sys.exit(1)

import torch as _torch
_DEVICE = "cpu"
_COMPUTE_TYPE = "int8"
if _torch.cuda.is_available():
    _cc = _torch.cuda.get_device_capability(0)
    if _cc[0] >= 6:
        # CUDA 12 (required by CTranslate2 4.x) dropped Maxwell (SM 5.x) support.
        # SM 6.0+ (Pascal and newer) works; SM 5.x silently fails during inference.
        _DEVICE = "cuda"
        _COMPUTE_TYPE = "float16" if _cc[0] >= 7 else "float32"

SUPPORTED_FORMATS = {".mp3", ".mp4", ".m4a", ".wav", ".flac", ".ogg", ".webm"}
VALID_MODELS = [
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "medium", "medium.en",
    "large-v2", "large-v3",
]

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = str(_PROJECT_ROOT / "data" / "media" / "transcripts")

# Make db module importable from this script
sys.path.insert(0, str(_PROJECT_ROOT / "src" / "best_foot_forward"))
try:
    from db import register_file as _register_file
except Exception:
    _register_file = None


def _fmt_ts(seconds, long=False):
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if long or h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def check_env():
    if not os.environ.get("HF_TOKEN"):
        print("ERROR: HF_TOKEN environment variable not set.", file=sys.stderr)
        print("", file=sys.stderr)
        print("pyannote.audio requires a HuggingFace token to load the diarization model.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Steps to fix:", file=sys.stderr)
        print("  1. Create a free account at https://huggingface.co", file=sys.stderr)
        print("  2. Accept model terms at:", file=sys.stderr)
        print("       https://huggingface.co/pyannote/speaker-diarization-3.1", file=sys.stderr)
        print("       https://huggingface.co/pyannote/speaker-diarization-community-1", file=sys.stderr)
        print("  3. Generate a token at https://huggingface.co/settings/tokens", file=sys.stderr)
        print("  4. Run: export HF_TOKEN=hf_your_token_here", file=sys.stderr)
        sys.exit(1)


def load_audio(path):
    p = Path(path)
    if not p.exists():
        print(f"ERROR: Audio file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if p.suffix.lower() not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        print(f"ERROR: Unsupported format '{p.suffix}'. Supported: {supported}", file=sys.stderr)
        sys.exit(1)
    return str(p.resolve())


def transcribe_audio(audio_path, model_size):
    global _DEVICE, _COMPUTE_TYPE

    def _run(device, compute_type):
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("Transcribing audio...", file=sys.stderr)
        gen, info = model.transcribe(audio_path, beam_size=5)
        segs = []
        for seg in gen:
            if seg.text.strip():
                segs.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        return segs, info.duration

    print(f"Loading ASR model ({model_size}) on {_DEVICE}...", file=sys.stderr)
    try:
        return _run(_DEVICE, _COMPUTE_TYPE)
    except RuntimeError as e:
        if _DEVICE == "cuda":
            print(f"  CUDA device error — falling back to CPU ({e})", file=sys.stderr)
            print("  Tip: fix with: flatpak override --user com.vscodium.codium --device=all", file=sys.stderr)
            _DEVICE = "cpu"
            _COMPUTE_TYPE = "int8"
            print("Retrying ASR on cpu...", file=sys.stderr)
            return _run("cpu", "int8")
        raise


def _decode_audio(audio_path):
    """Decode any audio format to a (1, T) float32 tensor at 16 kHz via ffmpeg.

    Bypasses torchaudio/torchcodec entirely — both use CUDA libs that don't exist
    on CPU-only torch installs. Uses ffmpeg (system dep) + stdlib wave module instead.
    """
    import subprocess
    import tempfile
    import wave
    import numpy as np
    import torch

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_path, "-y"],
            check=True, capture_output=True,
        )
        with wave.open(tmp_path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            sample_rate = wf.getframerate()
        waveform = torch.from_numpy(data).unsqueeze(0)  # (1, samples)
    finally:
        os.unlink(tmp_path)
    return waveform, sample_rate


def diarize_audio(audio_path, num_speakers):
    import pyannote.audio as _pann
    _pann_major = int(_pann.__version__.split(".")[0])

    print("Loading diarization model...", file=sys.stderr)
    try:
        token = os.environ["HF_TOKEN"]
        if _pann_major >= 4:
            pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=token)
        else:
            pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "unauthorized" in msg or "forbidden" in msg or "403" in msg or "gated" in msg:
            print("ERROR: HuggingFace access denied.", file=sys.stderr)
            print("Make sure your HF_TOKEN is valid and you have accepted terms for BOTH:", file=sys.stderr)
            print("  https://huggingface.co/pyannote/speaker-diarization-3.1", file=sys.stderr)
            print("  https://huggingface.co/pyannote/speaker-diarization-community-1", file=sys.stderr)
        else:
            print(f"ERROR: Could not load diarization model — {e}", file=sys.stderr)
            print("Check your internet connection and HF_TOKEN.", file=sys.stderr)
        sys.exit(1)

    pipeline = pipeline.to(_torch.device(_DEVICE))
    print(f"Running speaker diarization on {_DEVICE}...", file=sys.stderr)
    waveform, sample_rate = _decode_audio(audio_path)
    audio_input = {"waveform": waveform, "sample_rate": sample_rate}
    kwargs = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    diarization = pipeline(audio_input, **kwargs)

    # pyannote 4.x returns DiarizeOutput with .exclusive_speaker_diarization;
    # pyannote 3.x returns Annotation directly.
    annotation = getattr(diarization, "exclusive_speaker_diarization", diarization)
    turns = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        turns.append({"start": turn.start, "end": turn.end, "speaker": speaker})
    return turns


def assign_speakers(whisper_segments, diarization):
    result = []
    for seg in whisper_segments:
        best_speaker, best_overlap = "UNKNOWN", 0.0
        for turn in diarization:
            overlap = max(0.0, min(seg["end"], turn["end"]) - max(seg["start"], turn["start"]))
            if overlap > best_overlap:
                best_overlap, best_speaker = overlap, turn["speaker"]
        result.append({**seg, "speaker": best_speaker})
    return result


def format_transcript(segments, audio_path, duration, model_size):
    audio_name = Path(audio_path).name
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    duration_str = _fmt_ts(duration, long=True)
    speaker_count = len({s["speaker"] for s in segments})
    long_ts = duration >= 3600

    lines = [
        f"# Transcript: {audio_name}",
        f"**Date:** {now}",
        f"**Duration:** {duration_str}",
        f"**Speakers detected:** {speaker_count}",
        f"**Model:** whisper {model_size}",
        f"**Source:** {audio_path}",
        "",
        "---",
        "",
        "## Transcript",
        "",
    ]

    for seg in segments:
        ts = _fmt_ts(seg["start"], long=long_ts)
        lines.append(f"**[{ts}] {seg['speaker']}:** {seg['text']}")
        lines.append("")

    return "\n".join(lines)


def write_output(content, output_dir, audio_path):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(audio_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = out / f"{stem}_{timestamp}.md"
    dest.write_text(content, encoding="utf-8")
    return str(dest)


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file with speaker diarization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python3 transcribe.py interview.m4a -m small.en -n 2",
    )
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument(
        "-m", "--model",
        default="base.en",
        choices=VALID_MODELS,
        metavar="MODEL",
        help=f"Whisper model size (default: base.en). Choices: {', '.join(VALID_MODELS)}",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        metavar="DIR",
        help="Output directory (overrides --company/--role if both provided)",
    )
    parser.add_argument(
        "-n", "--num-speakers",
        type=int,
        default=None,
        metavar="N",
        help="Hint for number of speakers (default: auto-detect)",
    )
    parser.add_argument(
        "--company",
        default=None,
        metavar="COMPANY",
        help="Company name — routes transcript to data/applications/{company}/{role}/",
    )
    parser.add_argument(
        "--role",
        default=None,
        metavar="ROLE",
        help="Role slug (spaces OK) — used with --company to route to the application directory",
    )
    args = parser.parse_args()

    # Resolve output directory: explicit -o > --company/--role > default
    if args.output_dir:
        out_dir = args.output_dir
    elif args.company and args.role:
        out_dir = str(_PROJECT_ROOT / "data" / "applications" / slugify(args.company) / slugify(args.role))
    else:
        out_dir = DEFAULT_OUTPUT_DIR

    check_env()
    audio_path = load_audio(args.audio_file)
    whisper_segs, duration = transcribe_audio(audio_path, args.model)
    diarization = diarize_audio(audio_path, args.num_speakers)
    segments = assign_speakers(whisper_segs, diarization)
    content = format_transcript(segments, audio_path, duration, args.model)
    output_path = write_output(content, out_dir, audio_path)
    print(f"\nTranscript saved to: {output_path}", file=sys.stderr)
    print(output_path)

    if _register_file:
        source_stem = Path(args.audio_file).stem
        summary = f"Transcript: {source_stem}"
        if args.company and args.role:
            summary = f"Transcript ({args.company} – {args.role}): {source_stem}"
        _register_file(output_path, "transcript", summary)


if __name__ == "__main__":
    main()
