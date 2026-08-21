#!/usr/bin/env python3
"""Command-line interface for NeoTranscribe.

Usage:
    python cli.py <audio_file> [--output <output_file>] [--key <api_key>]

If no output file is specified, saves to <audio_file>_transcript.txt
If no API key is provided, reads MISTRAL_API_KEY from environment or ~/.openclaw/.env
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from src.api_client import TranscriptionError, transcribe_file
from src.transcript import Transcript


def transcribe_with_retry(path: str, api_key: str, max_retries: int = 6) -> dict:
    """Call transcribe_file, waiting and retrying on rate limits (HTTP 429)."""
    delay = 30
    for attempt in range(max_retries + 1):
        try:
            return transcribe_file(path, api_key)
        except TranscriptionError as e:
            if e.status_code != 429 or attempt == max_retries:
                raise
            print(
                f"\n  Rate limited — waiting {delay}s before retrying "
                f"({attempt + 1}/{max_retries})...",
                flush=True,
            )
            time.sleep(delay)
            delay = min(delay * 2, 300)

# Lazy import chunker — requires pydub + ffmpeg which may not be available
_chunker = None

def _get_chunker():
    global _chunker
    if _chunker is None:
        try:
            from src import chunker
            _chunker = chunker
        except ImportError:
            return None
    return _chunker

def needs_chunking(path: str) -> bool:
    c = _get_chunker()
    if c is None:
        # Can't chunk without pydub — check size and warn
        size = os.path.getsize(path)
        if size > 100 * 1024 * 1024:
            print(
                f"WARNING: File is {size / 1024 / 1024:.0f} MB and chunking is unavailable "
                f"(pydub/ffmpeg not installed). Sending as single request — may timeout.",
                file=sys.stderr,
            )
        return False
    return c.needs_chunking(path)


def load_api_key() -> str | None:
    """Try to load API key from environment or .env file."""
    key = os.environ.get("MISTRAL_API_KEY")
    if key:
        return key

    env_path = os.path.expanduser("~/.openclaw/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("MISTRAL_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files using Mistral Voxtral with speaker diarization."
    )
    parser.add_argument("audio_file", help="Path to the audio file to transcribe")
    parser.add_argument(
        "-o", "--output", help="Output file path (default: <input>_transcript.txt)"
    )
    parser.add_argument(
        "-k", "--key", help="Mistral API key (default: from env or ~/.openclaw/.env)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Also save raw JSON response"
    )
    args = parser.parse_args()

    # Validate input
    audio_path = args.audio_file
    if not os.path.exists(audio_path):
        print(f"Error: File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    # Get API key
    api_key = args.key or load_api_key()
    if not api_key:
        print(
            "Error: No API key found. Provide --key, set MISTRAL_API_KEY env var, "
            "or add it to ~/.openclaw/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    # Set up output path
    stem = Path(audio_path).stem
    output_path = args.output or f"{stem}_transcript.txt"

    print(f"Input:  {audio_path} ({_format_size(os.path.getsize(audio_path))})")
    print(f"Output: {output_path}")
    print()

    try:
        if needs_chunking(audio_path):
            result = _transcribe_chunked(audio_path, api_key)
        else:
            print("Transcribing...")
            result = transcribe_with_retry(audio_path, api_key)
            print("Done.")
    except TranscriptionError as e:
        print(f"\nTranscription error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)

    # Save raw JSON if requested
    if args.json:
        import json

        json_path = f"{stem}_transcript.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Raw JSON saved to: {json_path}")

    # Build transcript and export
    transcript = Transcript.from_api_response(result)
    export_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = transcript.format_export(Path(audio_path).name, export_date)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Summary
    speakers = transcript.get_speaker_ids()
    segments = len(transcript.segments)
    print()
    print(f"Transcript saved to: {output_path}")
    print(f"Speakers detected:   {len(speakers)} ({', '.join(speakers)})")
    print(f"Segments:            {segments}")


def _transcribe_chunked(audio_path: str, api_key: str) -> dict:
    """Handle chunked transcription with progress output."""
    c = _get_chunker()
    if c is None:
        raise TranscriptionError("Chunking requires pydub and ffmpeg. Install them or use a smaller file.")

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"File is {size_mb:.0f} MB — splitting into chunks...")

    chunk_paths = c.split_audio(audio_path, progress_callback=lambda msg: print(f"  {msg}"))
    total = len(chunk_paths)
    print(f"Split into {total} chunks.\n")

    chunk_results = []
    chunk_durations = []
    try:
        for i, chunk_path in enumerate(chunk_paths, 1):
            print(f"Transcribing chunk {i}/{total}...", end=" ", flush=True)
            result = transcribe_with_retry(chunk_path, api_key)
            chunk_results.append(result)
            chunk_durations.append(c.get_duration_s(chunk_path))
            print("done.")
    finally:
        c.cleanup_chunks(chunk_paths)

    print("\nStitching chunks together...")
    return c.stitch_segments(chunk_results, chunk_durations)


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


if __name__ == "__main__":
    main()
