"""Audio file chunking for large files."""

import os
import tempfile
from pathlib import Path

from pydub import AudioSegment

# Threshold in bytes (100 MB)
SIZE_THRESHOLD = 100 * 1024 * 1024

# Chunk duration in milliseconds (30 minutes)
CHUNK_DURATION_MS = 30 * 60 * 1000

FORMAT_MAP = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".m4a": "mp4",
    ".flac": "flac",
    ".ogg": "ogg",
}


def needs_chunking(file_path: str) -> bool:
    """Return True if the file exceeds the size threshold."""
    return os.path.getsize(file_path) > SIZE_THRESHOLD


def split_audio(file_path: str, progress_callback=None) -> list[str]:
    """Split an audio file into ~30-minute chunks.

    Returns a list of temporary file paths for the chunks.
    The caller is responsible for cleaning up the temp files.

    progress_callback(message: str) is called with status updates.
    """
    ext = Path(file_path).suffix.lower()
    fmt = FORMAT_MAP.get(ext)
    if fmt is None:
        raise ValueError(f"Unsupported audio format: {ext}")

    if progress_callback:
        progress_callback("Loading audio file for splitting...")

    audio = AudioSegment.from_file(file_path, format=fmt)
    total_duration = len(audio)
    chunks = []
    start = 0
    chunk_index = 0

    temp_dir = tempfile.mkdtemp(prefix="voxtral_chunks_")

    while start < total_duration:
        end = min(start + CHUNK_DURATION_MS, total_duration)
        chunk = audio[start:end]
        chunk_index += 1

        # Export chunks as mp3 to keep file sizes manageable
        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index:03d}.mp3")
        if progress_callback:
            progress_callback(
                f"Exporting chunk {chunk_index}..."
            )
        chunk.export(chunk_path, format="mp3", bitrate="128k")
        chunks.append(chunk_path)
        start = end

    return chunks


def get_chunk_count(file_path: str) -> int:
    """Estimate the number of chunks without loading the full file.

    Uses file duration estimation based on file size and bitrate heuristics.
    Falls back to loading the file if needed.
    """
    ext = Path(file_path).suffix.lower()
    fmt = FORMAT_MAP.get(ext)
    if fmt is None:
        return 1

    try:
        audio = AudioSegment.from_file(file_path, format=fmt)
        total_duration = len(audio)
        count = (total_duration + CHUNK_DURATION_MS - 1) // CHUNK_DURATION_MS
        return max(count, 1)
    except Exception:
        # If we can't determine, assume a rough estimate from file size
        # ~1 MB per minute for mp3 at 128kbps
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        estimated_minutes = size_mb  # rough 1:1 ratio
        count = int(estimated_minutes / 30) + 1
        return max(count, 1)


def stitch_segments(chunk_results: list[dict]) -> dict:
    """Combine transcription results from multiple chunks.

    Adjusts timestamps so they are continuous across chunks.
    Returns a single combined result dict with 'text' and 'segments'.
    """
    combined_text_parts = []
    combined_segments = []
    time_offset = 0.0

    for result in chunk_results:
        combined_text_parts.append(result.get("text", ""))

        segments = result.get("segments", [])
        if not segments:
            continue

        for seg in segments:
            adjusted = dict(seg)
            adjusted["start"] = seg.get("start", 0.0) + time_offset
            adjusted["end"] = seg.get("end", 0.0) + time_offset
            combined_segments.append(adjusted)

        # Advance the offset to the end of the last segment in this chunk
        last_end = max(s.get("end", 0.0) for s in segments)
        time_offset += last_end

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
