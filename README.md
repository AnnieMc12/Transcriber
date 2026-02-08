# Voxtral Transcriber

A Windows desktop application for transcribing audio files using the Mistral API (Voxtral Mini model) with speaker diarization.

## Features

- Transcribe audio files (MP3, WAV, M4A, FLAC, OGG) using Mistral's Voxtral Mini model
- Speaker diarization — identifies and labels different speakers
- Auto-chunking for large files (>100 MB) into ~30-minute segments
- Rename speakers before exporting (proper label mapping, not text find-replace)
- Export clean formatted transcripts as .txt files
- Drag-and-drop or file picker for audio input
- Persistent API key storage

## Requirements

- Python 3.10+
- A Mistral API key (get one at https://console.mistral.ai/)
- FFmpeg installed and on PATH (required by pydub for audio processing)

## Setup

```bash
pip install -r requirements.txt
```

## Running from Source

```bash
python main.py
```

## Building the .exe

### Option 1: Using the build script

```bash
python build.py
```

### Option 2: Using PyInstaller directly

```bash
pyinstaller --onefile --windowed --name VoxtralTranscriber main.py
```

### Option 3: Using the spec file

```bash
pyinstaller build.spec
```

The executable will be created in the `dist/` folder.

### Bundling FFmpeg

For the .exe to work on machines without FFmpeg installed, you need to bundle ffmpeg.exe:

1. Download a static FFmpeg build from https://www.gyan.dev/ffmpeg/builds/ (get the essentials build)
2. Extract `ffmpeg.exe` from the archive
3. Place it in the project root or add it to the PyInstaller build:

```bash
pyinstaller --onefile --windowed --name VoxtralTranscriber --add-binary "ffmpeg.exe;." main.py
```

## Usage

1. Launch the application
2. On first run, enter your Mistral API key when prompted
3. Drag and drop an audio file onto the drop zone, or click "Browse..."
4. Click "Transcribe" and wait for processing
5. Review the transcript in the preview panel
6. Rename speakers in the Speaker Mapping section and click "Apply Names"
7. Click "Export Transcript" to save as a .txt file

## Project Structure

```
Transcriber/
├── main.py              # Application entry point
├── build.py             # PyInstaller build script
├── build.spec           # PyInstaller spec file
├── requirements.txt     # Python dependencies
├── README.md
└── src/
    ├── __init__.py
    ├── api_client.py    # Mistral API communication
    ├── chunker.py       # Audio splitting for large files
    ├── config.py        # Persistent settings (API key)
    ├── main_window.py   # PyQt6 GUI
    ├── transcript.py    # Transcript data model and formatting
    └── worker.py        # Background transcription thread
```
