"""Main application window for Voxtral Transcriber."""

import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import get_api_key, set_api_key
from .transcript import Transcript
from .worker import TranscriptionWorker

ACCEPTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


class DropZone(QLabel):
    """A label that accepts drag-and-drop of audio files."""

    file_dropped = None  # Set by parent

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(100)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QLabel {"
            "  border: 2px dashed #aaa;"
            "  border-radius: 8px;"
            "  padding: 20px;"
            "  color: #666;"
            "  background-color: #fafafa;"
            "}"
        )
        self._set_default_text()

    def _set_default_text(self):
        self.setText(
            "Drag and drop an audio file here\n\n"
            "Supported: MP3, WAV, M4A, FLAC, OGG"
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and self._is_valid_file(urls[0].toLocalFile()):
                event.acceptProposedAction()
                self.setStyleSheet(
                    "QLabel {"
                    "  border: 2px dashed #4a90d9;"
                    "  border-radius: 8px;"
                    "  padding: 20px;"
                    "  color: #4a90d9;"
                    "  background-color: #e8f0fe;"
                    "}"
                )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "QLabel {"
            "  border: 2px dashed #aaa;"
            "  border-radius: 8px;"
            "  padding: 20px;"
            "  color: #666;"
            "  background-color: #fafafa;"
            "}"
        )

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            "QLabel {"
            "  border: 2px dashed #aaa;"
            "  border-radius: 8px;"
            "  padding: 20px;"
            "  color: #666;"
            "  background-color: #fafafa;"
            "}"
        )
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if self._is_valid_file(file_path) and self.file_dropped:
                self.file_dropped(file_path)

    def _is_valid_file(self, path: str) -> bool:
        return Path(path).suffix.lower() in ACCEPTED_EXTENSIONS


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voxtral Transcriber")
        self.resize(800, 600)

        self._selected_file: str | None = None
        self._transcript: Transcript | None = None
        self._worker: TranscriptionWorker | None = None
        self._speaker_inputs: dict[str, QLineEdit] = {}

        self._build_menu()
        self._build_ui()
        self._build_status_bar()

        # Check API key on startup
        if not get_api_key():
            # Use a timer so the window renders first
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(300, self._prompt_api_key)

    # ── Menu ──────────────────────────────────────────────────────────

    def _build_menu(self):
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu("&Settings")

        api_key_action = QAction("Set API &Key...", self)
        api_key_action.triggered.connect(self._prompt_api_key)
        settings_menu.addAction(api_key_action)

    def _prompt_api_key(self):
        from PyQt6.QtWidgets import QInputDialog

        current = get_api_key()
        # Mask the current key for display
        display = current[:8] + "..." if len(current) > 8 else current
        key, ok = QInputDialog.getText(
            self,
            "Mistral API Key",
            "Enter your Mistral API key:"
            + (f"\n\nCurrent: {display}" if current else ""),
            QLineEdit.EchoMode.Normal,
            "" if current else "",
        )
        if ok and key.strip():
            set_api_key(key.strip())
            self._set_status("API key saved.")

    # ── Main UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── File Input Section ──
        file_group = QGroupBox("Audio File")
        file_layout = QVBoxLayout(file_group)

        self._drop_zone = DropZone()
        self._drop_zone.file_dropped = self._on_file_selected
        file_layout.addWidget(self._drop_zone)

        btn_row = QHBoxLayout()
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._browse_file)
        btn_row.addWidget(self._browse_btn)

        self._file_info_label = QLabel("")
        btn_row.addWidget(self._file_info_label, 1)

        self._transcribe_btn = QPushButton("Transcribe")
        self._transcribe_btn.setEnabled(False)
        self._transcribe_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #4a90d9;"
            "  color: white;"
            "  padding: 6px 20px;"
            "  border-radius: 4px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:disabled {"
            "  background-color: #ccc;"
            "  color: #888;"
            "}"
            "QPushButton:hover:!disabled {"
            "  background-color: #357abd;"
            "}"
        )
        self._transcribe_btn.clicked.connect(self._start_transcription)
        btn_row.addWidget(self._transcribe_btn)

        file_layout.addLayout(btn_row)
        layout.addWidget(file_group)

        # ── Transcript Preview ──
        preview_group = QGroupBox("Transcript")
        preview_layout = QVBoxLayout(preview_group)

        self._transcript_view = QTextEdit()
        self._transcript_view.setReadOnly(True)
        self._transcript_view.setPlaceholderText(
            "Transcript will appear here after transcription..."
        )
        self._transcript_view.setStyleSheet(
            "QTextEdit { font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; }"
        )
        preview_layout.addWidget(self._transcript_view)

        layout.addWidget(preview_group, 1)  # stretch

        # ── Speaker Mapping ──
        self._speaker_group = QGroupBox("Speaker Mapping")
        self._speaker_layout = QVBoxLayout(self._speaker_group)

        self._speaker_scroll = QScrollArea()
        self._speaker_scroll.setWidgetResizable(True)
        self._speaker_scroll_content = QWidget()
        self._speaker_grid = QGridLayout(self._speaker_scroll_content)
        self._speaker_scroll.setWidget(self._speaker_scroll_content)
        self._speaker_layout.addWidget(self._speaker_scroll)

        speaker_btn_row = QHBoxLayout()
        self._apply_names_btn = QPushButton("Apply Names")
        self._apply_names_btn.clicked.connect(self._apply_speaker_names)
        speaker_btn_row.addStretch()
        speaker_btn_row.addWidget(self._apply_names_btn)
        self._speaker_layout.addLayout(speaker_btn_row)

        self._speaker_group.setVisible(False)
        layout.addWidget(self._speaker_group)

        # ── Export ──
        export_row = QHBoxLayout()
        export_row.addStretch()
        self._export_btn = QPushButton("Export Transcript")
        self._export_btn.setEnabled(False)
        self._export_btn.setStyleSheet(
            "QPushButton {"
            "  padding: 6px 20px;"
            "  border-radius: 4px;"
            "}"
        )
        self._export_btn.clicked.connect(self._export_transcript)
        export_row.addWidget(self._export_btn)
        layout.addLayout(export_row)

    # ── Status Bar ────────────────────────────────────────────────────

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._set_status("Ready")

    def _set_status(self, text: str):
        self._status_bar.showMessage(text)

    # ── File Selection ────────────────────────────────────────────────

    def _browse_file(self):
        filter_str = "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "", filter_str
        )
        if path:
            self._on_file_selected(path)

    def _on_file_selected(self, path: str):
        self._selected_file = path
        name = Path(path).name
        size = os.path.getsize(path)
        size_str = self._format_size(size)
        self._file_info_label.setText(f"{name} ({size_str})")
        self._drop_zone.setText(f"Selected: {name}")
        self._transcribe_btn.setEnabled(True)
        self._set_status(f"File selected: {name}")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    # ── Transcription ─────────────────────────────────────────────────

    def _start_transcription(self):
        api_key = get_api_key()
        if not api_key:
            self._prompt_api_key()
            api_key = get_api_key()
            if not api_key:
                return

        if not self._selected_file:
            return

        # Disable controls during transcription
        self._transcribe_btn.setEnabled(False)
        self._browse_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._speaker_group.setVisible(False)
        self._transcript_view.clear()

        self._set_status("Transcribing...")

        self._worker = TranscriptionWorker(self._selected_file, api_key)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_transcription_done)
        self._worker.error.connect(self._on_transcription_error)
        self._worker.start()

    def _on_progress(self, message: str):
        self._set_status(message)

    def _on_transcription_done(self, transcript: Transcript):
        self._transcript = transcript
        self._worker = None

        # Show transcript
        self._transcript_view.setPlainText(transcript.format_transcript())

        # Build speaker mapping UI
        self._build_speaker_mapping(transcript)

        # Re-enable controls
        self._transcribe_btn.setEnabled(True)
        self._browse_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
        self._set_status("Transcription complete.")

    def _on_transcription_error(self, message: str):
        self._worker = None
        self._transcribe_btn.setEnabled(True)
        self._browse_btn.setEnabled(True)
        self._set_status("Error")
        QMessageBox.critical(self, "Transcription Error", message)

    # ── Speaker Mapping ───────────────────────────────────────────────

    def _build_speaker_mapping(self, transcript: Transcript):
        # Clear existing widgets from grid
        while self._speaker_grid.count():
            item = self._speaker_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._speaker_inputs.clear()
        speaker_ids = transcript.get_speaker_ids()

        if not speaker_ids:
            self._speaker_group.setVisible(False)
            return

        for row, sid in enumerate(speaker_ids):
            label = QLabel(f"{transcript.get_display_name(sid)}:")
            label.setMinimumWidth(100)
            self._speaker_grid.addWidget(label, row, 0)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText("Enter real name...")
            line_edit.setText(transcript.get_display_name(sid))
            self._speaker_grid.addWidget(line_edit, row, 1)
            self._speaker_inputs[sid] = line_edit

        self._speaker_group.setVisible(True)

    def _apply_speaker_names(self):
        if not self._transcript:
            return

        for sid, line_edit in self._speaker_inputs.items():
            name = line_edit.text().strip()
            if name:
                self._transcript.set_display_name(sid, name)

        # Refresh the transcript view
        self._transcript_view.setPlainText(self._transcript.format_transcript())
        self._set_status("Speaker names updated.")

    # ── Export ─────────────────────────────────────────────────────────

    def _export_transcript(self):
        if not self._transcript or not self._selected_file:
            return

        original_name = Path(self._selected_file).stem
        default_name = f"{original_name}_transcript.txt"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Transcript",
            default_name,
            "Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        export_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = self._transcript.format_export(
            Path(self._selected_file).name, export_date
        )

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._set_status(f"Exported to {Path(path).name}")
        except OSError as e:
            QMessageBox.critical(self, "Export Error", f"Could not save file:\n{e}")
