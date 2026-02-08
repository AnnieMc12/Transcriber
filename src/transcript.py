"""Transcript data model and formatting utilities."""

from dataclasses import dataclass, field


@dataclass
class Segment:
    """A single transcription segment."""

    text: str
    start: float
    end: float
    speaker_id: str
    type: str = "transcription"


@dataclass
class Transcript:
    """Holds the full transcription result and speaker mapping."""

    segments: list[Segment] = field(default_factory=list)
    full_text: str = ""
    speaker_map: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, response: dict) -> "Transcript":
        """Parse a Mistral API response (or stitched result) into a Transcript."""
        segments = []
        for seg in response.get("segments", []):
            segments.append(
                Segment(
                    text=seg.get("text", "").strip(),
                    start=seg.get("start", 0.0),
                    end=seg.get("end", 0.0),
                    speaker_id=seg.get("speaker_id", "unknown"),
                    type=seg.get("type", "transcription"),
                )
            )
        transcript = cls(
            segments=segments,
            full_text=response.get("text", ""),
        )
        # Initialize speaker_map with all detected speaker IDs
        for seg in segments:
            if seg.speaker_id not in transcript.speaker_map:
                transcript.speaker_map[seg.speaker_id] = _display_name(
                    seg.speaker_id
                )
        return transcript

    def get_speaker_ids(self) -> list[str]:
        """Return sorted list of unique speaker IDs."""
        return sorted(self.speaker_map.keys())

    def get_display_name(self, speaker_id: str) -> str:
        """Return the mapped display name for a speaker ID."""
        return self.speaker_map.get(speaker_id, _display_name(speaker_id))

    def set_display_name(self, speaker_id: str, name: str):
        """Update the display name for a speaker ID."""
        self.speaker_map[speaker_id] = name

    def format_timestamp(self, seconds: float) -> str:
        """Format seconds as [HH:MM:SS]."""
        total = int(seconds)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"[{h:02d}:{m:02d}:{s:02d}]"

    def format_transcript(self) -> str:
        """Format the transcript with timestamps and speaker names."""
        lines = []
        for seg in self.segments:
            if seg.type != "transcription":
                continue
            ts = self.format_timestamp(seg.start)
            name = self.get_display_name(seg.speaker_id)
            lines.append(f"{ts} {name}: {seg.text}")
        return "\n".join(lines)

    def format_export(self, original_filename: str, export_date: str) -> str:
        """Format for file export with header."""
        speaker_names = []
        for sid in self.get_speaker_ids():
            speaker_names.append(self.get_display_name(sid))

        header = (
            f"TRANSCRIPT: {original_filename}\n"
            f"Date: {export_date}\n"
            f"Speakers: {', '.join(speaker_names)}\n"
            f"\n---\n\n"
        )
        return header + self.format_transcript() + "\n"


def _display_name(speaker_id: str) -> str:
    """Convert a speaker_id like 'speaker_1' into 'Speaker 1'."""
    parts = speaker_id.split("_")
    if len(parts) == 2 and parts[0].lower() == "speaker":
        return f"Speaker {parts[1]}"
    return speaker_id.replace("_", " ").title()
