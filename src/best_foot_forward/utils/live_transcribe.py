"""
live_transcribe.py — Live microphone capture with real-time Whisper transcription.

Records audio from the default microphone while transcribing in near-real-time.
Produces:
  1. A WAV file in data/recordings/ (always saved, even on Ctrl+C)
  2. Timestamped ASR text printed to the terminal as you speak

Diarization (speaker labels) is a post-processing step — run transcribe.py on
the saved WAV when the call is done.

SETUP:
  sudo apt install libportaudio2   # system dep for sounddevice
  uv sync --group audio

USAGE:
  uv run python src/best_foot_forward/utils/live_transcribe.py
  uv run python src/best_foot_forward/utils/live_transcribe.py -m small.en
  uv run python src/best_foot_forward/utils/live_transcribe.py --list-devices
  uv run python src/best_foot_forward/utils/live_transcribe.py -d 3 --window 8

POST-PROCESSING (add speaker labels after the call):
  uv run python src/best_foot_forward/utils/transcribe.py <saved.wav> -n 2

GPU NOTE:
  This machine has a NVIDIA Quadro M1200 (no driver currently installed).
  Installing the driver gives 8-15x faster transcription. Steps:
    sudo ubuntu-drivers autoinstall && sudo reboot
  Then update pyproject.toml to use the pytorch-cuda index instead of pytorch-cpu,
  and change device="cpu" to device="cuda" in this file and transcribe.py.
"""

import os
import sys
import argparse
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import warnings
    warnings.filterwarnings("ignore", message="CUDA initialization.*driver.*too old", category=UserWarning)
    import numpy as np
    import soundfile as sf
    from faster_whisper import WhisperModel
    import sounddevice as sd
except ImportError as e:
    print(f"ERROR: Missing Python dependency — {e}", file=sys.stderr)
    print("  uv sync --group audio", file=sys.stderr)
    sys.exit(1)
except OSError as e:
    if "PortAudio" in str(e):
        print("ERROR: PortAudio library not found.", file=sys.stderr)
        print("  sudo apt install libportaudio2", file=sys.stderr)
    else:
        print(f"ERROR: {e}", file=sys.stderr)
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

SAMPLE_RATE = 16000
DEFAULT_SILENCE_THRESHOLD = 0.01   # RMS ~-40 dBFS; speech is typically 0.02-0.3

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = str(_PROJECT_ROOT / "data" / "media" / "recordings")

VALID_MODELS = [
    "tiny", "tiny.en", "base", "base.en",
    "small", "small.en", "medium", "medium.en", "large-v3",
]


def _load_model(model_size):
    global _DEVICE, _COMPUTE_TYPE
    print(f"Loading transcription model ({model_size}) on {_DEVICE}...", file=sys.stderr)
    model = WhisperModel(model_size, device=_DEVICE, compute_type=_COMPUTE_TYPE)
    if _DEVICE == "cuda":
        # Smoke test: run a silent 1-second buffer to catch Flatpak GPU device access
        # failures before recording starts rather than crashing mid-session.
        try:
            silent = np.zeros(SAMPLE_RATE, dtype=np.float32)
            list(model.transcribe(silent, beam_size=1)[0])
        except RuntimeError as e:
            print(f"  CUDA device error — falling back to CPU ({e})", file=sys.stderr)
            print("  Tip: fix with: flatpak override --user com.vscodium.codium --device=all", file=sys.stderr)
            _DEVICE = "cpu"
            _COMPUTE_TYPE = "int8"
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return model


def list_devices():
    default_in = sd.default.device[0]
    print("Available audio input devices:\n")
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            marker = "  ← default" if i == default_in else ""
            print(f"  [{i:2d}] {dev['name']}{marker}")
    print("\nUse -d N to select a device by index.")


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))


def _fmt_ts(total_seconds: float) -> str:
    t = int(total_seconds)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


def transcription_worker(model, wav_path, transcript_path, window_samples, threshold, audio_q):
    """Read from audio_q, write to WAV + transcript file, and transcribe each window.

    Timestamps are based on audio sample count (accurate regardless of how long
    Whisper takes to process each window).
    """
    samples_in_prior_windows = 0
    window_buffer = []
    window_samples_collected = 0

    with (sf.SoundFile(wav_path, mode="w", samplerate=SAMPLE_RATE, channels=1, subtype="PCM_16") as wav,
          open(transcript_path, "w", encoding="utf-8") as txt):
        while True:
            try:
                chunk = audio_q.get(timeout=1.0)
            except queue.Empty:
                continue

            if chunk is None:
                _flush_buffer(model, window_buffer, window_samples_collected,
                              samples_in_prior_windows, threshold, txt)
                break

            # Write to disk immediately — constant memory regardless of recording length
            wav.write(chunk)
            wav.flush()

            window_buffer.append(chunk)
            window_samples_collected += len(chunk)

            if window_samples_collected >= window_samples:
                audio = np.concatenate(window_buffer).squeeze()
                if _rms(audio) > threshold:
                    ts = _fmt_ts(samples_in_prior_windows / SAMPLE_RATE)
                    segments, _ = model.transcribe(audio, beam_size=5, vad_filter=True)
                    for seg in segments:
                        text = seg.text.strip()
                        if text:
                            line = f"[{ts}] {text}"
                            print(line, flush=True)
                            txt.write(line + "\n")
                            txt.flush()

                samples_in_prior_windows += window_samples_collected
                window_buffer = []
                window_samples_collected = 0


def _flush_buffer(model, window_buffer, window_samples_collected,
                  samples_in_prior_windows, threshold, txt):
    if not window_buffer or window_samples_collected == 0:
        return
    audio = np.concatenate(window_buffer).squeeze()
    if _rms(audio) > threshold:
        ts = _fmt_ts(samples_in_prior_windows / SAMPLE_RATE)
        segments, _ = model.transcribe(audio, beam_size=5, vad_filter=True)
        for seg in segments:
            text = seg.text.strip()
            if text:
                line = f"[{ts}] {text}"
                print(line, flush=True)
                txt.write(line + "\n")
                txt.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Record microphone audio with live Whisper transcription.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Press Ctrl+C to stop and save the recording.",
    )
    parser.add_argument("--list-devices", action="store_true",
                        help="Print available input devices and exit")
    parser.add_argument("-m", "--model", default="base.en",
                        choices=VALID_MODELS, metavar="MODEL",
                        help=f"Whisper model size (default: base.en). Choices: {', '.join(VALID_MODELS)}")
    parser.add_argument("-w", "--window", type=float, default=6.0, metavar="SECS",
                        help="Audio window in seconds before each transcription pass (default: 6)")
    parser.add_argument("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, metavar="DIR",
                        help="Directory for WAV output (default: data/recordings/)")
    parser.add_argument("-d", "--device", type=int, default=None, metavar="N",
                        help="Input device index (default: system default; use --list-devices to see options)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_SILENCE_THRESHOLD, metavar="RMS",
                        help=f"RMS silence gate — windows below this are skipped (default: {DEFAULT_SILENCE_THRESHOLD})")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    # Create output dir and filename at start so partial recordings are always saved
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    wav_path = out_dir / f"recording_{stamp}.wav"
    transcript_path = out_dir / f"recording_{stamp}.txt"

    model = _load_model(args.model)

    window_samples = int(args.window * SAMPLE_RATE)
    audio_q = queue.Queue()

    def audio_callback(indata, frames, cb_time, status):
        if status:
            print(f"  [audio] {status}", file=sys.stderr)
        audio_q.put(indata.copy())

    worker = threading.Thread(
        target=transcription_worker,
        args=(model, wav_path, transcript_path, window_samples, args.threshold, audio_q),
        daemon=True,
    )

    device_label = f"device {args.device}" if args.device is not None else "default"
    print(f"Recording to: {wav_path}", file=sys.stderr)
    print(f"Model: {args.model}  |  Window: {args.window}s  |  Input: {device_label}", file=sys.stderr)
    print(f"Press Ctrl+D (or Ctrl+C) to stop.\n", file=sys.stderr)

    _stop = threading.Event()

    def _watch_stdin():
        try:
            sys.stdin.read()  # blocks until Ctrl+D (EOF)
        except OSError:
            pass
        _stop.set()

    threading.Thread(target=_watch_stdin, daemon=True).start()

    start_time = time.monotonic()

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            device=args.device, callback=audio_callback):
            worker.start()
            while not _stop.is_set():
                sd.sleep(200)
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        print("\nStopping...", file=sys.stderr)
        audio_q.put(None)
        try:
            worker.join(timeout=60)
        except KeyboardInterrupt:
            print("(interrupted — waiting up to 5s for file finalization...)", file=sys.stderr)
            worker.join(timeout=5)

    duration = _fmt_ts(time.monotonic() - start_time)
    print(f"\nSaved: {wav_path} ({duration})", file=sys.stderr)
    print(f"Transcript: {transcript_path}", file=sys.stderr)
    print(f"\nFor a diarized transcript with speaker labels, run:", file=sys.stderr)
    print(f"  uv run python src/best_foot_forward/utils/transcribe.py \\", file=sys.stderr)
    print(f"    {wav_path} -n 2", file=sys.stderr)


if __name__ == "__main__":
    main()
