"""Audio file chunking for large files.

Chunk extraction streams through ffmpeg/ffprobe subprocesses so that
long recordings never need to be decoded into memory at once (a 3-hour
MP3 decodes to ~2 GB of raw PCM, which can OOM-kill the process).
"""

import os
import subprocess
import tempfile
from pathlib import Path

# Threshold in bytes (100 MB)
SIZE_THRESHOLD = 100 * 1024 * 1024

# Chunk duration in milliseconds (30 minutes)
CHUNK_DURATION_MS = 30 * 60 * 1000

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def needs_chunking(file_path: str) -> bool:
    """Return True if the file exceeds the size threshold."""
    return os.path.getsize(file_path) > SIZE_THRESHOLD


def get_duration_s(file_path: str) -> float:
    """Return the duration of an audio file in seconds via ffprobe.

    Reads metadata only — does not decode the audio.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def split_audio(file_path: str, progress_callback=None) -> list[str]:
    """Split an audio file into ~30-minute chunks.

    Returns a list of temporary file paths for the chunks.
    The caller is responsible for cleaning up the temp files.

    Chunks are exported as 16 kHz mono MP3 — plenty for speech models,
    and it keeps each 30-minute chunk well under API upload limits.

    progress_callback(message: str) is called with status updates.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported audio format: {ext}")

    if progress_callback:
        progress_callback("Reading audio duration...")

    total_s = get_duration_s(file_path)
    chunk_s = CHUNK_DURATION_MS / 1000
    chunks = []
    start = 0.0
    chunk_index = 0

    temp_dir = tempfile.mkdtemp(prefix="voxtral_chunks_")

    while start < total_s:
        end = min(start + chunk_s, total_s)
        chunk_index += 1
        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index:03d}.mp3")

        if progress_callback:
            progress_callback(f"Exporting chunk {chunk_index}...")

        # Decode only [start, end) — memory stays constant regardless of
        # total file length.
        subprocess.run(
            [
                "ffmpeg", "-nostdin", "-v", "error",
                "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                "-i", file_path,
                "-ac", "1", "-ar", "16000", "-b:a", "64k",
                "-y", chunk_path,
            ],
            check=True,
            capture_output=True,
        )
        chunks.append(chunk_path)
        start = end

    return chunks


def get_chunk_count(file_path: str) -> int:
    """Return the number of chunks the file will be split into."""
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return 1

    try:
        total_ms = get_duration_s(file_path) * 1000
        count = int((total_ms + CHUNK_DURATION_MS - 1) // CHUNK_DURATION_MS)
        return max(count, 1)
    except Exception:
        # Rough estimate from file size: ~1 MB per minute for 128kbps mp3
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        count = int(size_mb / 30) + 1
        return max(count, 1)


def stitch_segments(
    chunk_results: list[dict],
    chunk_durations: list[float] | None = None,
) -> dict:
    """Combine transcription results from multiple chunks.

    Adjusts timestamps so they are continuous across chunks.

    Args:
        chunk_results: Parsed API responses, one per chunk, in order.
        chunk_durations: Actual duration in seconds of each chunk file.
            When provided, offsets advance by the real chunk length;
            otherwise falls back to the last segment's end time (which
            drifts if a chunk ends in silence).

    Returns a single combined result dict with 'text' and 'segments'.
    """
    combined_text_parts = []
    combined_segments = []
    time_offset = 0.0

    for i, result in enumerate(chunk_results):
        combined_text_parts.append(result.get("text", ""))

        segments = result.get("segments", [])
        for seg in segments:
            adjusted = dict(seg)
            adjusted["start"] = seg.get("start", 0.0) + time_offset
            adjusted["end"] = seg.get("end", 0.0) + time_offset
            combined_segments.append(adjusted)

        if chunk_durations is not None and i < len(chunk_durations):
            time_offset += chunk_durations[i]
        elif segments:
            time_offset += max(s.get("end", 0.0) for s in segments)

    return {
        "text": " ".join(combined_text_parts),
        "segments": combined_segments,
    }


def cleanup_chunks(chunk_paths: list[str]):
    """Remove temporary chunk files and their parent directory."""
    if not chunk_paths:
        return
    parent = None
    for path in chunk_paths:
        try:
            if os.path.exists(path):
                parent = os.path.dirname(path)
                os.remove(path)
        except OSError:
            pass
    if parent:
        try:
            os.rmdir(parent)
        except OSError:
            pass
