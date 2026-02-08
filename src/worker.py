"""Background worker for transcription tasks."""

from PyQt6.QtCore import QThread, pyqtSignal

from .api_client import TranscriptionError, transcribe_file
from .chunker import (
    cleanup_chunks,
    needs_chunking,
    split_audio,
    stitch_segments,
)
from .transcript import Transcript


class TranscriptionWorker(QThread):
    """Runs transcription in a background thread.

    Signals:
        progress(str): Status message updates.
        finished(Transcript): Emitted on successful completion.
        error(str): Emitted on failure with an error message.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # Transcript
    error = pyqtSignal(str)

    def __init__(self, file_path: str, api_key: str):
        super().__init__()
        self.file_path = file_path
        self.api_key = api_key
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._do_transcription()
        except TranscriptionError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")

    def _do_transcription(self):
        if needs_chunking(self.file_path):
            self._transcribe_chunked()
        else:
            self._transcribe_single()

    def _transcribe_single(self):
        self.progress.emit("Transcribing audio...")
        result = transcribe_file(self.file_path, self.api_key)
        if self._cancelled:
            return
        transcript = Transcript.from_api_response(result)
        self.finished.emit(transcript)

    def _transcribe_chunked(self):
        self.progress.emit("File exceeds 100 MB — splitting into chunks...")

        def on_split_progress(msg):
            self.progress.emit(msg)

        chunk_paths = split_audio(self.file_path, progress_callback=on_split_progress)

        if self._cancelled:
            cleanup_chunks(chunk_paths)
            return

        total = len(chunk_paths)
        self.progress.emit(f"Split into {total} chunks. Starting transcription...")

        chunk_results = []
        try:
            for i, chunk_path in enumerate(chunk_paths, 1):
                if self._cancelled:
                    break
                self.progress.emit(f"Transcribing chunk {i} of {total}...")
                result = transcribe_file(chunk_path, self.api_key)
                chunk_results.append(result)
        finally:
            cleanup_chunks(chunk_paths)

        if self._cancelled:
            return

        self.progress.emit("Stitching chunks together...")
        combined = stitch_segments(chunk_results)
        transcript = Transcript.from_api_response(combined)
        self.finished.emit(transcript)
